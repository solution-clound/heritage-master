"""上下文管理测试"""

import sys
import pytest
import tempfile
import os

sys.path.insert(0, "src")

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


class TestContextTrimmer:
    """上下文窗口裁剪"""

    def _make_messages(self, count: int) -> list:
        """生成 N 条测试消息"""
        messages = [SystemMessage(content="你是非遗助手")]
        for i in range(count):
            messages.append(HumanMessage(content=f"问题{i}"))
            messages.append(AIMessage(content=f"回答{i}"))
        return messages

    def test_short_context_not_trimmed(self):
        """短上下文不应被裁剪"""
        from heritage_master.agent.context import ContextManager
        ctx = ContextManager.__new__(ContextManager)
        messages = self._make_messages(5)  # 1 system + 10 对话 = 11 条
        result = ctx._trim_context(messages)
        assert len(result) == len(messages)

    def test_long_context_trimmed(self):
        """长上下文应被裁剪"""
        from heritage_master.agent.context import ContextManager, MAX_CONTEXT_MESSAGES
        ctx = ContextManager.__new__(ContextManager)
        messages = self._make_messages(20)  # 1 system + 40 对话 = 41 条
        assert len(messages) > MAX_CONTEXT_MESSAGES
        result = ctx._trim_context(messages)
        assert len(result) < len(messages)
        # 第一条应该是 SystemMessage
        assert isinstance(result[0], SystemMessage)
        # 裁剪后保留最近的对话消息
        assert len(result) > 1

    def test_trim_preserves_system_message(self):
        """裁剪后 SystemMessage 保留"""
        from heritage_master.agent.context import ContextManager
        ctx = ContextManager.__new__(ContextManager)
        messages = self._make_messages(20)
        result = ctx._trim_context(messages)
        assert isinstance(result[0], SystemMessage)
        assert result[0].content == "你是非遗助手"


class TestProfileContext:
    """用户画像上下文构建"""

    def test_empty_memory_returns_empty(self):
        """无记忆时返回空字符串"""
        from heritage_master.agent.context import ContextManager
        from unittest.mock import MagicMock

        ctx = ContextManager.__new__(ContextManager)
        ctx._memory_manager = MagicMock()
        ctx._memory_manager.load_memory.return_value = None

        result = ctx._build_profile_context("user_1", "explorer")
        assert result == ""

    def test_profile_with_interests(self):
        """有兴趣标签时返回格式化文本"""
        from heritage_master.agent.context import ContextManager
        from unittest.mock import MagicMock

        ctx = ContextManager.__new__(ContextManager)
        ctx._memory_manager = MagicMock()
        ctx._memory_manager.load_memory.return_value = {
            "profile": {
                "relationship_stage": "成长期",
                "interest_tags": ["茶艺", "刺绣"],
                "personality_notes": "认真好学",
                "question_count": 15,
            },
            "teaching_progress": {
                "completed_topics": ["潮州功夫茶", "广绣入门"],
            },
            "core_memories": [],
        }

        result = ctx._build_profile_context("user_1", "explorer")
        assert "成长期" in result
        assert "茶艺" in result
        assert "刺绣" in result
        assert "认真好学" in result
