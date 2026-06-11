"""修行系统测试

纯逻辑测试不需要数据库，集成测试需要。
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from heritage_master.tools.cultivation import (
    STAGES,
    STAGE_REQUIREMENTS,
    _generate_comment,
    _evaluate_score,
    _generate_practice_with_llm,
)


# ─── 阶段定义测试（纯逻辑，无 DB）────────────────────────

def test_stages_order():
    """测试阶段顺序正确"""
    assert STAGES == ["入门期", "成长期", "精进期", "传承期"]


def test_stage_requirements_have_min_avg_score():
    """测试所有阶段都有平均分门槛"""
    for stage, req in STAGE_REQUIREMENTS.items():
        assert "min_avg_score" in req, f"{stage} 缺少 min_avg_score"
        assert isinstance(req["min_avg_score"], int), f"{stage} min_avg_score 应为整数"


def test_stage_requirements_progression():
    """测试阶段要求递增"""
    reqs = [STAGE_REQUIREMENTS[s] for s in STAGES if STAGE_REQUIREMENTS[s].get("next")]
    for i in range(len(reqs) - 1):
        assert reqs[i]["min_practice_days"] <= reqs[i + 1]["min_practice_days"]
        assert reqs[i]["min_questions"] <= reqs[i + 1]["min_questions"]


def test_stage_requirements_final_stage():
    """测试传承期没有下一阶段"""
    assert STAGE_REQUIREMENTS["传承期"]["next"] is None


def test_stage_requirements_score_thresholds():
    """测试分数门槛合理"""
    assert STAGE_REQUIREMENTS["入门期"]["min_avg_score"] == 60
    assert STAGE_REQUIREMENTS["成长期"]["min_avg_score"] == 65
    assert STAGE_REQUIREMENTS["精进期"]["min_avg_score"] == 70
    assert STAGE_REQUIREMENTS["传承期"]["min_avg_score"] == 0  # 无门槛


# ─── LLM 点评测试 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_comment_fallback_to_template():
    """测试无 LLM 时降级到模板点评"""
    comment = await _generate_comment("chagongfu", "今天练习了泡茶", llm_func=None)
    assert isinstance(comment, str)
    assert len(comment) > 0


@pytest.mark.asyncio
async def test_generate_comment_with_llm():
    """测试有 LLM 时使用 LLM 点评"""
    mock_llm = AsyncMock(return_value="嗯，你今天泡的这杯茶，水温控制得不错。继续用心感受。")
    comment = await _generate_comment("chagongfu", "今天练习了泡茶，感觉水温很重要", llm_func=mock_llm)
    assert "水温" in comment or "泡茶" in comment
    mock_llm.assert_called_once()


@pytest.mark.asyncio
async def test_generate_comment_llm_failure_fallback():
    """测试 LLM 失败时降级到模板"""
    mock_llm = AsyncMock(side_effect=Exception("API error"))
    comment = await _generate_comment("chagongfu", "今天练习了泡茶", llm_func=mock_llm)
    assert isinstance(comment, str)
    assert len(comment) > 0


@pytest.mark.asyncio
async def test_generate_comment_unknown_master():
    """测试未知大师的模板点评"""
    comment = await _generate_comment("unknown_master", "练习内容", llm_func=None)
    assert comment == "继续努力。"


@pytest.mark.asyncio
async def test_generate_comment_wushishizi():
    """测试醒狮大师的模板点评"""
    comment = await _generate_comment("wushishizi", "今天练了马步", llm_func=None)
    assert isinstance(comment, str)
    assert len(comment) > 0


# ─── 评分测试 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_evaluate_score_rule_fallback():
    """测试规则评分（无 LLM）"""
    # 短内容
    score_short = await _evaluate_score("今天练习了", "", llm_func=None)
    assert 60 <= score_short <= 70

    # 长内容 + 深度关键词
    long_text = "今天练习了泡茶，感受了水温对茶味的影响。通过观察和思考，发现80度和100度泡出来的茶完全不同。这让我理解了一个道理：差一点就差很多。" * 2
    score_deep = await _evaluate_score(long_text, "", llm_func=None)
    assert score_deep > score_short


@pytest.mark.asyncio
async def test_evaluate_score_with_llm():
    """测试 LLM 评分"""
    mock_llm = AsyncMock(return_value="85")
    long_content = "今天练习了泡茶，感受了水温对茶味的影响，发现细节很重要。"
    score = await _evaluate_score(long_content, "chagongfu", llm_func=mock_llm)
    assert score == 85


@pytest.mark.asyncio
async def test_evaluate_score_llm_returns_garbage():
    """测试 LLM 返回无效内容时降级到规则"""
    mock_llm = AsyncMock(return_value="这不是一个数字")
    score = await _evaluate_score("今天练习了泡茶，感受很多", "chagongfu", llm_func=mock_llm)
    assert 60 <= score <= 100  # 应该降级到规则评分


@pytest.mark.asyncio
async def test_evaluate_score_max_100():
    """测试评分不超过 100"""
    score = await _evaluate_score("x" * 500, "", llm_func=None)
    assert score <= 100


@pytest.mark.asyncio
async def test_evaluate_score_short_content_no_llm():
    """测试短内容不触发 LLM（< 20 字符）"""
    mock_llm = AsyncMock(return_value="90")
    score = await _evaluate_score("短", "", llm_func=mock_llm)
    # 短内容不走 LLM，应该用规则评分
    mock_llm.assert_not_called()
    assert 60 <= score <= 70


# ─── LLM 功课生成测试 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_practice_with_llm_success():
    """测试 LLM 功课生成成功"""
    mock_llm = AsyncMock(return_value="今天试着用不同水温泡同一款茶，记录口感差异。")
    content = await _generate_practice_with_llm("chagongfu", "入门期", mock_llm)
    assert content is not None
    assert "水温" in content or "茶" in content


@pytest.mark.asyncio
async def test_generate_practice_with_llm_failure():
    """测试 LLM 功课生成失败返回 None"""
    mock_llm = AsyncMock(side_effect=Exception("API error"))
    content = await _generate_practice_with_llm("chagongfu", "入门期", mock_llm)
    assert content is None


@pytest.mark.asyncio
async def test_generate_practice_with_llm_too_short():
    """测试 LLM 返回过短内容时返回 None"""
    mock_llm = AsyncMock(return_value="好")
    content = await _generate_practice_with_llm("chagongfu", "入门期", mock_llm)
    assert content is None  # 太短，应返回 None 降级到模板
