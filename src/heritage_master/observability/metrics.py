"""
指标收集器 — 请求级指标 + 聚合统计

收集：
- 请求计数（总数/成功/失败）
- 响应时间分布（P50/P95/P99）
- 工具调用成功率
- 意图分布
- 用户满意度（通过 feedback 接口回填）
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("heritage.metrics")


@dataclass
class RequestMetric:
    """单次请求指标"""
    trace_id: str
    user_id: str
    session_id: str
    intent: str
    started_at: float
    finished_at: float = 0.0
    status: str = "running"  # running / success / failed
    tool_calls: int = 0
    tool_successes: int = 0
    tool_failures: int = 0
    reply_len: int = 0
    accepted: bool | None = None  # 用户是否接受（feedback 回填）
    error_message: str = ""


class MetricsCollector:
    """聚合指标收集器（线程安全）"""

    def __init__(self, max_recent: int = 500):
        self._recent: deque[RequestMetric] = deque(maxlen=max_recent)
        self._lock = threading.Lock()
        self._db_conn = None  # SQLite 连接（外部注入）

        # 聚合计数器
        self._total_requests = 0
        self._success_requests = 0
        self._failed_requests = 0
        self._tool_calls = 0
        self._tool_successes = 0
        self._tool_failures = 0
        self._intent_counts: dict[str, int] = defaultdict(int)
        self._accepted_count = 0
        self._rejected_count = 0
        self._latencies: list[float] = []

    def init_db(self, db_path: str) -> None:
        """初始化 SQLite 持久化"""
        import sqlite3
        self._db_conn = sqlite3.connect(db_path, check_same_thread=False)
        self._db_conn.execute("""
            CREATE TABLE IF NOT EXISTS request_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT,
                user_id TEXT,
                session_id TEXT,
                intent TEXT,
                status TEXT,
                latency_ms REAL,
                tool_calls INTEGER DEFAULT 0,
                tool_successes INTEGER DEFAULT 0,
                tool_failures INTEGER DEFAULT 0,
                reply_len INTEGER DEFAULT 0,
                accepted INTEGER DEFAULT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        self._db_conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_created ON request_metrics(created_at)
        """)
        self._db_conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_intent ON request_metrics(intent)
        """)
        self._db_conn.commit()

    def _persist_metric(self, metric: RequestMetric) -> None:
        """写入 SQLite"""
        if not self._db_conn:
            return
        try:
            latency = (metric.finished_at - metric.started_at) * 1000 if metric.finished_at else 0
            accepted_val = 1 if metric.accepted is True else (0 if metric.accepted is False else None)
            self._db_conn.execute(
                """INSERT INTO request_metrics
                   (trace_id, user_id, session_id, intent, status, latency_ms,
                    tool_calls, tool_successes, tool_failures, reply_len, accepted)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (metric.trace_id, metric.user_id, metric.session_id,
                 metric.intent, metric.status, latency,
                 metric.tool_calls, metric.tool_successes, metric.tool_failures,
                 metric.reply_len, accepted_val),
            )
            self._db_conn.commit()
        except Exception as e:
            logger.warning("指标持久化失败: %s", e)

    def _persist_feedback(self, trace_id: str, accepted: bool) -> None:
        """更新 SQLite 中的满意度"""
        if not self._db_conn:
            return
        try:
            self._db_conn.execute(
                "UPDATE request_metrics SET accepted = ? WHERE trace_id = ?",
                (1 if accepted else 0, trace_id),
            )
            self._db_conn.commit()
        except Exception as e:
            logger.warning("反馈持久化失败: %s", e)

    def record_request(self, metric: RequestMetric) -> None:
        """记录一次请求的完整指标"""
        with self._lock:
            self._recent.append(metric)
            self._total_requests += 1

            if metric.status == "success":
                self._success_requests += 1
            elif metric.status == "failed":
                self._failed_requests += 1

            self._tool_calls += metric.tool_calls
            self._tool_successes += metric.tool_successes
            self._tool_failures += metric.tool_failures

            if metric.intent:
                self._intent_counts[metric.intent] += 1

            latency = metric.finished_at - metric.started_at
            if latency > 0:
                self._latencies.append(latency * 1000)  # ms
                if len(self._latencies) > 1000:
                    self._latencies = self._latencies[-1000:]

            if metric.accepted is True:
                self._accepted_count += 1
            elif metric.accepted is False:
                self._rejected_count += 1

        # 持久化到 SQLite（锁外执行，避免长时间持锁）
        self._persist_metric(metric)

    def record_feedback(self, trace_id: str, accepted: bool) -> None:
        """回填用户满意度"""
        with self._lock:
            for m in self._recent:
                if m.trace_id == trace_id:
                    m.accepted = accepted
                    if accepted:
                        self._accepted_count += 1
                    else:
                        self._rejected_count += 1
                    break
        self._persist_feedback(trace_id, accepted)

    def get_summary(self) -> dict[str, Any]:
        """获取聚合指标摘要"""
        with self._lock:
            # 计算百分位
            p50 = p95 = p99 = 0.0
            if self._latencies:
                sorted_lat = sorted(self._latencies)
                n = len(sorted_lat)
                p50 = sorted_lat[int(n * 0.5)]
                p95 = sorted_lat[int(n * 0.95)]
                p99 = sorted_lat[min(int(n * 0.99), n - 1)]

            success_rate = (
                self._success_requests / self._total_requests * 100
                if self._total_requests > 0
                else 0
            )
            tool_success_rate = (
                self._tool_successes / self._tool_calls * 100
                if self._tool_calls > 0
                else 0
            )
            total_feedback = self._accepted_count + self._rejected_count
            acceptance_rate = (
                self._accepted_count / total_feedback * 100
                if total_feedback > 0
                else 0
            )

            return {
                "requests": {
                    "total": self._total_requests,
                    "success": self._success_requests,
                    "failed": self._failed_requests,
                    "success_rate_pct": round(success_rate, 1),
                },
                "latency_ms": {
                    "p50": round(p50, 1),
                    "p95": round(p95, 1),
                    "p99": round(p99, 1),
                },
                "tools": {
                    "total_calls": self._tool_calls,
                    "successes": self._tool_successes,
                    "failures": self._tool_failures,
                    "success_rate_pct": round(tool_success_rate, 1),
                },
                "intents": dict(self._intent_counts),
                "satisfaction": {
                    "accepted": self._accepted_count,
                    "rejected": self._rejected_count,
                    "acceptance_rate_pct": round(acceptance_rate, 1),
                },
            }

    def get_recent(self, limit: int = 20) -> list[dict]:
        """获取最近的请求指标"""
        with self._lock:
            recent = list(self._recent)[-limit:]
            return [
                {
                    "trace_id": m.trace_id,
                    "user_id": m.user_id,
                    "intent": m.intent,
                    "status": m.status,
                    "latency_ms": round((m.finished_at - m.started_at) * 1000, 1) if m.finished_at else 0,
                    "tool_calls": m.tool_calls,
                    "tool_successes": m.tool_successes,
                    "reply_len": m.reply_len,
                    "accepted": m.accepted,
                }
                for m in reversed(recent)
            ]


# 全局单例
metrics = MetricsCollector()
