"""非遗大师人设系统测试"""

import pytest
from heritage_master.tools.master_prompt import (
    MASTER_SYSTEM_PROMPT,
    build_qa_prompt,
    build_compare_prompt,
    get_project_knowledge,
    list_knowledge_projects,
    list_masters,
    get_master,
    get_master_prompt,
    _load_knowledge,
    MASTERS,
)


def test_system_prompt_not_empty():
    """测试系统提示词不为空"""
    assert len(MASTER_SYSTEM_PROMPT) > 100


def test_system_prompt_contains_style():
    """测试系统提示词包含风格定义"""
    assert "比喻" in MASTER_SYSTEM_PROMPT or "故事" in MASTER_SYSTEM_PROMPT


def test_masters_registry():
    """测试大师注册表"""
    assert len(MASTERS) >= 2
    assert "chagongfu" in MASTERS
    assert "wushishizi" in MASTERS


def test_list_masters():
    """测试列出大师"""
    masters = list_masters()
    assert len(masters) >= 2
    for m in masters:
        assert "id" in m
        assert "name" in m
        assert "title" in m
        assert "avatar" in m
        assert "expertise" in m
        assert "intro" in m
        # 不应包含 system_prompt
        assert "system_prompt" not in m


def test_get_master():
    """测试获取指定大师"""
    master = get_master("chagongfu")
    assert master is not None
    assert master["name"] == "叶汉钟"
    assert "system_prompt" in master

    # 不存在的大师
    assert get_master("nonexistent") is None


def test_get_master_prompt():
    """测试获取大师 prompt"""
    prompt = get_master_prompt("chagongfu")
    assert len(prompt) > 100
    assert "叶汉钟" in prompt or "潮州工夫茶" in prompt

    # 不存在的大师应返回默认
    default_prompt = get_master_prompt("nonexistent")
    assert len(default_prompt) > 100


def test_masters_have_distinct_prompts():
    """测试不同大师有不同 prompt"""
    prompt_a = get_master_prompt("chagongfu")
    prompt_b = get_master_prompt("wushishizi")
    assert prompt_a != prompt_b


def test_masters_are_real_people():
    """测试大师是真实传承人"""
    cgm = get_master("chagongfu")
    wsn = get_master("wushishizi")
    assert cgm["name"] == "叶汉钟"
    assert wsn["name"] == "黄钦添"
    assert "潮州工夫茶" in cgm["intro"]
    assert "醒狮" in wsn["intro"]


def test_masters_have_scenes():
    """测试大师有场景描述"""
    for m in list_masters():
        assert m.get("scene"), f"{m['name']} 缺少场景描述"


def test_masters_have_greetings():
    """测试大师有开场白"""
    for m in list_masters():
        assert m.get("greeting"), f"{m['name']} 缺少开场白"


def test_load_knowledge():
    """测试加载知识库"""
    knowledge = _load_knowledge()
    assert isinstance(knowledge, dict)
    assert len(knowledge) >= 10, f"知识库项目数不足: {len(knowledge)}"


def test_list_knowledge_projects():
    """测试列出知识库项目"""
    projects = list_knowledge_projects()
    assert isinstance(projects, list)
    assert len(projects) >= 10
    assert "昆曲" in projects


def test_get_project_knowledge_known():
    """测试获取已知项目知识"""
    k = get_project_knowledge("昆曲")
    assert k is not None
    assert "origin" in k or "characteristics" in k


def test_get_project_knowledge_unknown():
    """测试获取未知项目返回 None"""
    k = get_project_knowledge("不存在的项目xyz")
    assert k is None


def test_build_qa_prompt_basic():
    """测试构建基本问答 prompt"""
    messages = build_qa_prompt("什么是昆曲？")
    assert isinstance(messages, list)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "什么是昆曲" in messages[1]["content"]


def test_build_qa_prompt_with_context():
    """测试带上下文的问答 prompt"""
    context = [
        {"name": "昆曲", "category": "传统戏剧", "description": "昆曲是百戏之祖"},
    ]
    messages = build_qa_prompt("昆曲是什么？", context_items=context)
    assert len(messages) == 2
    assert "昆曲" in messages[1]["content"]
    assert "传统戏剧" in messages[1]["content"]


def test_build_qa_prompt_with_news():
    """测试带新闻的问答 prompt"""
    news = [
        {"title": "昆曲演出", "date": "2026年5月", "source": "测试"},
    ]
    messages = build_qa_prompt("昆曲有什么活动？", news=news)
    assert "昆曲演出" in messages[1]["content"]


def test_build_qa_prompt_with_master_id():
    """测试指定大师的问答 prompt"""
    messages = build_qa_prompt("什么是昆曲？", master_id="wushishizi")
    assert "黄钦添" in messages[0]["content"] or "醒狮" in messages[0]["content"]


def test_build_compare_prompt():
    """测试对比分析 prompt"""
    messages = build_compare_prompt("昆曲", "京剧")
    assert isinstance(messages, list)
    assert len(messages) == 2
    content = messages[1]["content"]
    assert "昆曲" in content
    assert "京剧" in content
    assert "对比" in content


def test_build_compare_prompt_with_data():
    """测试带数据的对比分析 prompt"""
    data_a = {"category": "传统戏剧", "description": "昆曲是百戏之祖"}
    data_b = {"category": "传统戏剧", "description": "京剧是中国国粹"}
    messages = build_compare_prompt("昆曲", "京剧", data_a, data_b)
    content = messages[1]["content"]
    assert "百戏之祖" in content
    assert "国粹" in content
