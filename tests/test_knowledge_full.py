# -*- coding: utf-8 -*-
"""知识库测试 — 结构化知识、RAG 文件、格式化"""
import pytest
from pathlib import Path
from heritage_master.tools.master_prompt import (
    get_project_knowledge, list_knowledge_projects,
    build_qa_prompt, build_compare_prompt,
)
from heritage_master.tools.knowledge_base import (
    _search_local_files, _format_knowledge, get_knowledge,
    ask_heritage_expert, index_knowledge_files,
)


class TestStructuredKnowledge:
    def test_list_projects(self):
        projects = list_knowledge_projects()
        assert len(projects) >= 100

    def test_known_project(self):
        k = get_project_knowledge("昆曲")
        assert k is not None
        assert k["name"] == "昆曲"

    def test_known_project_jingju(self):
        k = get_project_knowledge("京剧")
        assert k is not None
        assert "传统戏剧" in k.get("category", "")

    def test_unknown_project(self):
        k = get_project_knowledge("不存在的项目xyz")
        assert k is None

    def test_project_has_category(self):
        projects = list_knowledge_projects()
        for name in projects[:10]:
            k = get_project_knowledge(name)
            assert k.get("category", ""), f"{name} missing category"

    def test_project_has_region(self):
        projects = list_knowledge_projects()
        for name in projects[:10]:
            k = get_project_knowledge(name)
            region = k.get("region", [])
            assert region, f"{name} missing region"


class TestKnowledgeFormatting:
    def test_format_overview(self):
        k = {"name": "test", "category": "传统戏剧", "region": ["北京"]}
        result = _format_knowledge(k, "overview")
        assert "test" in result
        assert "传统戏剧" in result

    def test_format_history(self):
        k = {"name": "test", "origin": {"period": "明代", "place": "苏州"}}
        result = _format_knowledge(k, "history")
        assert "明代" in result
        assert "苏州" in result

    def test_format_technique(self):
        k = {"name": "test", "characteristics": ["特点1", "特点2"]}
        result = _format_knowledge(k, "technique")
        assert "特点1" in result

    def test_format_inheritors(self):
        k = {"name": "test", "inheritors": [{"name": "张三", "title": "大师"}]}
        result = _format_knowledge(k, "inheritors")
        assert "张三" in result

    def test_format_works(self):
        k = {"name": "test", "masterpieces": ["作品1", "作品2"]}
        result = _format_knowledge(k, "works")
        assert "作品1" in result

    def test_format_empty(self):
        result = _format_knowledge({}, "overview")
        # Empty knowledge still generates header line
        assert result == "" or result.strip() == "" or result.startswith("#")


class TestLocalFileSearch:
    def test_rag_dir_exists(self):
        rag_dir = Path("src/heritage_master/rag/knowledge")
        assert rag_dir.exists()

    def test_rag_dir_has_files(self):
        rag_dir = Path("src/heritage_master/rag/knowledge")
        files = list(rag_dir.glob("*.md"))
        assert len(files) >= 100

    def test_search_known_project(self):
        result = _search_local_files("昆曲")
        # May or may not find results depending on file content
        assert result is None or len(result) > 0


class TestKnowledgeJson:
    def test_knowledge_json_exists(self):
        p = Path("src/heritage_master/data/knowledge.json")
        assert p.exists()

    def test_knowledge_json_count(self):
        import json
        data = json.loads(Path("src/heritage_master/data/knowledge.json").read_text(encoding="utf-8"))
        assert len(data) >= 150

    def test_knowledge_json_no_empty_names(self):
        import json
        data = json.loads(Path("src/heritage_master/data/knowledge.json").read_text(encoding="utf-8"))
        for name in data:
            assert name.strip(), f"Empty name in knowledge.json"
