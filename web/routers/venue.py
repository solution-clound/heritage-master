from fastapi import Query, APIRouter

from heritage_master.tools.venue_finder import search_venues_amap, get_venue_detail
from heritage_master.data.crawler import search_heritage_data
from heritage_master.config import settings

router = APIRouter()


@router.get("/api/map-config")
async def map_config():
    """返回高德地图 JS API 配置（供前端 AmapView 使用）"""
    js_key = settings.amap_js_key or settings.amap_key
    return {
        "available": bool(js_key),
        "key": js_key,
        "security_code": settings.amap_security_code,
    }


@router.get("/api/venues")
async def api_venues(
    city: str = Query(..., description="城市名"),
    keyword: str = Query("非遗", description="搜索关键词"),
    limit: int = Query(10, ge=1, le=25),
    lng: float = Query(None, description="用户经度"),
    lat: float = Query(None, description="用户纬度"),
    sort: int = Query(None, description="排序: 0=距离 1=综合"),
):
    """查找非遗场馆"""
    venues = await search_venues_amap(city=city, keyword=keyword, limit=limit, lng=lng, lat=lat, sort=sort)
    # 为没有照片的场馆生成静态地图图片 URL
    amap_key = settings.amap_key
    for v in venues:
        if not v.get("photos") and v.get("lng") and v.get("lat") and amap_key:
            v["map_img"] = (
                f"https://restapi.amap.com/v3/staticmap?"
                f"location={v['lng']},{v['lat']}&zoom=15&size=400*200"
                f"&markers=mid,0xFF0000:{v['lng']},{v['lat']}&key={amap_key}"
            )
    return {"venues": venues, "city": city}


@router.get("/api/venue/detail")
async def api_venue_detail(
    poi_id: str = Query(..., description="高德 POI ID"),
):
    """获取场馆详情"""
    detail = await get_venue_detail(poi_id)
    # 添加静态地图图片
    if detail and not detail.get("photos") and detail.get("lng") and detail.get("lat"):
        if settings.amap_key:
            detail["map_img"] = (
                f"https://restapi.amap.com/v3/staticmap?"
                f"location={detail['lng']},{detail['lat']}&zoom=16&size=600*300"
                f"&markers=mid,0xFF0000:{detail['lng']},{detail['lat']}&key={settings.amap_key}"
            )
    return {"detail": detail}


@router.get("/api/venue/heritage")
async def api_venue_heritage(city: str = Query(...), name: str = Query("")):
    """获取场馆关联的非遗项目 — 优先用场馆名匹配，不足则补充城市级项目"""
    if not city:
        return {"heritage": []}
    # 去掉"市""区""县"等后缀，提高匹配率
    clean_city = city.replace("市", "").replace("区", "").replace("县", "")

    # 提取场馆名中的核心关键词（去掉常见无意义后缀）
    venue_keyword = ""
    if name:
        venue_keyword = (
            name.replace("博物馆", "").replace("展览馆", "").replace("展示馆", "")
            .replace("美术馆", "").replace("纪念馆", "").replace("艺术馆", "")
            .replace("传习所", "").replace("传习中心", "").replace("体验馆", "")
            .replace("研究院", "").replace("研究中心", "").replace("文化馆", "")
            .replace("非遗馆", "").replace("展馆", "").replace("工作室", "")
            .strip()
        )

    items = []
    # 1) 先用场馆关键词 + 城市搜索，找到与场馆主题相关的非遗项目
    if venue_keyword:
        items = await search_heritage_data(query=venue_keyword, region=clean_city, limit=6)

    # 2) 如果关键词匹配结果不足，补充城市级非遗项目
    if len(items) < 3:
        city_items = await search_heritage_data(region=clean_city, limit=6)
        # 去重
        existing_names = {i.get("name") for i in items}
        for it in city_items:
            if it.get("name") not in existing_names:
                items.append(it)
            if len(items) >= 6:
                break

    return {"heritage": items}
