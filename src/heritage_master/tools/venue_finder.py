from __future__ import annotations

"""
场馆查找工具 - 基于高德地图 API 查找非遗场馆
"""

import httpx

from heritage_master.config import settings
from heritage_master.tools.http_client import get_client


async def search_venues_amap(
    city: str,
    keyword: str = "非遗",
    lng: float = None,
    lat: float = None,
    radius: int = 5000,
    limit: int = 10,
) -> list[dict]:
    """
    通过高德地图 API 搜索非遗相关场馆。

    Args:
        city: 城市名，如"广州"、"北京"
        keyword: 搜索关键词
        lng: 经度（可选，用于距离排序）
        lat: 纬度（可选）
        radius: 搜索半径（米），默认5000
        limit: 返回数量

    Returns:
        场馆列表
    """
    if not settings.amap_key:
        return []

    url = "https://restapi.amap.com/v3/place/text"
    params = {
        "key": settings.amap_key,
        "keywords": keyword,
        "city": city,
        "citylimit": "true",
        "types": "风景名胜|博物馆|展览馆|文化传媒|科教文化服务",
        "offset": min(limit, 25),
        "extensions": "all",
    }

    # 如果有坐标，使用周边搜索
    if lng and lat:
        url = "https://restapi.amap.com/v3/place/around"
        params["location"] = f"{lng},{lat}"
        params["radius"] = radius

    try:
        client = get_client()
        resp = await client.get(url, params=params)
        data = resp.json()

        if data.get("status") != "1":
            return []

        venues = []
        for poi in data.get("pois", []):
            venue = {
                "id": poi.get("id", ""),
                "name": poi.get("name", ""),
                "address": poi.get("address", ""),
                "city": poi.get("cityname", ""),
                "district": poi.get("adname", ""),
                "type": poi.get("type", ""),
                "tel": poi.get("tel", ""),
                "lng": float(poi.get("location", "0,0").split(",")[0]),
                "lat": float(poi.get("location", "0,0").split(",")[1]),
                "distance": poi.get("distance", ""),
                "business_hours": "",
                "rating": "",
                "photos": [],
            }

            # 提取营业时间和评分
            biz_ext = poi.get("biz_ext", {})
            if biz_ext:
                venue["rating"] = biz_ext.get("rating", "")
                venue["business_hours"] = biz_ext.get("open_time", "")

            # 提取照片
            photos = poi.get("photos", [])
            if photos:
                venue["photos"] = [p.get("url", "") for p in photos[:3] if p.get("url")]

            venues.append(venue)

        return venues[:limit]

    except Exception as e:
        print(f"[venue_finder] 高德API调用失败: {e}")
        return []


def format_venue_list(venues: list[dict], city: str) -> str:
    """格式化场馆列表为可读文本"""
    if not venues:
        if not settings.amap_key:
            return (
                "⚠️ 未配置高德地图 API Key，无法查询实时场馆数据。\n"
                "请设置环境变量 HERITAGE_AMAP_KEY。\n"
                "申请地址：https://lbs.amap.com/dev/key/app"
            )
        return f"未在 {city} 找到相关非遗场馆。请尝试其他关键词或城市。"

    lines = [f"# {city} 非遗相关场馆（{len(venues)}个）\n"]

    for i, v in enumerate(venues, 1):
        name = v["name"]
        address = v["address"]
        district = v["district"]
        tel = v["tel"]
        distance = v["distance"]
        rating = v["rating"]
        hours = v["business_hours"]

        line = f"{i}. **{name}**"
        if rating:
            line += f"  ⭐{rating}"

        if address:
            line += f"\n   📍 {district} {address}"
        if distance:
            dist_m = int(distance)
            if dist_m >= 1000:
                line += f"  ({dist_m/1000:.1f}km)"
            else:
                line += f"  ({dist_m}m)"
        if tel:
            line += f"\n   📞 {tel}"
        if hours:
            line += f"\n   ⏰ {hours}"

        lines.append(line)

    return "\n".join(lines)


async def find_nearby_venues(
    city: str,
    keyword: str = "非遗",
    lng: float = None,
    lat: float = None,
    radius: int = 5000,
    limit: int = 10,
) -> str:
    """
    查找附近的非遗场馆/体验点。

    Args:
        city: 城市名
        keyword: 搜索关键词，默认"非遗"
        lng: 经度（可选）
        lat: 纬度（可选）
        radius: 搜索半径（米）
        limit: 返回数量

    Returns:
        格式化的场馆列表
    """
    venues = await search_venues_amap(
        city=city, keyword=keyword, lng=lng, lat=lat, radius=radius, limit=limit
    )
    return format_venue_list(venues, city)


async def get_venue_detail(poi_id: str) -> dict:
    """
    获取单个场馆的详细信息（高德 POI 详情 API）。

    Args:
        poi_id: 高德 POI ID

    Returns:
        场馆详细信息
    """
    if not settings.amap_key or not poi_id:
        return {}

    url = "https://restapi.amap.com/v3/place/detail"
    params = {
        "key": settings.amap_key,
        "id": poi_id,
        "extensions": "all",
    }

    try:
        client = get_client()
        resp = await client.get(url, params=params)
        data = resp.json()

        if data.get("status") != "1":
            return {}

        pois = data.get("pois", [])
        if not pois:
            return {}

        poi = pois[0]
        detail = {
            "id": poi.get("id", ""),
            "name": poi.get("name", ""),
            "address": poi.get("address", ""),
            "city": poi.get("cityname", ""),
            "district": poi.get("adname", ""),
            "type": poi.get("type", ""),
            "typecode": poi.get("typecode", ""),
            "tel": poi.get("tel", ""),
            "lng": float(poi.get("location", "0,0").split(",")[0]),
            "lat": float(poi.get("location", "0,0").split(",")[1]),
            "website": poi.get("website", ""),
            "pname": poi.get("pname", ""),
            "business_hours": "",
            "rating": "",
            "cost": "",
            "photos": [],
            "tags": [],
        }

        # 营业时间、评分、人均消费
        biz_ext = poi.get("biz_ext", {})
        if biz_ext:
            detail["rating"] = biz_ext.get("rating", "")
            detail["business_hours"] = biz_ext.get("open_time", "")
            detail["cost"] = biz_ext.get("cost", "")

        # 照片
        photos = poi.get("photos", [])
        if photos:
            detail["photos"] = [
                {"title": p.get("title", ""), "url": p.get("url", "")}
                for p in photos[:10]
                if p.get("url")
            ]

        # 标签
        if poi.get("tag"):
            detail["tags"] = [t.strip() for t in poi["tag"].split(";") if t.strip()]

            return detail

    except Exception as e:
        print(f"[venue_finder] 获取场馆详情失败: {e}")
        return {}
