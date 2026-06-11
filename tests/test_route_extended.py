"""路线规划工具扩展测试 — 距离计算、TSP、聚类"""

import pytest
from heritage_master.tools.route_planner import (
    _haversine_km, _solve_tsp_nn, _cluster_into_days, _generate_template_route
)


class TestHaversine:
    """Haversine 距离计算测试"""

    def test_same_point(self):
        """同一点距离为0"""
        assert _haversine_km(23.1, 113.3, 23.1, 113.3) == 0.0

    def test_known_distance(self):
        """北京到上海约1068km"""
        dist = _haversine_km(39.9, 116.4, 31.2, 121.5)
        assert 1000 < dist < 1200

    def test_symmetry(self):
        """距离对称性"""
        d1 = _haversine_km(23.1, 113.3, 39.9, 116.4)
        d2 = _haversine_km(39.9, 116.4, 23.1, 113.3)
        assert abs(d1 - d2) < 0.001


class TestTSP:
    """TSP 排序测试"""

    def _make_matrix(self, coords):
        """从坐标列表构建距离矩阵"""
        n = len(coords)
        matrix = [[None]*n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i][j] = {"distance_km": 0, "duration_min": 0, "source": "self"}
                else:
                    km = _haversine_km(coords[i][0], coords[i][1], coords[j][0], coords[j][1])
                    matrix[i][j] = {"distance_km": km, "duration_min": km*12, "source": "haversine"}
        return matrix

    def test_single_point(self):
        """单点排序"""
        matrix = [[{"distance_km": 0, "duration_min": 0, "source": "self"}]]
        order = _solve_tsp_nn(matrix, 0)
        assert order == [0]

    def test_two_points(self):
        """两点排序"""
        coords = [(23.1, 113.3), (23.2, 113.4)]
        matrix = self._make_matrix(coords)
        order = _solve_tsp_nn(matrix, 0)
        assert len(order) == 2
        assert set(order) == {0, 1}

    def test_three_points(self):
        """三点排序应访问所有点"""
        coords = [(23.1, 113.3), (23.5, 113.5), (23.3, 113.4)]
        matrix = self._make_matrix(coords)
        order = _solve_tsp_nn(matrix, 0)
        assert len(order) == 3
        assert set(order) == {0, 1, 2}

    def test_start_point_first(self):
        """起点应在第一位"""
        coords = [(23.1, 113.3), (23.5, 113.5), (23.3, 113.4)]
        matrix = self._make_matrix(coords)
        order = _solve_tsp_nn(matrix, 1)
        assert order[0] == 1


class TestClusterIntoDays:
    """分天聚类测试"""

    def test_single_day(self):
        """单天聚类"""
        clusters = _cluster_into_days([0, 1, 2, 3], 1)
        assert len(clusters) == 1
        assert len(clusters[0]) == 4

    def test_two_days(self):
        """两天聚类"""
        clusters = _cluster_into_days([0, 1, 2, 3, 4, 5], 2)
        assert len(clusters) == 2
        total = sum(len(c) for c in clusters)
        assert total == 6

    def test_empty_input(self):
        """空输入"""
        clusters = _cluster_into_days([], 3)
        assert len(clusters) == 3
        assert all(len(c) == 0 for c in clusters)

    def test_fewer_items_than_days(self):
        """景点少于天数"""
        clusters = _cluster_into_days([0, 1], 5)
        assert len(clusters) == 5


class TestTemplateRoute:
    """模板路线测试"""

    def test_guangzhou_route(self):
        """广州路线应包含具体场馆"""
        result = _generate_template_route("广州", 1)
        assert "广州" in result
        assert "Day 1" in result

    def test_unknown_city_fallback(self):
        """未知城市应有通用建议"""
        result = _generate_template_route("某某市", 2)
        assert "某某市" in result
        assert "Day 1" in result
        assert "Day 2" in result
