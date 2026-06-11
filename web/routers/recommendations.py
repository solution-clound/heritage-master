import json

from fastapi import Query, APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from heritage_master.data.crawler import search_heritage_data
from heritage_master.tools import user_manager

router = APIRouter()


@router.get("/api/recommendations")
async def api_recommendations(user_id: str = Query(...)):
    """基于用户画像推荐非遗项目"""
    # 读取用户兴趣标签
    profile = user_manager.get_user_profile(user_id, "explorer")
    interests = []
    if profile:
        raw = profile.get("interest_tags", "[]")
        try:
            interests = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            interests = []

    # 无兴趣标签时使用默认热门类别
    if not interests:
        interests = ["传统技艺", "传统戏剧", "传统音乐", "民俗", "传统美术"]

    # 用兴趣标签作为关键词搜索，每个标签取 3 条
    all_items = []
    seen_names = set()
    for tag in interests[:5]:
        items = await search_heritage_data(query=tag, limit=3)
        for item in items:
            name = item.get("name", "")
            if name not in seen_names:
                seen_names.add(name)
                all_items.append(item)

    return {"heritage": all_items[:15], "interests_used": interests[:5]}
