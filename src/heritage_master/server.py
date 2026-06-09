from __future__ import annotations

"""
非遗大师助手 - MCP Server 入口

基于 FastMCP 框架，注册所有非遗相关工具。
可被 Claude Code、Cursor、OpenClaw 等支持 MCP 的 AI 工具调用。

启动方式：
    # 开发模式
    python -m heritage_master.server

    # 或通过 uvx
    uvx heritage-master
"""

from mcp.server.fastmcp import FastMCP

from heritage_master.tools.heritage_search import search_heritage, get_heritage_info, list_categories
from heritage_master.tools.venue_finder import find_nearby_venues
from heritage_master.tools.knowledge_base import ask_heritage_expert, get_knowledge
from heritage_master.tools.forum import browse_discussions, create_discussion, reply_discussion, search_discussions
from heritage_master.tools.route_planner import plan_heritage_route
from heritage_master.tools.master_prompt import (
    MASTER_SYSTEM_PROMPT,
    build_qa_prompt,
    build_compare_prompt,
    get_project_knowledge,
    list_knowledge_projects,
)


# ─── 创建 MCP Server ───────────────────────────────────
mcp = FastMCP(
    "heritage-master",
    instructions="中国非物质文化遗产大师助手 - 精通非遗文化，提供导航、知识、论坛服务。"
    "你可以搜索非遗项目、查看详情、查找场馆、知识问答、规划旅行路线。"
    "使用 ask_heritage_question 工具向非遗大师提问，获取专业深度的回答。",
)


# ─── 注册 Tools ────────────────────────────────────────

@mcp.tool()
async def search_heritage_projects(
    query: str = "",
    category: str = "",
    region: str = "",
    limit: int = 10,
) -> str:
    """
    搜索中国非物质文化遗产项目。

    支持按名称、类别、地区筛选。数据来源：中国非物质文化遗产网。

    Args:
        query: 搜索关键词，如"昆曲"、"刺绣"、"醒狮"
        category: 非遗类别，可选值：民间文学/传统音乐/传统舞蹈/传统戏剧/曲艺/传统体育游艺杂技/传统美术/传统技艺/传统医药/民俗
        region: 地区，如"广东"、"江苏"、"浙江"
        limit: 返回数量，默认10

    Returns:
        匹配的非遗项目列表
    """
    return await search_heritage(query=query, category=category, region=region, limit=limit)


@mcp.tool()
async def get_heritage_project_info(name: str) -> str:
    """
    获取非遗项目的详细信息。

    包含历史渊源、技艺特点、传承人、代表作品等。
    数据来源：百度百科 + 中国非遗网。

    Args:
        name: 项目名称，如"昆曲"、"广绣"、"京剧"

    Returns:
        项目的详细信息
    """
    return await get_heritage_info(name)


@mcp.tool()
def get_heritage_categories() -> str:
    """
    列出中国非物质文化遗产的十大类别。

    Returns:
        十大类别列表
    """
    return list_categories()


@mcp.tool()
async def find_heritage_venues(
    city: str,
    keyword: str = "非遗",
    lng: float = None,
    lat: float = None,
    radius: int = 5000,
    limit: int = 10,
) -> str:
    """
    查找某个城市的非遗场馆/体验点。

    基于高德地图实时数据，返回场馆名称、地址、电话、评分等。

    Args:
        city: 城市名，如"广州"、"北京"、"上海"
        keyword: 搜索关键词，默认"非遗"，也可搜索"博物馆"、"文化馆"等
        lng: 经度（可选，提供后按距离排序）
        lat: 纬度（可选）
        radius: 搜索半径（米），默认5000
        limit: 返回数量，默认10

    Returns:
        场馆列表
    """
    return await find_nearby_venues(city=city, keyword=keyword, lng=lng, lat=lat, radius=radius, limit=limit)


@mcp.tool()
async def ask_heritage_question(question: str) -> str:
    """
    向非遗大师提问。

    基于 RAG 知识库回答非遗相关问题。支持任何非遗相关问题。

    Args:
        question: 你的问题，如"昆曲和京剧有什么区别？"、"四大名绣是哪些？"

    Returns:
        回答内容
    """
    return await ask_heritage_expert(question)


@mcp.tool()
async def get_heritage_knowledge(name: str, aspect: str = "overview") -> str:
    """
    获取非遗项目某方面的知识。

    Args:
        name: 项目名称
        aspect: 想了解的方面，可选值：
            - overview: 概述（默认）
            - history: 历史渊源
            - technique: 技艺特点
            - inheritors: 代表性传承人
            - works: 代表作品
            - learning: 学习资源

    Returns:
        对应方面的知识内容
    """
    return await get_knowledge(name=name, aspect=aspect)


@mcp.tool()
async def browse_heritage_forum(
    category: str = None,
    keyword: str = None,
    limit: int = 5,
) -> str:
    """
    浏览非遗论坛的讨论帖。

    Args:
        category: 论坛分类，可选值：
            - experience: 体验分享
            - guide: 攻略推荐
            - qna: 知识问答
            - stories: 传承人故事
            - events: 活动信息
        keyword: 搜索关键词
        limit: 返回数量，默认5

    Returns:
        讨论列表
    """
    return await browse_discussions(category=category, keyword=keyword, limit=limit)


@mcp.tool()
async def post_to_heritage_forum(
    title: str,
    body: str,
    category: str = "experience",
) -> str:
    """
    在非遗论坛发布帖子。

    Args:
        title: 帖子标题
        body: 帖子内容（Markdown格式）
        category: 分类，可选值：experience/guide/qna/stories/events

    Returns:
        发布结果
    """
    return await create_discussion(title=title, body=body, category=category)


@mcp.tool()
async def reply_to_heritage_forum(
    discussion_number: int,
    body: str,
) -> str:
    """
    回复非遗论坛的帖子。

    Args:
        discussion_number: 讨论编号
        body: 回复内容

    Returns:
        回复结果
    """
    return await reply_discussion(discussion_number=discussion_number, body=body)


@mcp.tool()
async def search_heritage_forum(
    keyword: str,
    limit: int = 5,
) -> str:
    """
    搜索非遗论坛讨论。

    Args:
        keyword: 搜索关键词
        limit: 返回数量

    Returns:
        搜索结果
    """
    return await search_discussions(keyword=keyword, limit=limit)


@mcp.tool()
async def plan_heritage_trip(
    city: str,
    days: int = 1,
    interests: list[str] = None,
    start_point: str = None,
) -> str:
    """
    规划非遗主题游览路线。

    基于城市和兴趣，规划多日非遗主题行程。

    Args:
        city: 城市名
        days: 游玩天数（1-7）
        interests: 感兴趣的非遗类别列表，如["传统戏剧", "传统技艺"]
        start_point: 出发地点（可选）

    Returns:
        路线规划文本
    """
    return await plan_heritage_route(city=city, days=days, interests=interests, start_point=start_point)


@mcp.tool()
async def query_knowledge_graph(
    query: str,
    node_type: str = "",
    limit: int = 10,
) -> str:
    """
    搜索文化知识图谱。

    搜索非遗知识图谱中的人物、流派、技艺、作品等节点。

    Args:
        query: 搜索关键词
        node_type: 节点类型过滤（person/school/technique/work/project/region）
        limit: 返回数量

    Returns:
        匹配的节点列表
    """
    from heritage_master.data.knowledge_graph import search_nodes
    results = search_nodes(query, node_type=node_type or None, limit=limit)
    if not results:
        return "未找到匹配的图谱节点"

    lines = [f"找到 {len(results)} 个相关节点："]
    for r in results:
        ntype = r.get("type", "")
        name = r.get("name", r.get("node_id", ""))
        desc = r.get("description", "")[:50]
        lines.append(f"- [{ntype}] {name}" + (f" - {desc}" if desc else ""))
    return "\n".join(lines)


@mcp.tool()
async def get_inheritance_chain(
    person_name: str,
) -> str:
    """
    获取某位传承人的师承链。

    向上追溯师承关系，显示传承脉络。

    Args:
        person_name: 传承人姓名

    Returns:
        师承链文本
    """
    from heritage_master.data.knowledge_graph import get_inheritance_chain as _get_chain
    person_id = person_name if ":" in person_name else f"person:{person_name}"
    chain = _get_chain(person_id)
    if not chain:
        return f"未找到 {person_name} 的师承记录"

    lines = [f"{person_name} 的师承链："]
    for i, c in enumerate(chain):
        name = c.get("name", "")
        title = c.get("title", "")
        prefix = "  " * i + ("└─ " if i > 0 else "")
        lines.append(f"{prefix}{name}" + (f" ({title})" if title else ""))
    return "\n".join(lines)


@mcp.tool()
async def explore_cultural_graph(
    node_id: str,
    depth: int = 2,
) -> str:
    """
    从某节点出发探索文化图谱。

    展示节点的多层关联关系。

    Args:
        node_id: 节点ID（如 "person:黄钦添", "project:醒狮"）
        depth: 探索深度（1-3）

    Returns:
        图谱探索结果文本
    """
    from heritage_master.data.knowledge_graph import explore_node
    result = explore_node(node_id, depth=min(depth, 3))
    if "error" in result:
        return result["error"]

    center = result["center"]
    lines = [f"【{center.get('name', '')}】({center.get('type', '')}) 的关联网络："]
    lines.append(f"共 {len(result['neighbors'])} 个关联节点：")

    for n in result["neighbors"]:
        name = n.get("name", "")
        ntype = n.get("type", "")
        edge = n.get("edge_type", "")
        d = n.get("depth", 0)
        indent = "  " * d
        lines.append(f"{indent}- [{edge}] {name} ({ntype})")

    return "\n".join(lines)


# ─── 注册 Prompts ──────────────────────────────────────

@mcp.prompt()
def heritage_expert_prompt() -> str:
    """获取非遗大师的系统人设提示词，用于自定义 AI 助手的行为。"""
    return MASTER_SYSTEM_PROMPT


@mcp.prompt()
def heritage_compare(project_a: str, project_b: str) -> str:
    """
    生成两个非遗项目的对比分析提示。

    Args:
        project_a: 第一个项目名称，如"昆曲"
        project_b: 第二个项目名称，如"京剧"
    """
    return (
        f"请从历史渊源、艺术特点、文化地位、传承现状等方面，"
        f"系统对比分析「{project_a}」和「{project_b}」的异同。\n\n"
        f"建议使用 get_heritage_project_info 工具获取两个项目的详细信息后再进行分析。"
    )


@mcp.prompt()
def heritage_guide(city: str, interests: str = "") -> str:
    """
    生成个性化的非遗旅行指南提示。

    Args:
        city: 目标城市
        interests: 兴趣方向，如"传统戏剧,传统技艺"
    """
    interest_text = f"，特别关注{interests}方面" if interests else ""
    return (
        f"请为用户规划一次{city}的非遗文化之旅{interest_text}。\n\n"
        f"建议：\n"
        f"1. 先用 find_heritage_venues 查找{city}的非遗场馆\n"
        f"2. 用 search_heritage_projects 搜索{city}相关的非遗项目\n"
        f"3. 用 plan_heritage_trip 规划具体行程\n"
        f"4. 结合当地特色美食、交通等给出实用建议"
    )


@mcp.prompt()
def heritage_deep_dive(project_name: str) -> str:
    """
    生成某个非遗项目的深度探索提示。

    Args:
        project_name: 项目名称
    """
    return (
        f"请对「{project_name}」进行全方位深度介绍。\n\n"
        f"建议从以下维度展开：\n"
        f"1. 历史渊源与文化背景\n"
        f"2. 核心技艺与美学特征\n"
        f"3. 代表性传承人及其贡献\n"
        f"4. 经典代表作品\n"
        f"5. 主要流派与地域差异\n"
        f"6. 当代传承现状与挑战\n"
        f"7. 如何学习和体验\n\n"
        f"可使用 get_heritage_project_info 和 get_heritage_knowledge 工具获取详细信息。"
    )


# ─── 注册 Resources ────────────────────────────────────

@mcp.resource("heritage://categories")
def get_categories_resource() -> str:
    """非遗十大类别"""
    return list_categories()


@mcp.resource("heritage://knowledge/projects")
def list_projects_resource() -> str:
    """列出知识库中所有有结构化知识的非遗项目"""
    projects = list_knowledge_projects()
    return f"知识库中包含以下 {len(projects)} 个非遗项目的结构化知识：\n" + "\n".join(f"- {p}" for p in projects)


@mcp.resource("heritage://knowledge/{name}")
def get_project_resource(name: str) -> str:
    """获取某个非遗项目的结构化知识"""
    knowledge = get_project_knowledge(name)
    if not knowledge:
        return f"暂无「{name}」的结构化知识。"
    import json
    return json.dumps(knowledge, ensure_ascii=False, indent=2)


# ─── 入口 ──────────────────────────────────────────────
def main():
    """MCP Server 入口"""
    mcp.run()


if __name__ == "__main__":
    main()
