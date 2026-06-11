"""意图识别测试 — 规则匹配 + 边界 case"""

import sys
import pytest

sys.path.insert(0, "src")

from heritage_master.agent.nodes import (
    Intent,
    IntentResult,
    classify_intent_rule,
    TOOL_HINTS,
)


class TestIntentRuleClassification:
    """规则匹配意图分类"""

    def test_venue_intent(self):
        """场馆相关消息应识别为 venue"""
        cases = ["广州哪里有博物馆", "附近有非遗体验馆吗", "场馆地址在哪"]
        for msg in cases:
            result = classify_intent_rule(msg)
            assert result is not None, f"未识别: {msg}"
            assert result.intent == Intent.VENUE, f"{msg} -> {result.intent}"
            assert result.method == "rule"

    def test_trip_intent(self):
        """旅行相关消息应识别为 trip"""
        cases = ["潮州三天旅行攻略", "怎么规划路线", "去苏州玩几天合适"]
        for msg in cases:
            result = classify_intent_rule(msg)
            assert result is not None, f"未识别: {msg}"
            assert result.intent == Intent.TRIP

    def test_knowledge_intent(self):
        """知识问答应识别为 knowledge"""
        cases = ["谁是叶汉钟", "传承人有哪些", "昆曲的历史起源", "师承关系是什么"]
        for msg in cases:
            result = classify_intent_rule(msg)
            assert result is not None, f"未识别: {msg}"
            assert result.intent == Intent.KNOWLEDGE

    def test_event_intent(self):
        """活动查询应识别为 event"""
        cases = ["最近有什么展览", "有没有工作坊可以参加"]
        for msg in cases:
            result = classify_intent_rule(msg)
            assert result is not None, f"未识别: {msg}"
            assert result.intent == Intent.EVENT

    def test_search_intent(self):
        """搜索类消息应识别为 search"""
        cases = ["搜索刺绣", "有哪些非遗项目", "查一下广东的非遗"]
        for msg in cases:
            result = classify_intent_rule(msg)
            assert result is not None, f"未识别: {msg}"
            assert result.intent == Intent.SEARCH

    def test_chat_returns_none(self):
        """闲聊消息规则匹配应返回 None（需 LLM 兜底）"""
        cases = ["你好", "今天天气不错", "谢谢"]
        for msg in cases:
            result = classify_intent_rule(msg)
            assert result is None, f"不应匹配: {msg} -> {result}"

    def test_empty_message_returns_none(self):
        """空消息应返回 None"""
        assert classify_intent_rule("") is None
        assert classify_intent_rule("   ") is None

    def test_priority_order(self):
        """同时匹配多个意图时，应按优先级返回"""
        # "广州博物馆有什么活动" 同时匹配 venue 和 event
        # venue 排在 event 前面（_INTENT_PATTERNS 中 venue 在前）
        result = classify_intent_rule("广州博物馆有什么活动")
        assert result is not None
        # 应该匹配到 venue（先出现的模式）
        assert result.intent == Intent.VENUE


class TestToolHints:
    """工具提示映射"""

    def test_all_intents_have_hints(self):
        """所有意图都有对应的工具提示"""
        for intent in Intent:
            assert intent in TOOL_HINTS, f"缺少提示: {intent}"

    def test_chat_hint_says_no_tool(self):
        """chat 意图应提示不使用工具"""
        assert "不需要" in TOOL_HINTS[Intent.CHAT] or "直接" in TOOL_HINTS[Intent.CHAT]
