"""知识库工具测试"""

import pytest
from heritage_master.tools.knowledge_base import (
    _search_local_files,
    _format_knowledge,
    get_knowledge,
    ask_heritage_expert,
    KNOWLEDGE_DIR,
)


def test_knowledge_dir_exists():
    """测试知识库目录存在"""
    assert KNOWLEDGE_DIR.exists(), f"知识库目录不存在: {KNOWLEDGE_DIR}"


def test_knowledge_dir_has_files():
    """测试知识库目录包含 Markdown 文件"""
    md_files = list(KNOWLEDGE_DIR.glob("**/*.md"))
    assert len(md_files) >= 1, "知识库目录中没有 Markdown 文件"


def test_search_local_files_found():
    """测试本地文件搜索能找到已知项目"""
    result = _search_local_files("昆曲")
    assert result is not None
    assert "昆曲" in result


def test_search_local_files_not_found():
    """测试本地文件搜索对不存在的项目返回 None"""
    result = _search_local_files("不存在的非遗项目xyz")
    assert result is None


def test_format_knowledge_overview():
    """测试概述格式化"""
    k = {
        "name": "测试项目",
        "description": "这是一个测试项目",
        "category": "传统技艺",
        "region": ["北京", "上海"],
    }
    result = _format_knowledge(k, "overview")
    assert "测试项目" in result
    assert "传统技艺" in result
    assert "北京" in result


def test_format_knowledge_history():
    """测试历史格式化"""
    k = {
        "name": "测试项目",
        "origin": {
            "period": "明代",
            "place": "北京",
            "founder": "张三",
        },
    }
    result = _format_knowledge(k, "history")
    assert "明代" in result
    assert "北京" in result
    assert "张三" in result


def test_format_knowledge_technique():
    """测试技艺特点格式化"""
    k = {
        "name": "测试项目",
        "characteristics": ["特点一", "特点二", "特点三"],
    }
    result = _format_knowledge(k, "technique")
    assert "特点一" in result
    assert "特点二" in result


def test_format_knowledge_inheritors():
    """测试传承人格式化"""
    k = {
        "name": "测试项目",
        "inheritors": [
            {"name": "李四", "title": "国家级传承人", "specialty": "刺绣"},
        ],
    }
    result = _format_knowledge(k, "inheritors")
    assert "李四" in result
    assert "国家级传承人" in result


def test_format_knowledge_works():
    """测试代表作品格式化"""
    k = {
        "name": "测试项目",
        "masterpieces": ["作品一", "作品二"],
        "related": ["相关项目"],
    }
    result = _format_knowledge(k, "works")
    assert "作品一" in result
    assert "相关项目" in result


def test_format_knowledge_empty():
    """测试空知识返回空字符串"""
    k = {"name": "测试项目"}
    result = _format_knowledge(k, "history")
    assert result == ""


@pytest.mark.asyncio
async def test_get_knowledge_known_project():
    """测试获取已知项目的知识"""
    # 昆曲在知识库中应该有数据
    result = await get_knowledge("昆曲", "overview")
    assert "昆曲" in result
    # 应该包含一些有用的信息
    assert len(result) > 50


@pytest.mark.asyncio
async def test_get_knowledge_unknown_project():
    """测试获取未知项目返回提示信息"""
    result = await get_knowledge("不存在的项目xyz", "overview")
    assert "暂未找到" in result


@pytest.mark.asyncio
async def test_ask_heritage_expert():
    """测试知识问答"""
    result = await ask_heritage_expert("什么是昆曲？")
    assert isinstance(result, str)
    assert len(result) > 20
