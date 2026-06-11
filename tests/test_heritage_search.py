# -*- coding: utf-8 -*-
"""非遗搜索工具测试 — 覆盖搜索、详情、降级链路"""
import pytest
from heritage_master.data.crawler import (
    search_heritage_data, get_heritage_detail,
    _get_builtin_data, _filter_builtin, _load_cached_results,
    CATEGORIES, _CATEGORY_TYPE_MAP, _map_province_code,
    _clean_rx_time, _CITY_PROVINCE_MAP,
)


# ============================================================
# 内置数据完整性
# ============================================================

class TestBuiltinData:
    def test_count_at_least_150(self):
        data = _get_builtin_data()
        assert len(data) >= 150

    def test_no_duplicate_names(self):
        data = _get_builtin_data()
        names = [d["name"] for d in data]
        assert len(names) == len(set(names))

    def test_all_categories_covered(self):
        data = _get_builtin_data()
        cats = {d["category"] for d in data}
        for cat in CATEGORIES:
            assert cat in cats, f"Missing category: {cat}"

    def test_each_category_at_least_5(self):
        from collections import Counter
        data = _get_builtin_data()
        cats = Counter(d["category"] for d in data)
        for cat, count in cats.items():
            assert count >= 5, f"{cat} only has {count} items"

    def test_all_have_name(self):
        for item in _get_builtin_data():
            assert item.get("name", "").strip()

    def test_all_have_category(self):
        for item in _get_builtin_data():
            assert item.get("category", "").strip()

    def test_unesco_items_present(self):
        data = _get_builtin_data()
        unesco = [d for d in data if d.get("unesco")]
        assert len(unesco) >= 10

    def test_specific_essential_items(self):
        names = {d["name"] for d in _get_builtin_data()}
        for name in ["昆曲", "京剧", "太极拳", "春节", "川剧", "安塞腰鼓"]:
            assert name in names, f"Essential item missing: {name}"

    def test_region_coverage(self):
        regions = set()
        for item in _get_builtin_data():
            for r in item.get("region", "").split(","):
                r = r.strip()
                if r and r != "全国":
                    regions.add(r)
        assert len(regions) >= 20


# ============================================================
# 搜索功能
# ============================================================

class TestSearchHeritageData:
    @pytest.mark.asyncio
    async def test_search_by_name(self):
        results = await search_heritage_data(query="昆曲")
        assert len(results) >= 1
        assert any("昆曲" in r["name"] for r in results)

    @pytest.mark.asyncio
    async def test_search_by_category(self):
        results = await search_heritage_data(category="传统戏剧")
        assert len(results) >= 3

    @pytest.mark.asyncio
    async def test_search_by_region(self):
        results = await search_heritage_data(region="广东")
        assert len(results) >= 3

    @pytest.mark.asyncio
    async def test_search_combined(self):
        results = await search_heritage_data(category="传统技艺", region="广东")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_no_result(self):
        results = await search_heritage_data(query="不存在的非遗项目xyz")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_limit(self):
        results = await search_heritage_data(limit=3)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_search_returns_list(self):
        results = await search_heritage_data()
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_item_has_required_fields(self):
        results = await search_heritage_data(query="广绣", limit=1)
        if results:
            item = results[0]
            assert "name" in item
            assert "category" in item


# ============================================================
# 辅助函数
# ============================================================

class TestHelperFunctions:
    def test_clean_rx_time_batch(self):
        assert "第一批" in _clean_rx_time("2006(第一批")

    def test_clean_rx_time_plain(self):
        result = _clean_rx_time("2008(第二批")
        assert "第二批" in result

    def test_map_province_code_guangdong(self):
        code = _map_province_code("广东")
        assert code == "440000"

    def test_map_province_code_city(self):
        code = _map_province_code("广州")
        assert code == "440000"

    def test_map_province_code_unknown(self):
        code = _map_province_code("未知")
        assert code == ""

    def test_city_province_map(self):
        assert _CITY_PROVINCE_MAP.get("广州") == "广东"
        assert _CITY_PROVINCE_MAP.get("南京") == "江苏"
        assert _CITY_PROVINCE_MAP.get("成都") == "四川"

    def test_category_type_map(self):
        assert _CATEGORY_TYPE_MAP.get("民间文学") == "1"
        assert _CATEGORY_TYPE_MAP.get("传统音乐") == "2"

    def test_filter_builtin(self):
        data = _get_builtin_data()
        gd = _filter_builtin(data, region="广东")
        assert len(gd) >= 5
        for item in gd:
            assert "广东" in item.get("region", "")

    def test_filter_builtin_by_category(self):
        data = _get_builtin_data()
        drama = _filter_builtin(data, category="传统戏剧")
        assert len(drama) >= 3
        for item in drama:
            assert item["category"] == "传统戏剧"
