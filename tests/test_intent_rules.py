"""意图分类规则测试"""
import pytest
langgraph = pytest.importorskip("langgraph", reason="langgraph not installed")

class TestIntentRules:
    def test_trip_intent(self):
        from heritage_master.agent.nodes import classify_intent_rule, Intent
        for msg in ["去广州玩","规划行程","三天游","怎么玩"]:
            r = classify_intent_rule(msg)
            assert r is not None and r.intent == Intent.TRIP

    def test_venue_intent(self):
        from heritage_master.agent.nodes import classify_intent_rule, Intent
        for msg in ["附近有什么博物馆","哪里有体验馆","文化馆在哪"]:
            r = classify_intent_rule(msg)
            assert r is not None and r.intent == Intent.VENUE

    def test_knowledge_intent(self):
        from heritage_master.agent.nodes import classify_intent_rule, Intent
        for msg in ["传承人是谁","历史起源","代表作品"]:
            r = classify_intent_rule(msg)
            assert r is not None and r.intent == Intent.KNOWLEDGE

    def test_search_intent(self):
        from heritage_master.agent.nodes import classify_intent_rule, Intent
        for msg in ["搜索昆曲","有哪些非遗项目"]:
            r = classify_intent_rule(msg)
            assert r is not None and r.intent == Intent.SEARCH

    def test_event_intent(self):
        from heritage_master.agent.nodes import classify_intent_rule, Intent
        for msg in ["最近有什么展览","有什么活动"]:
            r = classify_intent_rule(msg)
            assert r is not None and r.intent == Intent.EVENT
