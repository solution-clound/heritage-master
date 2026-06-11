"""长期记忆系统测试"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch


class TestMemoryManager:
    """MemoryManager CRUD 测试"""

    def _make_manager(self, tmp_path):
        """创建使用临时目录的 MemoryManager"""
        from heritage_master.tools.memory import MemoryManager, MEMORY_DIR
        # 直接 patch MEMORY_DIR 模块级变量
        import heritage_master.tools.memory as mem_mod
        original = mem_mod.MEMORY_DIR
        mem_mod.MEMORY_DIR = Path(str(tmp_path))
        mm = MemoryManager()
        # 在 teardown 恢复
        self._cleanup = lambda: setattr(mem_mod, 'MEMORY_DIR', original)
        return mm

    def test_load_creates_empty(self, tmp_path):
        mm = self._make_manager(tmp_path)
        memory = mm.load_memory("explorer", "user1")
        assert memory["version"] == "1.0"
        assert memory["user_id"] == "user1"
        assert memory["profile"]["relationship_stage"] == "入门期"
        assert memory["core_memories"] == []

    def test_add_core_memory(self, tmp_path):
        mm = self._make_manager(tmp_path)
        mem_id = mm.add_core_memory("explorer", "user1", {
            "type": "interest", "content": "用户对昆曲感兴趣", "importance": 8,
        })
        assert mem_id.startswith("mem_")
        memories = mm.get_core_memories("explorer", "user1")
        assert len(memories) == 1
        assert memories[0]["content"] == "用户对昆曲感兴趣"

    def test_get_core_memories_filter_by_type(self, tmp_path):
        mm = self._make_manager(tmp_path)
        mm.add_core_memory("explorer", "user1", {"type": "interest", "content": "A"})
        mm.add_core_memory("explorer", "user1", {"type": "preference", "content": "B"})
        mm.add_core_memory("explorer", "user1", {"type": "interest", "content": "C"})
        interests = mm.get_core_memories("explorer", "user1", memory_type="interest")
        assert len(interests) == 2
        assert all(m["type"] == "interest" for m in interests)

    def test_update_memory_reference(self, tmp_path):
        mm = self._make_manager(tmp_path)
        mem_id = mm.add_core_memory("explorer", "user1", {"type": "interest", "content": "test"})
        mm.update_memory_reference("explorer", "user1", mem_id)
        mm.update_memory_reference("explorer", "user1", mem_id)
        # 直接读文件验证，不依赖排序
        memory = mm.load_memory("explorer", "user1")
        mem = [m for m in memory["core_memories"] if m["id"] == mem_id][0]
        assert mem["reference_count"] == 2
        assert mem["last_referenced"] is not None

    def test_add_conversation_topic(self, tmp_path):
        mm = self._make_manager(tmp_path)
        mm.add_conversation_topic("explorer", "user1", "昆曲")
        mm.add_conversation_topic("explorer", "user1", "昆曲")
        memory = mm.load_memory("explorer", "user1")
        topics = memory["data_records"]["conversation_topics"]
        assert len(topics) == 1
        assert topics[0]["count"] == 2

    def test_update_teaching_progress(self, tmp_path):
        mm = self._make_manager(tmp_path)
        mm.update_teaching_progress("explorer", "user1", current_stage="成长期")
        mm.update_teaching_progress("explorer", "user1", completed_topics="昆曲基础")
        memory = mm.load_memory("explorer", "user1")
        tp = memory["teaching_progress"]
        assert tp["current_stage"] == "成长期"
        assert "昆曲基础" in tp["completed_topics"]

    def test_memory_context_generation(self, tmp_path):
        mm = self._make_manager(tmp_path)
        mm.add_core_memory("explorer", "user1", {"type": "interest", "content": "喜欢昆曲", "importance": 8})
        mm.update_teaching_progress("explorer", "user1", current_stage="成长期")
        ctx = mm.get_memory_context("explorer", "user1")
        assert "喜欢昆曲" in ctx
        assert "成长期" in ctx


class TestMemoryExtractor:
    """MemoryExtractor 规则提取测试"""

    def test_extract_interest(self):
        from heritage_master.tools.memory import MemoryExtractor
        ext = MemoryExtractor()
        results = ext.extract_by_rules("我想了解一下昆曲的历史", "", "explorer")
        assert len(results) >= 1
        assert any(r["type"] == "interest" for r in results)

    def test_extract_preference(self):
        from heritage_master.tools.memory import MemoryExtractor
        ext = MemoryExtractor()
        results = ext.extract_by_rules("我喜欢广绣的色彩", "", "explorer")
        assert any(r["type"] == "preference" for r in results)

    def test_extract_empty_message(self):
        from heritage_master.tools.memory import MemoryExtractor
        ext = MemoryExtractor()
        results = ext.extract_by_rules("", "", "explorer")
        assert results == []

    def test_extract_short_message(self):
        from heritage_master.tools.memory import MemoryExtractor
        ext = MemoryExtractor()
        results = ext.extract_by_rules("好", "", "explorer")
        assert results == []

    def test_extract_topics(self):
        from heritage_master.tools.memory import MemoryExtractor
        ext = MemoryExtractor()
        topics = ext.extract_topics("我想学习凤凰单丛的冲泡方法", "chagongfu")
        assert "凤凰单丛" in topics


class TestGreetingGenerator:
    """问候生成测试"""

    def test_first_meeting_greeting(self):
        from heritage_master.tools.memory import GreetingGenerator
        gen = GreetingGenerator()
        memory = {
            "profile": {"relationship_stage": "入门期"},
            "core_memories": [],
            "data_records": {"conversation_topics": [], "visit_log": []},
            "teaching_progress": {},
        }
        greeting = gen.generate_greeting("explorer", memory)
        assert len(greeting) > 0

    def test_returning_user_greeting(self):
        from heritage_master.tools.memory import GreetingGenerator
        from datetime import datetime, timedelta, timezone
        gen = GreetingGenerator()
        last_talk = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        memory = {
            "profile": {"relationship_stage": "成长期", "last_talk_at": last_talk},
            "core_memories": [],
            "data_records": {"conversation_topics": [], "visit_log": [{"date": "2025-01-01"}]},
            "teaching_progress": {},
        }
        greeting = gen.generate_greeting("explorer", memory)
        # Should have content and mention absence somehow
        assert len(greeting) > 5
