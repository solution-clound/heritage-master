from __future__ import annotations

"""
路线规划工具 - 基于非遗场馆规划主题游览路线

使用高德地图 API 规划多日行程，包含：
- Haversine 距离计算
- 高德步行导航 API 实际距离/时间
- 最近邻 TSP 排序
- 按地理位置分天
"""

import asyncio
import math

from heritage_master.tools.http_client import get_client

import httpx

from heritage_master.config import settings
from heritage_master.tools.venue_finder import search_venues_amap


# ─── 距离计算 ─────────────────────────────────────────


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine 公式计算两点间直线距离（km）"""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def _batch_amap_walking(
    venues: list[dict], pairs: list[tuple[int, int]], amap_key: str
) -> list[tuple[int, int, float, float]]:
    """批量调用高德步行导航 API，返回 [(i, j, dist_km, dur_min), ...]"""
    semaphore = asyncio.Semaphore(3)
    results = []

    async def fetch_one(client: httpx.AsyncClient, i: int, j: int):
        async with semaphore:
            origin = f"{venues[i]['lng']},{venues[i]['lat']}"
            dest = f"{venues[j]['lng']},{venues[j]['lat']}"
            url = "https://restapi.amap.com/v3/direction/walking"
            params = {"key": amap_key, "origin": origin, "destination": dest}
            resp = await client.get(url, params=params)
            data = resp.json()
            if data.get("status") == "1":
                path = data.get("data", {}).get("paths", [{}])[0]
                dist_m = int(path.get("distance", 0))
                dur_s = int(path.get("duration", 0))
                return (i, j, dist_m / 1000, dur_s / 60)
            return None

    try:
        client = get_client()
        tasks = [fetch_one(client, i, j) for i, j in pairs]
        raw = await asyncio.gather(*tasks, return_exceptions=True)
        results = [r for r in raw if r is not None and not isinstance(r, Exception)]
    except Exception:
        pass

    return results


async def _build_distance_matrix(venues: list[dict], amap_key: str = "") -> list[list[dict]]:
    """构建 NxN 距离矩阵。先用 Haversine，再用高德步行导航升级近距离对。"""
    n = len(venues)

    # Step 1: Haversine 矩阵
    matrix: list[list[dict]] = [[None] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                matrix[i][j] = {"distance_km": 0, "duration_min": 0, "source": "self"}
            else:
                km = _haversine_km(venues[i]["lat"], venues[i]["lng"], venues[j]["lat"], venues[j]["lng"])
                matrix[i][j] = {"distance_km": km, "duration_min": km * 12, "source": "haversine"}

    # Step 2: 用高德步行导航升级 < 5km 的对
    if amap_key:
        pairs = [
            (i, j)
            for i in range(n)
            for j in range(n)
            if i != j and matrix[i][j]["distance_km"] < 5.0
        ]
        pairs = pairs[:20]
        results = await _batch_amap_walking(venues, pairs, amap_key)
        for i, j, dist_km, dur_min in results:
            matrix[i][j] = {"distance_km": dist_km, "duration_min": dur_min, "source": "amap"}

    return matrix


# ─── TSP 排序 ─────────────────────────────────────────


def _solve_tsp_nn(dist_matrix: list[list[dict]], start_idx: int = 0) -> list[int]:
    """最近邻 TSP 启发式算法，返回访问顺序索引列表。"""
    n = len(dist_matrix)
    if n <= 1:
        return list(range(n))

    visited = [False] * n
    order = [start_idx]
    visited[start_idx] = True

    for _ in range(n - 1):
        current = order[-1]
        best_next = -1
        best_dist = float("inf")
        for j in range(n):
            if not visited[j] and dist_matrix[current][j]["distance_km"] < best_dist:
                best_dist = dist_matrix[current][j]["distance_km"]
                best_next = j
        order.append(best_next)
        visited[best_next] = True

    return order


# ─── 分天聚类 ─────────────────────────────────────────


def _cluster_into_days(full_order: list[int], days: int) -> list[list[int]]:
    """将 TSP 路径按天分段。"""
    n = len(full_order)
    if n == 0:
        return [[] for _ in range(days)]
    if n <= days:
        clusters = [[full_order[i]] for i in range(n)]
        while len(clusters) < days:
            clusters.append([])
        return clusters

    venues_per_day = min(4, max(2, n // days))
    clusters = []
    remaining = full_order

    for day in range(days):
        if day == days - 1:
            clusters.append(remaining)
        else:
            chunk = remaining[:venues_per_day]
            clusters.append(chunk)
            remaining = remaining[venues_per_day:]
            # 剩余太少时，合并重分
            if len(remaining) < (days - day - 1):
                clusters[-1].extend(remaining)
                remaining = []

    return clusters


# ─── 地理编码 ─────────────────────────────────────────


async def _geocode_amap(address: str, city: str, amap_key: str) -> dict | None:
    """高德地理编码，返回 {"lng": float, "lat": float} 或 None。"""
    try:
        client = get_client()
        resp = await client.get(
            "https://restapi.amap.com/v3/geocode/geo",
            params={"key": amap_key, "address": address, "city": city},
        )
        data = resp.json()
        if data.get("status") == "1" and data.get("geocodes"):
            location = data["geocodes"][0].get("location", "")
            parts = location.split(",")
            if len(parts) == 2:
                return {"lng": float(parts[0]), "lat": float(parts[1])}
    except Exception:
        pass
    return None


async def _resolve_start_point(
    start_point: str, city: str, venues: list[dict]
) -> int | None:
    """解析出发地文字为场馆索引。先匹配名称，再地理编码找最近场馆。"""
    if not start_point:
        return None

    # 名称匹配
    for i, v in enumerate(venues):
        if start_point in v["name"]:
            return i

    # 地理编码
    amap_key = settings.amap_key
    if amap_key:
        coords = await _geocode_amap(start_point, city, amap_key)
        if coords:
            best_idx = 0
            best_dist = float("inf")
            for i, v in enumerate(venues):
                d = _haversine_km(coords["lat"], coords["lng"], v["lat"], v["lng"])
                if d < best_dist:
                    best_dist = d
                    best_idx = i
            return best_idx

    return None


# ─── 主函数 ───────────────────────────────────────────


async def plan_heritage_route(
    city: str,
    days: int = 1,
    interests: list[str] = None,
    start_point: str = None,
) -> dict:
    """
    规划非遗主题游览路线。

    Args:
        city: 城市名
        days: 游玩天数（1-7）
        interests: 感兴趣的非遗类别列表
        start_point: 出发地点

    Returns:
        {"itinerary": str, "route_data": {"venues": [...], "days": [...]}}
    """
    # 1. 搜索场馆（并行）
    import asyncio
    keywords = ["非遗", "博物馆", "文化馆", "工艺"]
    if interests:
        keywords.extend(interests)

    search_tasks = [search_venues_amap(city=city, keyword=kw, limit=10) for kw in keywords[:3]]
    results = await asyncio.gather(*search_tasks, return_exceptions=True)
    all_venues = []
    for r in results:
        if isinstance(r, list):
            all_venues.extend(r)

    # 去重
    seen = set()
    unique_venues = []
    for v in all_venues:
        name = v["name"]
        if name not in seen:
            seen.add(name)
            unique_venues.append(v)

    # 过滤无效坐标
    unique_venues = [v for v in unique_venues if v.get("lng") and v.get("lat")]

    if len(unique_venues) < 2:
        text = _generate_template_route(city, days, interests)
        return {"itinerary": text, "route_data": None}

    days = min(days, 7)

    # 2. 解析出发地
    start_idx = await _resolve_start_point(start_point, city, unique_venues)

    # 3. 构建距离矩阵
    dist_matrix = await _build_distance_matrix(unique_venues, settings.amap_key)

    # 4. TSP 排序
    if start_idx is not None:
        full_order = _solve_tsp_nn(dist_matrix, start_idx)
    else:
        # 用质心作为起点
        centroid_lat = sum(v["lat"] for v in unique_venues) / len(unique_venues)
        centroid_lng = sum(v["lng"] for v in unique_venues) / len(unique_venues)
        best_start = min(
            range(len(unique_venues)),
            key=lambda i: _haversine_km(
                centroid_lat, centroid_lng,
                unique_venues[i]["lat"], unique_venues[i]["lng"],
            ),
        )
        full_order = _solve_tsp_nn(dist_matrix, best_start)

    # 5. 限制每天最多4个景点，按天分段
    max_venues = 4 * days
    if len(full_order) > max_venues:
        full_order = full_order[:max_venues]
    day_clusters = _cluster_into_days(full_order, days)

    # 6. 渲染输出
    time_slots = ["上午", "下午", "傍晚", "晚上"]
    lines = [f"# {city} {days}日非遗主题之旅\n"]

    if interests:
        lines.append(f"兴趣方向：{'、'.join(interests)}\n")
    if start_point:
        lines.append(f"出发地：{start_point}\n")

    total_dist = 0.0

    for day_idx, cluster in enumerate(day_clusters):
        if not cluster:
            continue

        day_num = day_idx + 1
        lines.append(f"## Day {day_num}")

        day_dist = 0.0
        for slot_idx, venue_idx in enumerate(cluster):
            v = unique_venues[venue_idx]
            slot = time_slots[slot_idx] if slot_idx < len(time_slots) else f"第{slot_idx + 1}站"
            # 标记起点和终点
            if slot_idx == 0:
                lines.append(f"- **🚩 起点 · {slot}**：{v['name']}")
            elif slot_idx == len(cluster) - 1:
                lines.append(f"- **🏁 终点 · {slot}**：{v['name']}")
            else:
                lines.append(f"- **{slot}**：{v['name']}")
            if v.get("address"):
                lines.append(f"  - 地址：{v['address']}")
            if v.get("business_hours"):
                lines.append(f"  - 营业时间：{v['business_hours']}")

            # 到下一站的距离/时间
            if slot_idx < len(cluster) - 1:
                next_idx = cluster[slot_idx + 1]
                travel = dist_matrix[venue_idx][next_idx]
                dist_km = travel["distance_km"]
                dur_min = travel["duration_min"]
                source = "步行" if travel["source"] == "amap" else "直线距离"
                lines.append(f"  - 🚶 {source}前往下一景点：{dist_km:.1f}km，约{dur_min:.0f}分钟")
                day_dist += dist_km

        total_dist += day_dist

        if day_dist > 0:
            lines.append(f"\n  本日行程总距离：约{day_dist:.1f}km")

        lines.append("")

    # 行程总览
    lines.append("## 行程总览\n")
    lines.append(f"- 共 {len([c for c in day_clusters if c])} 天行程，{sum(len(c) for c in day_clusters)} 个景点")
    if total_dist > 0:
        lines.append(f"- 总移动距离：约{total_dist:.1f}km")
    if settings.amap_key:
        lines.append("- 距离数据：高德步行导航（近距离）+ 直线距离估算（远距离）")
    else:
        lines.append("- 距离为直线距离估算，实际路程可能更长")
    lines.append("- 建议使用高德地图实时导航获取最佳路线")

    # 7. 构建结构化数据（供前端地图使用，只包含路线中的场馆）
    route_venues = []
    for day_idx, cluster in enumerate(day_clusters):
        for slot_idx, venue_idx in enumerate(cluster):
            v = unique_venues[venue_idx]
            role = "start" if slot_idx == 0 else ("end" if slot_idx == len(cluster) - 1 else "stop")
            route_venues.append({
                "name": v["name"],
                "lng": v["lng"],
                "lat": v["lat"],
                "address": v.get("address", ""),
                "role": role,
            })

    route_days = []
    for day_idx, cluster in enumerate(day_clusters):
        day_venues = []
        for slot_idx, venue_idx in enumerate(cluster):
            role = "start" if slot_idx == 0 else ("end" if slot_idx == len(cluster) - 1 else "stop")
            day_venues.append({
                "name": unique_venues[venue_idx]["name"],
                "lng": unique_venues[venue_idx]["lng"],
                "lat": unique_venues[venue_idx]["lat"],
                "address": unique_venues[venue_idx].get("address", ""),
                "role": role,
            })
        route_days.append(day_venues)

    return {
        "itinerary": "\n".join(lines),
        "route_data": {
            "city": city,
            "venues": route_venues,
            "days": route_days,
        },
    }


def _generate_template_route(
    city: str, days: int, interests: list[str] = None
) -> str:
    """
    生成模板路线（无场馆数据时的降级方案）。
    基于城市和兴趣生成通用建议。
    """
    lines = [f"# {city} {days}日非遗主题之旅（建议）\n"]
    lines.append("⚠️ 暂无该城市的实时场馆数据，以下为通用建议：\n")

    # 基于城市给出建议
    city_hints = {
        "广州": ["粤剧艺术博物馆", "陈家祠（广东民间工艺博物馆）", "永庆坊非遗街", "广州文化馆"],
        "北京": ["中国国家博物馆", "故宫博物院", "景泰蓝工厂", "老舍茶馆"],
        "上海": ["上海博物馆", "豫园（海派文化）", "上海工艺美术博物馆"],
        "杭州": ["中国丝绸博物馆", "西湖（龙井茶文化）", "河坊街非遗体验"],
        "成都": ["成都博物馆", "锦里（蜀绣蜀锦）", "川剧院", "宽窄巷子"],
        "苏州": ["苏州博物馆", "拙政园（苏式园林）", "苏绣研究所", "昆曲博物馆"],
        "西安": ["陕西历史博物馆", "碑林（书法）", "回民街（饮食文化）"],
        "南京": ["南京博物院", "云锦博物馆", "夫子庙（民俗文化）"],
        "长沙": ["湖南省博物馆", "湘绣研究所", "火宫殿（湘菜文化）"],
        "景德镇": ["中国陶瓷博物馆", "古窑民俗博览区", "陶溪川文创街区"],
    }

    hints = city_hints.get(city)
    if hints:
        venues_per_day = max(2, len(hints) // days)
        for day in range(1, days + 1):
            lines.append(f"## Day {day}")
            start = (day - 1) * venues_per_day
            day_hints = hints[start : start + venues_per_day]
            for i, h in enumerate(day_hints):
                time_slot = ["上午", "下午", "傍晚"][i] if i < 3 else "晚上"
                lines.append(f"- **{time_slot}**：{h}")
            lines.append("")
    else:
        for day in range(1, days + 1):
            lines.append(f"## Day {day}")
            lines.append("- 上午：参观当地博物馆/文化馆")
            lines.append("- 下午：体验非遗手工技艺")
            lines.append("- 傍晚：逛非遗特色街区")
            lines.append("")

    lines.append("\n💡 **建议**：")
    lines.append("1. 提前在高德地图中搜索「非遗」「博物馆」获取最新场馆信息")
    lines.append("2. 关注当地文旅局公众号，获取最新活动信息")
    lines.append("3. 部分非遗体验需要提前预约")

    if interests:
        lines.append(f"\n🎯 你感兴趣的类别：{'、'.join(interests)}")
        lines.append("可以进一步搜索这些类别相关的非遗项目和场馆。")

    return "\n".join(lines)
