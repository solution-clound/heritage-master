"""LangGraph 工具定义 — 薄包装层

所有工具逻辑委托给 tools/agent_tools.py 共享实现，
此处只负责 LangChain @tool 装饰器绑定和 docstring。
"""

from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool

from heritage_master.tools.agent_tools import (
    search_heritage_impl,
    get_heritage_info_impl,
    find_venues_impl,
    plan_trip_impl,
    ask_knowledge_impl,
    get_knowledge_impl,
    query_knowledge_graph_impl,
    get_inheritance_chain_impl,
    find_events_impl,
    explore_cultural_graph_impl,
    browse_forum_impl,
    post_to_forum_impl,
    reply_to_forum_impl,
    search_forum_impl,
)


@tool
async def search_heritage(query: str = "", category: Optional[str] = None, region: Optional[str] = None) -> str:
    """搜索中国非物质文化遗产项目。可按关键词、类别、地区筛选。
    Args:
        query: 搜索关键词，如"昆曲"、"刺绣"、"醒狮"
        category: 非遗类别（民间文学/传统音乐/传统舞蹈/传统戏剧/曲艺/传统体育游艺与杂技/美术/传统技艺/传统医药/民俗）
        region: 地区，如"广东"、"江苏"、"浙江"
    """
    return await search_heritage_impl(query=query, category=category, region=region)


@tool
async def get_heritage_info(name: str) -> str:
    """获取非遗项目的详细信息。包含历史渊源、技艺特点、传承人、代表作品等。
    Args:
        name: 项目名称，如"昆曲"、"广绣"、"京剧"
    """
    return await get_heritage_info_impl(name=name)


@tool
async def find_venues(city: str, keyword: str = "非遗") -> str:
    """查找某个城市的非遗体验场馆、博物馆、文化馆。
    Args:
        city: 城市名，如"广州"、"北京"、"上海"
        keyword: 搜索关键词，默认"非遗"，也可搜"博物馆"、"文化馆"等
    """
    return await find_venues_impl(city=city, keyword=keyword)


@tool
async def plan_trip(city: str, days: int = 2, interests: list[str] | str = None) -> str:
    """规划非遗主题旅行路线，包含每日行程安排和路线数据。
    Args:
        city: 城市名，如"潮州"、"苏州"、"西安"
        days: 游玩天数，1-7天
        interests: 感兴趣的非遗类别列表，如["传统技艺", "传统戏剧"]
    """
    return await plan_trip_impl(city=city, days=days, interests=interests)


@tool
async def ask_knowledge(question: str) -> str:
    """向非遗大师提问。基于 RAG 知识库回答非遗相关问题。支持任何非遗相关问题。
    Args:
        question: 你的问题，如"昆曲和京戏有什么区别？"、"四大名绣是哪些？"
    """
    return await ask_knowledge_impl(question=question)


@tool
async def get_knowledge(name: str, aspect: str = "overview") -> str:
    """获取非遗项目某方面的知识。
    Args:
        name: 项目名称
        aspect: 想了解的方面，可选值：
            - overview: 概述（默认）
            - history: 历史渊源
            - technique: 技艺特点
            - inheritors: 代表性传承人
            - works: 代表作品
            - learning: 学习资源
    """
    return await get_knowledge_impl(name=name, aspect=aspect)


@tool
async def query_knowledge_graph(query: str, node_type: Optional[str] = None) -> str:
    """查询文化知识图谱。搜索传承人、流派、代表作品、技艺、地区等节点。
    Args:
        query: 搜索关键词，如人名、项目名、流派名
        node_type: 限定节点类型（person/school/work/technique/project/region）
    """
    return query_knowledge_graph_impl(query=query, node_type=node_type)


@tool
async def get_inheritance_chain(person_name: str) -> str:
    """查询某位传承人的师承谱系，向上追溯师承关系。
    Args:
        person_name: 传承人姓名，如"叶汉钟"、"蔡奉弦"、"黄钦添"
    """
    return get_inheritance_chain_impl(person_name=person_name)


@tool
async def find_events(region: Optional[str] = None, keyword: Optional[str] = None) -> str:
    """查找非遗相关的活动、展览、工作坊，推荐对应地区的官方文化平台。
    Args:
        region: 地区，如"广东"、"北京"、"浙江"
        keyword: 搜索关键词
    """
    return find_events_impl(region=region, keyword=keyword)


@tool
async def explore_cultural_graph(node_id: str, depth: int = 2) -> str:
    """从某节点出发探索文化图谱，展示节点的多层关联关系。
    Args:
        node_id: 节点ID，如 "person:黄钦添", "project:醒狮"
        depth: 探索深度，1-3
    """
    return explore_cultural_graph_impl(node_id=node_id, depth=depth)


@tool
async def browse_forum(category: Optional[str] = None, keyword: Optional[str] = None, limit: int = 5) -> str:
    """浏览非遗论坛的讨论帖子。
    Args:
        category: 论坛分类（experience/guide/qna/stories/events）
        keyword: 搜索关键词
        limit: 返回数量，默认5
    """
    return await browse_forum_impl(category=category, keyword=keyword, limit=limit)


@tool
async def post_to_forum(title: str, body: str, category: str = "experience") -> str:
    """在非遗论坛发布帖子。
    Args:
        title: 帖子标题
        body: 帖子内容（Markdown格式）
        category: 分类（experience/guide/qna/stories/events）
    """
    return await post_to_forum_impl(title=title, body=body, category=category)


@tool
async def reply_to_forum(discussion_number: str, body: str) -> str:
    """回复非遗论坛的帖子。
    Args:
        discussion_number: 帖子ID
        body: 回复内容
    """
    return await reply_to_forum_impl(discussion_number=discussion_number, body=body)


@tool
async def search_forum(keyword: str, limit: int = 5) -> str:
    """搜索非遗论坛讨论。
    Args:
        keyword: 搜索关键词
        limit: 返回数量
    """
    return await search_forum_impl(keyword=keyword, limit=limit)


# 所有工具列表 —— 供 graph.py 使用
HERITAGE_TOOLS = [
    search_heritage,
    get_heritage_info,
    find_venues,
    plan_trip,
    ask_knowledge,
    get_knowledge,
    query_knowledge_graph,
    get_inheritance_chain,
    find_events,
    explore_cultural_graph,
    browse_forum,
    post_to_forum,
    reply_to_forum,
    search_forum,
]
