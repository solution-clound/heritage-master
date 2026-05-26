"""场馆查找工具测试"""

import pytest
from heritage_master.tools.venue_finder import format_venue_list


def test_format_empty_venues():
    """测试空场馆列表格式化"""
    result = format_venue_list([], "广州")
    assert "未找到" in result or "未配置" in result or "未在" in result


def test_format_venue_list():
    """测试场馆列表格式化"""
    venues = [
        {
            "name": "测试场馆",
            "address": "测试地址",
            "city": "广州",
            "district": "荔湾区",
            "tel": "020-12345678",
            "lng": 113.26,
            "lat": 23.13,
            "distance": "1500",
            "business_hours": "9:00-17:00",
            "rating": "4.5",
        }
    ]
    result = format_venue_list(venues, "广州")
    assert "测试场馆" in result
    assert "荔湾区" in result
    assert "020-12345678" in result
    assert "1.5km" in result
