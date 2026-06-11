"""
可观测性 + 人机协同 API

GET  /api/metrics          — 聚合指标摘要
GET  /api/metrics/recent   — 最近请求列表
GET  /api/traces           — 最近 trace 列表
GET  /api/traces/{id}      — 单个 trace 详情
POST /api/feedback         — 用户反馈（满意度回填）
POST /api/human-handoff    — 转人工请求
"""

from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["observability"])


# ─── 指标端点 ─────────────────────────────────────────────

@router.get("/api/metrics")
async def api_metrics():
    """聚合指标摘要：请求成功率、延迟分布、工具成功率、满意度"""
    from heritage_master.observability.metrics import metrics
    return metrics.get_summary()


@router.get("/api/metrics/recent")
async def api_metrics_recent(limit: int = 20):
    """最近 N 条请求的详细指标"""
    from heritage_master.observability.metrics import metrics
    return {"items": metrics.get_recent(limit)}


# ─── Trace 端点 ───────────────────────────────────────────

@router.get("/api/traces")
async def api_traces(limit: int = 20):
    """最近的 trace 列表"""
    from heritage_master.observability.tracer import collector
    traces = collector.get_recent(limit)
    return {
        "items": [
            {
                "trace_id": t.trace_id,
                "user_id": t.user_id,
                "session_id": t.session_id,
                "status": t.status,
                "started_at": t.started_at,
                "total_ms": t.total_ms,
                "reply_len": t.reply_len,
                "steps": [
                    {
                        "timestamp": s.timestamp,
                        "event": s.event,
                        "data": s.data,
                        "duration_ms": s.duration_ms,
                    }
                    for s in t.steps
                ],
            }
            for t in traces
        ]
    }


@router.get("/api/traces/{trace_id}")
async def api_trace_detail(trace_id: str):
    """单个 trace 详情"""
    from heritage_master.observability.tracer import collector
    trace = collector.get_trace(trace_id)
    if not trace:
        return {"error": f"Trace {trace_id} not found"}
    return {
        "trace_id": trace.trace_id,
        "user_id": trace.user_id,
        "session_id": trace.session_id,
        "status": trace.status,
        "started_at": trace.started_at,
        "total_ms": trace.total_ms,
        "reply_len": trace.reply_len,
        "steps": [
            {
                "timestamp": s.timestamp,
                "event": s.event,
                "data": s.data,
                "duration_ms": s.duration_ms,
            }
            for s in trace.steps
        ],
    }


# ─── 用户反馈 ─────────────────────────────────────────────

class FeedbackBody(BaseModel):
    trace_id: str = Field(..., description="被评价请求的 trace_id")
    accepted: bool = Field(..., description="用户是否接受结果")
    comment: str = Field(default="", max_length=500)


@router.post("/api/agent-feedback")
async def api_feedback(body: FeedbackBody):
    """用户反馈 — 回填满意度到指标系统

    使用 /api/agent-feedback 避免与原有 /api/feedback 冲突。
    """
    from heritage_master.observability.metrics import metrics
    metrics.record_feedback(body.trace_id, body.accepted)

    # 同时存到 feedback 表
    try:
        from heritage_master.data.db import get_conn
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO feedback (trace_id, rating, reason, created_at) VALUES (?, ?, ?, ?)",
                (body.trace_id, "good" if body.accepted else "bad", body.comment, now),
            )
    except Exception:
        pass  # 非关键路径，失败不影响响应

    return {"ok": True, "message": "感谢反馈！"}


# ─── 转人工 ───────────────────────────────────────────────

class HandoffBody(BaseModel):
    user_id: str = Field(..., description="用户 ID")
    session_id: str = Field(default="", description="会话 ID")
    reason: str = Field(default="", description="转人工原因")
    message: str = Field(default="", description="用户最后的消息")


# 内存中的转人工请求队列
_handoff_queue: list[dict] = []


@router.post("/api/human-handoff")
async def api_human_handoff(body: HandoffBody):
    """转人工请求 — 将用户转接到人工客服

    前端收到此响应后应：
    1. 显示"正在为您转接人工客服..."
    2. 切换到人工客服界面
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    request = {
        "user_id": body.user_id,
        "session_id": body.session_id,
        "reason": body.reason,
        "message": body.message,
        "created_at": now,
        "status": "pending",
    }
    _handoff_queue.append(request)

    # 只保留最近 100 条
    if len(_handoff_queue) > 100:
        _handoff_queue.pop(0)

    return {
        "ok": True,
        "message": "已为您转接人工客服，请稍候...",
        "queue_position": len([r for r in _handoff_queue if r["status"] == "pending"]),
    }


@router.get("/api/human-handoff/queue")
async def api_handoff_queue():
    """管理员查看转人工队列"""
    return {
        "items": _handoff_queue,
        "pending": len([r for r in _handoff_queue if r["status"] == "pending"]),
    }
