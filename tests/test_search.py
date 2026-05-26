"""非遗搜索工具测试"""

import pytest
from heritage_master.data.crawler import search_heritage_data, _get_builtin_data


def test_builtin_data_count():
    """测试内置数据数量"""
    data = _get_builtin_data()
    assert len(data) >= 30, f"内置数据应至少30条，实际 {len(data)}"


def test_builtin_data_fields():
    """测试内置数据字段完整性"""
    data = _get_builtin_data()
    required_fields = ["name", "category", "region", "description"]
    for item in data:
        for field in required_fields:
            assert field in item, f"项目 {item.get('name')} 缺少字段 {field}"
            assert item[field], f"项目 {item.get('name')} 的字段 {field} 为空"


def test_builtin_data_has_guangdong():
    """测试内置数据包含广东非遗"""
    data = _get_builtin_data()
    gd_items = [item for item in data if "广东" in item.get("region", "")]
    assert len(gd_items) >= 5, f"广东非遗数据不足，实际 {len(gd_items)}"


def test_builtin_data_has_unesco():
    """测试内置数据包含UNESCO项目"""
    data = _get_builtin_data()
    unesco_items = [item for item in data if item.get("unesco")]
    assert len(unesco_items) >= 10, f"UNESCO项目数据不足，实际 {len(unesco_items)}"


@pytest.mark.asyncio
async def test_search_by_name():
    """按名称搜索"""
    results = await search_heritage_data(query="昆曲")
    assert len(results) >= 1
    assert any("昆曲" in item["name"] for item in results)


@pytest.mark.asyncio
async def test_search_by_category():
    """按类别搜索"""
    results = await search_heritage_data(category="传统戏剧")
    assert len(results) >= 3


@pytest.mark.asyncio
async def test_search_by_region():
    """按地区搜索"""
    results = await search_heritage_data(region="广东")
    assert len(results) >= 3


@pytest.mark.asyncio
async def test_search_combined():
    """组合条件搜索"""
    results = await search_heritage_data(category="传统技艺", region="广东")
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_search_no_result():
    """搜索不存在的项目"""
    results = await search_heritage_data(query="不存在的非遗项目xyz")
    assert len(results) == 0
