"""API 集成测试 — 可观测性 + 人机协同 + 异常处理"""

import sys
import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """创建测试客户端"""
    from web.app import app
    return TestClient(app)


class TestHealthEndpoints:
    """健康检查端点"""

    def test_health_liveness(self, client):
        """GET /health 返回 alive"""
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "alive"
        assert "uptime_seconds" in data

    def test_health_readiness(self, client):
        """GET /ready 返回组件状态"""
        r = client.get("/ready")
        data = r.json()
        assert "status" in data
        assert "components" in data
        assert "llm" in data["components"]
        assert "sqlite" in data["components"]


class TestUnifiedErrors:
    """统一错误格式"""

    def test_404_format(self, client):
        """404 返回统一格式"""
        r = client.get("/api/nonexistent")
        assert r.status_code == 404
        data = r.json()
        assert data["code"] == 404
        assert "message" in data
        assert "trace_id" in data
        assert "recoverable" in data

    def test_422_validation_error(self, client):
        """入参校验返回 422"""
        r = client.post("/api/agent/graph", json={})
        assert r.status_code == 422
        data = r.json()
        assert data["code"] == 422
        assert "trace_id" in data


class TestTraceId:
    """Trace ID 追踪"""

    def test_trace_id_in_response_header(self, client):
        """响应头包含 X-Trace-Id"""
        r = client.get("/api/nonexistent")
        assert "x-trace-id" in r.headers
        assert len(r.headers["x-trace-id"]) > 0

    def test_custom_trace_id_passthrough(self, client):
        """自定义 trace_id 应透传"""
        r = client.get("/api/nonexistent", headers={"X-Trace-Id": "my_custom_id"})
        assert r.headers.get("x-trace-id") == "my_custom_id"


class TestMetricsEndpoints:
    """指标端点"""

    def test_metrics_summary(self, client):
        """GET /api/metrics 返回聚合指标"""
        r = client.get("/api/metrics")
        assert r.status_code == 200
        data = r.json()
        assert "requests" in data
        assert "latency_ms" in data
        assert "tools" in data
        assert "intents" in data
        assert "satisfaction" in data

    def test_metrics_recent(self, client):
        """GET /api/metrics/recent 返回列表"""
        r = client.get("/api/metrics/recent?limit=5")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_traces_list(self, client):
        """GET /api/traces 返回 trace 列表"""
        r = client.get("/api/traces?limit=5")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data


class TestHumanHandoff:
    """转人工端点"""

    def test_handoff_request(self, client):
        """POST /api/human-handoff 提交转人工请求"""
        r = client.post("/api/human-handoff", json={
            "user_id": "test_user",
            "session_id": "test_session",
            "reason": "需要人工帮助",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "queue_position" in data

    def test_handoff_queue(self, client):
        """GET /api/human-handoff/queue 查看队列"""
        r = client.get("/api/human-handoff/queue")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "pending" in data
