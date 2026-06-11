"""扩充内置数据完整性测试"""

import pytest
from collections import Counter
from heritage_master.data.crawler import _get_builtin_data


class TestExpandedBuiltinData:
    """验证扩充后的内置数据质量"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.data = _get_builtin_data()
        self.names = [item["name"] for item in self.data]

    def test_total_count(self):
        assert len(self.data) >= 150

    def test_no_duplicates(self):
        dupes = [n for n, c in Counter(self.names).items() if c > 1]
        assert dupes == []

    def test_all_categories_covered(self):
        cats = set(item["category"] for item in self.data)
        expected = {"民间文学", "传统音乐", "传统舞蹈", "传统戏剧", "曲艺",
                    "传统体育、游艺与杂技", "传统美术", "传统技艺", "传统医药", "民俗"}
        missing = expected - cats
        assert not missing

    def test_category_balance(self):
        cats = Counter(item["category"] for item in self.data)
        for cat, count in cats.items():
            assert count >= 5

    def test_all_items_have_name(self):
        for item in self.data:
            assert item.get("name", "").strip()

    def test_all_items_have_category(self):
        for item in self.data:
            assert item.get("category", "").strip()

    def test_region_coverage(self):
        regions = set()
        for item in self.data:
            for r in item.get("region", "").split(","):
                r = r.strip()
                if r and r != "全国":
                    regions.add(r)
        assert len(regions) >= 20

    def test_unesco_items_present(self):
        unesco = [item for item in self.data if item.get("unesco")]
        assert len(unesco) >= 10

    def test_specific_items_exist(self):
        essential = ["昆曲", "京剧", "太极拳", "春节", "川剧", "安塞腰鼓"]
        for name in essential:
            assert name in self.names
