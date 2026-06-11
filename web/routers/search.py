"""
搜索 / 项目详情 / 知识库 / 百度百科 路由
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from heritage_master.data.crawler import (
    CATEGORIES,
    crawl_baike,
    get_heritage_detail,
    search_heritage_data,
)
from heritage_master.data.realtime import get_platforms_for_region
from heritage_master.tools.knowledge_base import ask_heritage_expert, get_knowledge
from heritage_master.tools.venue_finder import search_venues_amap

from deps import get_llm

router = APIRouter()


# ─── 内部辅助 ────────────────────────────────────────────


async def _ask_llm(question: str, context: str = "", messages: list = None) -> str | None:
    """调用 LLM 生成回答。支持传入自定义 messages 或自动构建。"""
    llm = get_llm()
    if not llm:
        return None

    if messages is None:
        user_msg = f"参考资料：\n{context}\n\n用户问题：{question}" if context else question
        messages = [
            {"role": "system", "content": "你是非遗大师助手。"},
            {"role": "user", "content": user_msg},
        ]

    return await llm.chat_completion(messages, temperature=0.7, max_tokens=2000)


async def _enrich_search_results(items: list[dict], query: str, region: str) -> list[dict]:
    """用 LLM 增强搜索结果的内容"""

    async def enrich_one(item: dict) -> dict:
        name = item.get("name", "")
        # 收集上下文：知识库 + 元数据
        knowledge = await get_knowledge(name, "overview")
        meta_parts = []
        if item.get("category"):
            meta_parts.append(f"类别：{item['category']}")
        if item.get("region"):
            meta_parts.append(f"地区：{item['region']}")
        if item.get("batch"):
            meta_parts.append(f"批次：{item['batch']}")
        meta_text = " | ".join(meta_parts)

        prompt = f"""基于以下真实资料，用 2-3 句话介绍「{name}」这个非遗项目。
要求：语言自然流畅，突出特色和价值。不要编造信息，只基于提供的资料整理。

项目元数据：{meta_text}
知识库资料：{knowledge[:500] if knowledge else '无'}

请用中文回答，2-3句话即可："""

        answer = await _ask_llm(prompt)
        if answer:
            item["description"] = answer
            item["enriched"] = True
        return item

    # 并发处理，但限制并发数
    semaphore = asyncio.Semaphore(3)

    async def limited_enrich(item):
        async with semaphore:
            return await enrich_one(item)

    results = await asyncio.gather(*[limited_enrich(item) for item in items])
    return list(results)


# ─── 路由 ────────────────────────────────────────────────


@router.get("/api/categories")
async def api_categories():
    """返回非遗十大类别"""
    return {"categories": CATEGORIES}


@router.get("/api/search")
async def api_search(
    query: str = Query("", description="搜索关键词"),
    category: str = Query("", description="非遗类别"),
    region: str = Query("", description="地区"),
    limit: int = Query(10, ge=1, le=50),
    enrich: bool = Query(False, description="是否用 LLM 增强内容"),
):
    """搜索非遗项目"""
    items = await search_heritage_data(query=query, category=category, region=region, limit=limit)

    # 如果开启增强，用 LLM 为每个项目生成丰富描述
    if enrich and items and get_llm():
        enriched = await _enrich_search_results(items, query, region)
        return {"items": enriched, "total": len(enriched)}

    return {"items": items, "total": len(items)}


@router.get("/api/search/enriched")
async def api_search_enriched(
    query: str = Query("", description="搜索关键词"),
    category: str = Query("", description="非遗类别"),
    region: str = Query("", description="地区"),
    limit: int = Query(8, ge=1, le=20),
):
    """组合接口：返回项目搜索结果 + 文化平台链接 + 路径规划建议"""
    # 1. 搜索非遗项目
    items = await search_heritage_data(query=query, category=category, region=region, limit=limit)

    # 2. 用 LLM 增强描述
    if items and get_llm():
        items = await _enrich_search_results(items, query, region)

    # 3. 获取文化平台链接（省级 + 城市级）
    platforms = get_platforms_for_region(region)
    events = []
    for p in platforms:
        events.append({
            "name": p["name"],
            "url": p["url"],
            "source": p["name"],
            "source_type": "platform",
            "event_type": p.get("type", "文化平台"),
            "desc": p.get("desc", ""),
            "search_hint": p.get("search_hint", ""),
            "type": p.get("type", ""),
        })

    # 4. 获取相关场馆（如果有城市信息）
    venues = []
    if region:
        try:
            venues = await search_venues_amap(city=region, keyword=query or "非遗", limit=5)
        except Exception:
            pass

    # 5. 构建路线建议提示
    route_hint = None
    if venues and len(venues) >= 2:
        route_hint = {
            "message": f"找到 {len(venues)} 个相关场馆，可规划参观路线",
            "venues": [v.get("name", "") for v in venues[:5]],
            "city": region,
            "suggestion": "使用 /api/trip 接口规划详细路线",
        }

    return {
        "items": items,
        "events": events,
        "venues": venues,
        "route_hint": route_hint,
        "platforms": platforms,
        "total_projects": len(items),
        "note": "活动查询基于文化服务平台，提供官方直达链接",
    }


@router.get("/api/project/{name}")
async def api_project_detail(name: str):
    """获取非遗项目详情"""
    detail = await get_heritage_detail(name)
    return {"project": detail}


@router.get("/api/knowledge")
async def api_knowledge(
    name: str = Query(..., description="项目名称"),
    aspect: str = Query("overview", description="方面"),
):
    """获取项目知识"""
    content = await get_knowledge(name=name, aspect=aspect)
    return {"content": content, "name": name, "aspect": aspect}


@router.get("/api/baike/{keyword}")
async def api_baike(keyword: str):
    """百度百科信息"""
    data = await crawl_baike(keyword)
    return {"data": data}
