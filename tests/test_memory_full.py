# -*- coding: utf-8 -*-
"""长期记忆系统测试 — CRUD、提取规则、问候生成、向量检索"""
import pytest
from pathlib import Path
from unittest.mock import patch
from heritage_master.tools.memory import (
    MemoryManager, MemoryExtractor, GreetingGenerator,
    MEMORY_TYPES, _normalize_stage, _empty_memory,
)


class TestMemoryManagerCRUD:
    def _make_manager(self, tmp_path):
        import heritage_master.tools.memory as mem_mod
        original = mem_mod.MEMORY_DIR
        mem_mod.MEMORY_DIR = Path(str(tmp_path))
        mm = MemoryManager()
        self._cleanup = lambda: setattr(mem_mod, "MEMORY_DIR", original)
        return mm

    def test_load_creates_empty(self, tmp_path):
        mm = self._make_manager(tmp_path)
        mem = mm.load_memory("explorer", "user1")
        assert mem["version"] == "1.0"
        assert mem["user_id"] == "user1"
        assert mem["core_memories"] == []

    def test_add_and_get_memory(self, tmp_path):
        mm = self._make_manager(tmp_path)
        mid = mm.add_core_memory("explorer", "u1", {"type": "interest", "content": "test", "importance": 8})
        assert mid.startswith("mem_")
        mems = mm.get_core_memories("explorer", "u1")
        assert len(mems) == 1
        assert mems[0]["content"] == "test"

    def test_filter_by_type(self, tmp_path):
        mm = self._make_manager(tmp_path)
        mm.add_core_memory("explorer", "u1", {"type": "interest", "content": "A"})
        mm.add_core_memory("explorer", "u1", {"type": "preference", "content": "B"})
        mm.add_core_memory("explorer", "u1", {"type": "interest", "content": "C"})
        interests = mm.get_core_memories("explorer", "u1", memory_type="interest")
        assert len(interests) == 2

    def test_update_reference(self, tmp_path):
        mm = self._make_manager(tmp_path)
        mid = mm.add_core_memory("explorer", "u1", {"type": "interest", "content": "x"})
        mm.update_memory_reference("explorer", "u1", mid)
        mm.update_memory_reference("explorer", "u1", mid)
        mem = mm.load_memory("explorer", "u1")
        m = [x for x in mem["core_memories"] if x["id"] == mid][0]
        assert m["reference_count"] == 2

    def test_conversation_topic(self, tmp_path):
        mm = self._make_manager(tmp_path)
        mm.add_conversation_topic("explorer", "u1", "昆曲")
        mm.add_conversation_topic("explorer", "u1", "昆曲")
        mem = mm.load_memory("explorer", "u1")
        topics = mem["data_records"]["conversation_topics"]
        assert len(topics) == 1
        assert topics[0]["count"] == 2

    def test_teaching_progress(self, tmp_path):
        mm = self._make_manager(tmp_path)
        mm.update_teaching_progress("explorer", "u1", current_stage="成长期")
        mm.update_teaching_progress("explorer", "u1", completed_topics="昆曲基础")
        mem = mm.load_memory("explorer", "u1")
        assert mem["teaching_progress"]["current_stage"] == "成长期"
        assert "昆曲基础" in mem["teaching_progress"]["completed_topics"]

    def test_memory_context(self, tmp_path):
        mm = self._make_manager(tmp_path)
        mm.add_core_memory("explorer", "u1", {"type": "interest", "content": "喜欢昆曲", "importance": 8})
        ctx = mm.get_memory_context("explorer", "u1")
        assert "喜欢昆曲" in ctx

    def test_greeting_context(self, tmp_path):
        mm = self._make_manager(tmp_path)
        mm.add_core_memory("explorer", "u1", {"type": "interest", "content": "test"})
        gctx = mm.get_greeting_context("explorer", "u1")
        assert "is_first" in gctx
        assert "relationship_stage" in gctx


class TestMemoryExtractor:
    def test_extract_interest(self):
        ext = MemoryExtractor()
        results = ext.extract_by_rules("我想了解一下昆曲的历史", "", "explorer")
        assert any(r["type"] == "interest" for r in results)

    def test_extract_preference(self):
        ext = MemoryExtractor()
        results = ext.extract_by_rules("我喜欢广绣的色彩", "", "explorer")
        assert any(r["type"] == "preference" for r in results)

    def test_extract_empty(self):
        ext = MemoryExtractor()
        assert ext.extract_by_rules("", "", "explorer") == []

    def test_extract_short(self):
        ext = MemoryExtractor()
        assert ext.extract_by_rules("好", "", "explorer") == []

    def test_extract_milestone(self):
        ext = MemoryExtractor()
        results = ext.extract_by_rules("我第一次学会了昆曲", "", "explorer")
        assert any(r["type"] == "milestone" for r in results)

    def test_extract_topics(self):
        ext = MemoryExtractor()
        topics = ext.extract_topics("我想学习凤凰单丛的冲泡方法", "chagongfu")
        assert "凤凰单丛" in topics


class TestNormalizeStage:
    def test_valid_stages(self):
        for stage in ["入门期", "成长期", "精进期", "传承期"]:
            assert _normalize_stage(stage) == stage

    def test_alias(self):
        assert _normalize_stage("试探期") == "入门期"
        assert _normalize_stage("初期") == "入门期"

    def test_unknown_defaults_to_entry(self):
        assert _normalize_stage("unknown") == "入门期"


class TestGreetingGenerator:
    def test_first_meeting(self):
        gen = GreetingGenerator()
        mem = {"profile": {"relationship_stage": "入门期"}, "core_memories": [],
               "data_records": {"conversation_topics": [], "visit_log": []}, "teaching_progress": {}}
        g = gen.generate_greeting("explorer", mem)
        assert len(g) > 0

    def test_master_greeting(self):
        gen = GreetingGenerator()
        mem = {"profile": {"relationship_stage": "成长期"}, "core_memories": [],
               "data_records": {"conversation_topics": [], "visit_log": [{"date": "2025-01-01"}]},
               "teaching_progress": {}}
        g = gen.generate_greeting("chagongfu", mem)
        assert len(g) > 0


class TestEmptyMemory:
    def test_structure(self):
        mem = _empty_memory("u1", "explorer")
        assert mem["user_id"] == "u1"
        assert mem["master_id"] == "explorer"
        assert mem["version"] == "1.0"
        assert isinstance(mem["core_memories"], list)
        assert isinstance(mem["data_records"], dict)
        assert isinstance(mem["teaching_progress"], dict)

    def test_memory_types(self):
        for t in MEMORY_TYPES:
            assert isinstance(t, str)
        assert "interest" in MEMORY_TYPES
        assert "preference" in MEMORY_TYPES
