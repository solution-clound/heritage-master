"""
实时非遗数据 - 获取最新新闻、展览、活动信息

数据源：
1. 中国非遗网 (ihchina.cn) - 新闻资讯（HTML 解析）

注意：
- 所有数据均来自真实网络请求，不使用硬编码兜底数据
- 爬虫可能因页面改版而失效，失败时返回空列表
- 返回的数据均带有 source 字段标明来源
- 缓存 TTL 为 1 小时，避免频繁请求

返回格式：list[dict]，每条包含 title/date/source/summary/url
"""

from __future__ import annotations
import re
import time
import json
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

import httpx

# ─── 缓存（短时效）──────────────────────────────────────
_cache = {}
_CACHE_TTL = 3600  # 1 小时


def _get_cached(key: str) -> Optional[list]:
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < _CACHE_TTL:
            return data
    return None


def _set_cache(key: str, data: list):
    _cache[key] = (time.time(), data)


# ─── 活动类型关键词 ─────────────────────────────────────
_EVENT_KEYWORDS = [
    "展览", "展演", "展示", "博览会", "展览馆",
    "活动", "体验", "互动", "参与",
    "报名", "预约", "名额",
    "工作坊", "工坊", " workshop",
    "讲座", "论坛", "研讨会",
    "大赛", "比赛", "竞赛", "评选",
    "演出", "公演", "汇演", "巡演",
    "培训", "研修", "传习",
    "市集", "集市", "庙会", "节庆",
    "开幕", "启动", "开幕",
]


def _classify_news(title: str) -> str:
    """根据标题判断是活动还是新闻"""
    for kw in _EVENT_KEYWORDS:
        if kw in title:
            return "event"
    return "news"


# ─── 中国非遗网新闻 ─────────────────────────────────────
_IHCHINA_NEWS_URL = "https://www.ihchina.cn/showInformation.html"


async def fetch_ihchina_news(limit: int = 10) -> list[dict]:
    """
    从中国非遗网获取最新新闻。

    注意：这是 HTML 解析，可能因页面改版而失效。
    失败时返回空列表，不返回假数据。
    """
    cached = _get_cached("ihchina_news")
    if cached is not None:
        return cached[:limit]

    results = []
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                _IHCHINA_NEWS_URL,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.ihchina.cn/",
                },
            )
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                # 尝试解析新闻列表
                for item in soup.select(".information-list li, .news-list li, .info-item")[:limit]:
                    title_el = item.select_one("a, .title, h3")
                    date_el = item.select_one(".date, .time, span")
                    if title_el:
                        title = title_el.get_text(strip=True)
                        link = title_el.get("href", "")
                        if link and not link.startswith("http"):
                            link = "https://www.ihchina.cn" + link
                        date = date_el.get_text(strip=True) if date_el else ""
                        if title and len(title) > 4:
                            item_type = _classify_news(title)
                            results.append({
                                "title": title,
                                "date": date,
                                "source": "中国非遗网",
                                "source_url": link,
                                "url": link,
                                "type": item_type,
                            })
    except Exception as e:
        print(f"[realtime] ihchina news fetch failed: {e}")

    if results:
        _set_cache("ihchina_news", results)
    return results[:limit]


# ─── 数据状态查询 ────────────────────────────────────────

def get_data_status() -> dict:
    """
    返回当前数据源的状态，供前端展示。
    让用户知道哪些数据是实时的、哪些获取失败了。
    """
    return {
        "ihchina_news": {
            "name": "中国非遗网新闻",
            "cached": "ihchina_news" in _cache,
            "source": "ihchina.cn",
            "type": "real_time",
        },
        "note": "所有数据均来自真实网络请求。爬虫可能因网站改版而失效。",
    }


# ─── 主要接口 ────────────────────────────────────────────

async def get_heritage_news(limit: int = 8) -> list[dict]:
    """
    获取最新非遗新闻和活动。

    仅从中国非遗网获取真实数据，不使用硬编码兜底数据。
    如果获取失败，返回空列表。

    Returns:
        list[dict]: 每条包含 title/date/source/summary/type
    """
    # 从中国非遗网获取
    ihchina_news = await fetch_ihchina_news(limit=limit)
    return ihchina_news[:limit]


async def get_heritage_events(
    keyword: str = "",
    region: str = "",
    limit: int = 10,
) -> list[dict]:
    """
    获取非遗活动（展览、工作坊、演出等）。

    从中国非遗网新闻中筛选活动类内容。
    如果没有注册链接，会标明来源。

    Args:
        keyword: 搜索关键词（如"茶文化"、"刺绣"）
        region: 地区筛选（如"广东"）
        limit: 返回数量

    Returns:
        list[dict]: 每条包含 title/date/source/source_url/type/event_type
    """
    # 获取所有新闻
    all_news = await fetch_ihchina_news(limit=50)

    # 筛选活动类
    events = [n for n in all_news if n.get("type") == "event"]

    # 如果没有活动类内容，返回空
    if not events:
        return []

    # 关键词筛选
    if keyword:
        events = [
            e for e in events
            if keyword in e.get("title", "") or keyword in e.get("summary", "")
        ]

    # 地区筛选
    if region:
        events = [
            e for e in events
            if region in e.get("title", "") or region in e.get("summary", "")
        ]

    # 为每条活动添加 event_type 分类
    for e in events:
        title = e.get("title", "")
        if any(kw in title for kw in ["展览", "展演", "展示", "博览会"]):
            e["event_type"] = "展览"
        elif any(kw in title for kw in ["工作坊", "工坊", "体验", "互动"]):
            e["event_type"] = "体验活动"
        elif any(kw in title for kw in ["讲座", "论坛", "研讨会"]):
            e["event_type"] = "讲座论坛"
        elif any(kw in title for kw in ["大赛", "比赛", "竞赛", "评选"]):
            e["event_type"] = "比赛评选"
        elif any(kw in title for kw in ["演出", "公演", "汇演", "巡演"]):
            e["event_type"] = "演出"
        elif any(kw in title for kw in ["培训", "研修", "传习"]):
            e["event_type"] = "培训传习"
        elif any(kw in title for kw in ["市集", "集市", "庙会", "节庆"]):
            e["event_type"] = "节庆市集"
        else:
            e["event_type"] = "其他活动"

    return events[:limit]


def get_news_for_context(question: str, limit: int = 5) -> list[dict]:
    """
    根据用户问题选择相关的新闻/活动。

    用于注入到 LLM prompt 中，让大师能引用最新动态。
    仅使用缓存中的真实数据，不返回假数据。
    如果没有缓存数据，返回空列表。
    """
    # 从缓存中获取已有的新闻
    cached = _get_cached("ihchina_news")
    if not cached:
        return []

    # 关键词匹配
    keywords = []
    category_keywords = {
        "戏曲": ["昆曲", "京剧", "粤剧", "戏曲", "戏剧"],
        "技艺": ["刺绣", "剪纸", "陶瓷", "漆器", "木雕", "技艺"],
        "音乐": ["古琴", "南音", "音乐"],
        "体育": ["太极拳", "武术", "醒狮", "龙舟"],
        "医药": ["中医", "针灸", "凉茶"],
        "民俗": ["春节", "端午", "中秋", "庙会", "民俗"],
    }

    for cat, kws in category_keywords.items():
        if any(k in question for k in kws):
            keywords.extend(kws)
            break

    # 如果没有特定关键词，返回前几条
    if not keywords:
        return cached[:limit]

    # 从缓存数据中筛选相关的
    related = []
    for n in cached:
        text = n.get("title", "") + n.get("summary", "")
        if any(kw in text for kw in keywords):
            related.append(n)

    # 如果相关数据不够，补充其他新闻
    if len(related) < limit:
        for n in cached:
            if n not in related:
                related.append(n)
            if len(related) >= limit:
                break

    return related[:limit]
