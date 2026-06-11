# -*- coding: utf-8 -*-
"""人设加载器 & 场馆查找 & 配置 & 可观测性 & 知识图谱 & Token预算测试"""
import pytest


class TestPersonaLoader:
    def test_list_personas(self):
        from heritage_master.tools.persona_loader import list_available_personas
        assert len(list_available_personas()) >= 5

    def test_known_persona(self):
        from heritage_master.tools.persona_loader import load_persona
        assert load_persona("chagongfu") is not None

    def test_unknown_persona(self):
        from heritage_master.tools.persona_loader import load_persona
        assert load_persona("nonexistent_xyz") is None

    def test_system_prompt(self):
        from heritage_master.tools.persona_loader import get_persona_system_prompt
        p = get_persona_system_prompt("chagongfu")
        assert p is not None and len(p) > 100

    def test_all_personas_have_prompt(self):
        from heritage_master.tools.persona_loader import list_available_personas, get_persona_system_prompt
        for slug in list_available_personas():
            assert get_persona_system_prompt(slug) is not None


class TestVenueFinder:
    def test_format_empty(self):
        from heritage_master.tools.venue_finder import format_venue_list
        assert "test_city" in format_venue_list([], "test_city")

    def test_format_with_venues(self):
        from heritage_master.tools.venue_finder import format_venue_list
        v = [{"name":"v1","address":"a","rating":"4.5","tel":"123","district":"d","distance":"1000","business_hours":"09-17"}]
        r = format_venue_list(v, "city")
        assert "v1" in r and "4.5" in r


class TestConfig:
    def test_settings_loads(self):
        from heritage_master.config import settings
        assert settings is not None

    def test_amap_key(self):
        from heritage_master.config import settings
        assert settings.amap_key

    def test_llm_config(self):
        from heritage_master.config import settings
        assert settings.llm_model and settings.llm_base_url

    def test_redis_config(self):
        from heritage_master.config import settings
        assert settings.redis_host == "localhost" and settings.redis_port == 6379


class TestMetrics:
    def test_record_and_summary(self):
        from heritage_master.observability.metrics import metrics, RequestMetric
        import time
        m = RequestMetric(trace_id="t1", user_id="u1", session_id="s1", intent="search", started_at=time.time(), finished_at=time.time()+0.1)
        metrics.record_request(m)
        s = metrics.get_summary()
        assert s["requests"]["total"] >= 1 and "latency_ms" in s


class TestTracer:
    def test_trace_lifecycle(self):
        from heritage_master.observability.tracer import collector
        collector.start_trace("tr_misc_001", user_id="u1", session_id="s1")
        collector.add_step("tr_misc_001", "step1")
        collector.end_trace("tr_misc_001", status="completed", total_ms=100)
        t = collector.get_trace("tr_misc_001")
        assert t is not None and t.status == "completed"


class TestKnowledgeGraph:
    def test_search_nodes(self):
        from heritage_master.data.knowledge_graph import search_nodes
        assert isinstance(search_nodes("test", limit=5), list)

    def test_graph_stats(self):
        from heritage_master.data.knowledge_graph import get_graph_stats
        assert isinstance(get_graph_stats(), dict)


class TestTokenBudget:
    @pytest.fixture(autouse=True)
    def _require_langgraph(self):
        pytest.importorskip("langgraph", reason="langgraph not installed")
    def test_unlimited(self):
        from heritage_master.agent.token_budget import check_budget
        assert check_budget(-1, "agent") is True

    def test_sufficient(self):
        from heritage_master.agent.token_budget import check_budget
        assert check_budget(6000, "agent") is True

    def test_insufficient(self):
        from heritage_master.agent.token_budget import check_budget
        assert check_budget(100, "agent") is False

    def test_deduct(self):
        from heritage_master.agent.token_budget import deduct
        assert 0 < deduct(6000, "agent") < 6000

    def test_deduct_unlimited(self):
        from heritage_master.agent.token_budget import deduct
        assert deduct(-1, "agent") == -1
