# -*- coding: utf-8 -*-
"""路线规划工具测试 — Haversine、TSP、聚类、模板降级"""
import pytest
from heritage_master.tools.route_planner import (
    _haversine_km, _solve_tsp_nn, _cluster_into_days,
    _generate_template_route, plan_heritage_route,
)


class TestHaversine:
    def test_same_point(self):
        assert _haversine_km(23.1, 113.3, 23.1, 113.3) == 0.0

    def test_known_distance_beijing_shanghai(self):
        dist = _haversine_km(39.9, 116.4, 31.2, 121.5)
        assert 1000 < dist < 1200

    def test_symmetry(self):
        d1 = _haversine_km(23.1, 113.3, 39.9, 116.4)
        d2 = _haversine_km(39.9, 116.4, 23.1, 113.3)
        assert abs(d1 - d2) < 0.001

    def test_short_distance(self):
        # Guangzhou city center to Baiyun airport ~28km
        dist = _haversine_km(23.13, 113.26, 23.39, 113.30)
        assert 20 < dist < 40

    def test_zero_distance_same_coords(self):
        assert _haversine_km(0, 0, 0, 0) == 0.0

    def test_antipodal_points(self):
        # Opposite sides of Earth ~20000km
        dist = _haversine_km(0, 0, 0, 180)
        assert 20000 < dist < 20100


class TestTSP:
    def _make_matrix(self, coords):
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
        matrix = [[{"distance_km": 0, "duration_min": 0, "source": "self"}]]
        assert _solve_tsp_nn(matrix, 0) == [0]

    def test_two_points(self):
        coords = [(23.1, 113.3), (23.2, 113.4)]
        order = _solve_tsp_nn(self._make_matrix(coords), 0)
        assert len(order) == 2
        assert set(order) == {0, 1}

    def test_three_points_visits_all(self):
        coords = [(23.1, 113.3), (23.5, 113.5), (23.3, 113.4)]
        order = _solve_tsp_nn(self._make_matrix(coords), 0)
        assert len(order) == 3
        assert set(order) == {0, 1, 2}

    def test_start_point_first(self):
        coords = [(23.1, 113.3), (23.5, 113.5), (23.3, 113.4)]
        order = _solve_tsp_nn(self._make_matrix(coords), 1)
        assert order[0] == 1

    def test_five_points(self):
        coords = [(23.1, 113.3), (23.2, 113.4), (23.3, 113.5), (23.4, 113.6), (23.5, 113.7)]
        order = _solve_tsp_nn(self._make_matrix(coords), 0)
        assert len(order) == 5
        assert len(set(order)) == 5


class TestClusterIntoDays:
    def test_single_day(self):
        clusters = _cluster_into_days([0, 1, 2, 3], 1)
        assert len(clusters) == 1
        assert sum(len(c) for c in clusters) == 4

    def test_two_days(self):
        clusters = _cluster_into_days([0, 1, 2, 3, 4, 5], 2)
        assert len(clusters) == 2
        assert sum(len(c) for c in clusters) == 6

    def test_empty_input(self):
        clusters = _cluster_into_days([], 3)
        assert len(clusters) == 3
        assert all(len(c) == 0 for c in clusters)

    def test_fewer_items_than_days(self):
        clusters = _cluster_into_days([0, 1], 5)
        assert len(clusters) == 5

    def test_three_days(self):
        clusters = _cluster_into_days(list(range(9)), 3)
        assert len(clusters) == 3
        assert sum(len(c) for c in clusters) == 9


class TestTemplateRoute:
    def test_guangzhou(self):
        result = _generate_template_route("广州", 1)
        assert "广州" in result
        assert "Day 1" in result

    def test_beijing(self):
        result = _generate_template_route("北京", 2)
        assert "Day 1" in result
        assert "Day 2" in result

    def test_unknown_city_fallback(self):
        result = _generate_template_route("某某市", 1)
        assert "某某市" in result
        assert "Day 1" in result

    def test_with_interests(self):
        result = _generate_template_route("成都", 1, ["传统戏剧", "传统技艺"])
        assert "成都" in result

    def test_multiple_cities(self):
        for city in ["广州", "北京", "上海", "杭州", "成都", "苏州", "西安"]:
            result = _generate_template_route(city, 1)
            assert city in result
            assert "Day 1" in result

    def test_multi_day(self):
        result = _generate_template_route("广州", 3)
        assert "Day 1" in result
        assert "Day 2" in result
        assert "Day 3" in result


class TestPlanHeritageRoute:
    @pytest.mark.asyncio
    async def test_returns_dict(self):
        result = await plan_heritage_route("广州", 1)
        assert isinstance(result, dict)
        assert "itinerary" in result

    @pytest.mark.asyncio
    async def test_itinerary_has_content(self):
        result = await plan_heritage_route("广州", 1)
        assert len(result["itinerary"]) > 50

    @pytest.mark.asyncio
    async def test_itinerary_contains_city(self):
        result = await plan_heritage_route("广州", 1)
        assert "广州" in result["itinerary"]
