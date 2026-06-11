"""指标收集器测试"""

import sys
import time
import pytest

sys.path.insert(0, "src")

from heritage_master.observability.metrics import MetricsCollector, RequestMetric


class TestMetricsCollector:
    """指标收集器"""

    def setup_method(self):
        """每个测试前重置"""
        self.collector = MetricsCollector(max_recent=100)

    def _make_metric(self, **kwargs) -> RequestMetric:
        """创建测试用指标"""
        defaults = {
            "trace_id": "tr_test_001",
            "user_id": "user_1",
            "session_id": "sess_1",
            "intent": "search",
            "started_at": time.time() - 1.0,
            "finished_at": time.time(),
            "status": "success",
            "tool_calls": 2,
            "tool_successes": 2,
            "tool_failures": 0,
            "reply_len": 200,
        }
        defaults.update(kwargs)
        return RequestMetric(**defaults)

    def test_record_single_request(self):
        """记录单次请求"""
        m = self._make_metric()
        self.collector.record_request(m)

        summary = self.collector.get_summary()
        assert summary["requests"]["total"] == 1
        assert summary["requests"]["success"] == 1
        assert summary["requests"]["failed"] == 0
        assert summary["requests"]["success_rate_pct"] == 100.0

    def test_record_success_and_failure(self):
        """记录成功和失败请求"""
        self.collector.record_request(self._make_metric(status="success"))
        self.collector.record_request(self._make_metric(status="success"))
        self.collector.record_request(self._make_metric(status="failed"))

        summary = self.collector.get_summary()
        assert summary["requests"]["total"] == 3
        assert summary["requests"]["success"] == 2
        assert summary["requests"]["failed"] == 1
        assert abs(summary["requests"]["success_rate_pct"] - 66.7) < 0.1

    def test_tool_stats(self):
        """工具调用统计"""
        self.collector.record_request(self._make_metric(tool_calls=3, tool_successes=2, tool_failures=1))
        self.collector.record_request(self._make_metric(tool_calls=1, tool_successes=1, tool_failures=0))

        summary = self.collector.get_summary()
        assert summary["tools"]["total_calls"] == 4
        assert summary["tools"]["successes"] == 3
        assert summary["tools"]["failures"] == 1
        assert summary["tools"]["success_rate_pct"] == 75.0

    def test_intent_distribution(self):
        """意图分布统计"""
        self.collector.record_request(self._make_metric(intent="search"))
        self.collector.record_request(self._make_metric(intent="search"))
        self.collector.record_request(self._make_metric(intent="venue"))

        summary = self.collector.get_summary()
        assert summary["intents"]["search"] == 2
        assert summary["intents"]["venue"] == 1

    def test_latency_percentiles(self):
        """延迟百分位计算"""
        # 创建 10 个请求，延迟从 100ms 到 1000ms
        for i in range(10):
            self.collector.record_request(
                self._make_metric(
                    started_at=time.time() - (i + 1) * 0.1,
                    finished_at=time.time(),
                )
            )

        summary = self.collector.get_summary()
        assert summary["latency_ms"]["p50"] > 0
        assert summary["latency_ms"]["p95"] >= summary["latency_ms"]["p50"]
        assert summary["latency_ms"]["p99"] >= summary["latency_ms"]["p95"]

    def test_feedback_accepted(self):
        """满意度回填 — 接受"""
        self.collector.record_request(self._make_metric(trace_id="tr_fb_001"))
        self.collector.record_feedback("tr_fb_001", True)

        summary = self.collector.get_summary()
        assert summary["satisfaction"]["accepted"] == 1
        assert summary["satisfaction"]["rejected"] == 0

    def test_feedback_rejected(self):
        """满意度回填 — 拒绝"""
        self.collector.record_request(self._make_metric(trace_id="tr_fb_002"))
        self.collector.record_feedback("tr_fb_002", False)

        summary = self.collector.get_summary()
        assert summary["satisfaction"]["accepted"] == 0
        assert summary["satisfaction"]["rejected"] == 1

    def test_acceptance_rate(self):
        """满意度百分比"""
        self.collector.record_request(self._make_metric(trace_id="tr_a1"))
        self.collector.record_request(self._make_metric(trace_id="tr_a2"))
        self.collector.record_feedback("tr_a1", True)
        self.collector.record_feedback("tr_a2", False)

        summary = self.collector.get_summary()
        assert summary["satisfaction"]["acceptance_rate_pct"] == 50.0

    def test_recent_list(self):
        """最近请求列表"""
        for i in range(5):
            self.collector.record_request(self._make_metric(trace_id=f"tr_{i}"))

        recent = self.collector.get_recent(limit=3)
        assert len(recent) == 3
        # 应该是最近的 3 个（倒序）
        assert recent[0]["trace_id"] == "tr_4"

    def test_max_recent_limit(self):
        """max_recent 限制"""
        collector = MetricsCollector(max_recent=5)
        for i in range(10):
            collector.record_request(self._make_metric(trace_id=f"tr_{i}"))

        recent = collector.get_recent(limit=100)
        assert len(recent) == 5  # 只保留最近 5 个

    def test_empty_summary(self):
        """空收集器的摘要"""
        summary = self.collector.get_summary()
        assert summary["requests"]["total"] == 0
        assert summary["latency_ms"]["p50"] == 0.0
