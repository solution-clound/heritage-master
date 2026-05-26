"""路线规划工具测试"""

import pytest
from heritage_master.tools.route_planner import _generate_template_route


def test_template_route_basic():
    """测试基本模板路线生成"""
    result = _generate_template_route("广州", 1)
    assert "广州" in result
    assert "Day 1" in result
    assert "非遗" in result


def test_template_route_multi_day():
    """测试多日路线"""
    result = _generate_template_route("北京", 3)
    assert "Day 1" in result
    assert "Day 2" in result
    assert "Day 3" in result


def test_template_route_known_city():
    """测试已知城市的模板路线"""
    result = _generate_template_route("广州", 1)
    # 广州应该有具体推荐
    assert any(name in result for name in ["粤剧", "陈家祠", "永庆坊", "文化馆"])


def test_template_route_unknown_city():
    """测试未知城市的模板路线"""
    result = _generate_template_route("小城市", 1)
    assert "小城市" in result
    assert "Day 1" in result
    # 应该有通用建议
    assert "博物馆" in result or "文化馆" in result


def test_template_route_with_interests():
    """测试带兴趣的模板路线"""
    result = _generate_template_route("成都", 1, ["传统戏剧", "传统技艺"])
    assert "成都" in result
    assert "传统戏剧" in result or "传统技艺" in result


def test_template_route_multiple_cities():
    """测试多个城市的模板路线"""
    cities = ["广州", "北京", "上海", "杭州", "成都"]
    for city in cities:
        result = _generate_template_route(city, 1)
        assert city in result
        assert "Day 1" in result


@pytest.mark.asyncio
async def test_plan_heritage_route():
    """测试路线规划（可能使用模板降级）"""
    from heritage_master.tools.route_planner import plan_heritage_route
    result = await plan_heritage_route("广州", 1)
    assert isinstance(result, str)
    assert len(result) > 50
    assert "广州" in result
