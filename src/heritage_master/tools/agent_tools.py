"""非遗探索助手 — Agent 工具定义

定义探索助手的 system prompt 和 function calling tools schema。
用于替代搜索、场馆、旅行三个独立页面，由 LLM 自动路由到合适工具。
"""

AGENT_SYSTEM_PROMPT = """你是非遗探索助手，帮助用户发现、了解和体验中国非物质文化遗产。

你有以下工具，每次只调用最匹配的一个：

**搜索与查询：**
1. **search_heritage** — 搜索非遗项目（按关键词、类别、地区）
2. **get_heritage_info** — 获取某个非遗项目的详细介绍
3. **query_knowledge_graph** — 查询知识图谱（传承人、流派、代表作品、技艺、地区关系）
4. **get_inheritance_chain** — 查询某位传承人的师承谱系（向上追溯）

**场馆与活动：**
5. **find_venues** — 查找体验场馆（博物馆、文化馆、体验中心）
6. **find_events** — 查找近期非遗活动、展览、演出、工作坊

**旅行规划：**
7. **plan_trip** — 规划非遗主题旅行路线（按城市、天数、兴趣）

**知识问答：**
8. **ask_knowledge** — 回答非遗相关知识问题（自由提问）
9. **get_knowledge** — 获取某个非遗项目的知识详情
10. **explore_cultural_graph** — 从某节点探索知识图谱（流派、传承关系等）

**论坛互动：**
11. **browse_forum** — 浏览论坛帖子（按分类或关键词）
12. **search_forum** — 搜索论坛帖子（按关键词）
13. **post_to_forum** — 在论坛发布帖子
14. **reply_to_forum** — 回复论坛帖子

【重要规则】你必须严格按照以下规则调用工具，不要自己编造答案：

- 用户问"有什么非遗"、"XX的非遗" → **必须调用** search_heritage
- 用户问"XX是谁"、"XX的传承人"、"XX有哪些流派" → **必须调用** query_knowledge_graph 或 get_inheritance_chain
- 用户问"哪里能体验"、"有什么场馆" → **必须调用** find_venues
- 用户问"最近有什么活动"、"展览"、"演出" → **必须调用** find_events
- 用户问"去XX玩"、"规划行程"、"X日游"、"路线"、"旅行" → **必须调用** plan_trip
- 用户问"XX是什么"、"介绍一下XX" → **必须调用** get_heritage_info 或 ask_knowledge
- 用户问"论坛"、"讨论"、"帖子"、"分享" → **必须调用** search_forum 或 browse_forum
- 用户要发帖、分享经历 → **必须调用** post_to_forum

用户的信息不够时，追问清楚再调用。不要在一个请求中调用多个工具。
回复时用亲切自然的语气。"""

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_heritage",
            "description": "搜索非遗项目，可按关键词、类别、地区筛选。返回项目名称、类别、地区等信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，如昆曲、刺绣、醒狮、剪纸",
                    },
                    "category": {
                        "type": "string",
                        "description": "非遗类别",
                        "enum": [
                            "民间文学",
                            "传统音乐",
                            "传统舞蹈",
                            "传统戏剧",
                            "曲艺",
                            "传统体育游艺与杂技",
                            "传统美术",
                            "传统技艺",
                            "传统医药",
                            "民俗",
                        ],
                    },
                    "region": {
                        "type": "string",
                        "description": "地区，如广东、浙江、北京、四川",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_venues",
            "description": "查找某城市的非遗体验场馆、博物馆、文化馆。返回场馆名称、地址、评分、电话等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名，如广州、潮州、北京、成都",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词，默认非遗，也可搜博物馆、文化馆等",
                    },
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_trip",
            "description": "规划非遗主题旅行路线，包含每日行程安排。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名，如潮州、苏州、西安",
                    },
                    "days": {
                        "type": "integer",
                        "description": "游玩天数，1-7天",
                        "default": 2,
                    },
                    "interests": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "感兴趣的非遗类别，如传统技艺、传统戏剧",
                    },
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_knowledge_graph",
            "description": "查询文化知识图谱。可搜索传承人、流派、代表作品、技艺、地区等节点及其关系。适合回答XX是谁、XX有哪些流派、XX的代表作品、XX和XX有什么关系等问题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，如人名、项目名、流派名、作品名",
                    },
                    "node_type": {
                        "type": "string",
                        "description": "限定节点类型",
                        "enum": ["person", "school", "work", "technique", "project", "region"],
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_inheritance_chain",
            "description": "查询某位传承人的师承谱系，向上追溯师承关系。适合回答XX的师傅是谁、XX的传承脉络等问题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "person_name": {
                        "type": "string",
                        "description": "传承人姓名，如叶汉钟、蔡正仁、黄钦添",
                    },
                },
                "required": ["person_name"],
            },
        },
    },
]


# ─── 论坛工具实现 ─────────────────────────────────────────


async def browse_forum_impl(category: str = None, keyword: str = None, limit: int = 5) -> str:
    """浏览论坛帖子"""
    from .forum import list_posts
    posts = list_posts(category=category, limit=limit)
    if keyword:
        posts = [p for p in posts if keyword in p.get("title", "") or keyword in p.get("content", "")]
    if not posts:
        return f"暂无相关讨论（分类={category or '全部'}，关键词={keyword or '无'}）。"
    lines = []
    for i, p in enumerate(posts[:limit], 1):
        lines.append(f"{i}. 【{p.get('category', '')}】{p.get('title', '')}")
        lines.append(f"   作者：{p.get('author', '匿名')} | 时间：{p.get('created_at', '')[:10]} | 👍{p.get('like_count', 0)} 💬{p.get('comment_count', 0)}")
        if p.get("content"):
            lines.append(f"   {p['content'][:100]}...")
        lines.append("")
    return "\n".join(lines)


async def search_forum_impl(keyword: str, limit: int = 5) -> str:
    """搜索论坛帖子"""
    from .forum import search_posts
    posts = search_posts(keyword=keyword, limit=limit)
    if not posts:
        return f"未找到关于「{keyword}」的讨论。"
    lines = [f"搜索结果：{keyword}（共{len(posts)}条）\n"]
    for i, p in enumerate(posts[:limit], 1):
        lines.append(f"{i}. 【{p.get('category', '')}】{p.get('title', '')}")
        lines.append(f"   作者：{p.get('author', '匿名')} | 时间：{p.get('created_at', '')[:10]} | 👍{p.get('like_count', 0)} 💬{p.get('comment_count', 0)}")
        if p.get("content"):
            lines.append(f"   {p['content'][:100]}...")
        lines.append("")
    return "\n".join(lines)


async def post_to_forum_impl(title: str, body: str, category: str = "experience") -> str:
    """发布论坛帖子"""
    from .forum import create_post
    import uuid
    user_id = "agent_bot"  # Agent 发帖使用系统用户
    post_id = str(uuid.uuid4())[:8]
    result = create_post(user_id=user_id, title=title, content=body, category=category)
    if result:
        return f"帖子发布成功！\n标题：{title}\n分类：{category}\n编号：#{post_id}\n\n您的分享将帮助更多人了解非遗文化。"
    return "帖子发布失败，请稍后再试。"


async def reply_to_forum_impl(discussion_number: str, body: str) -> str:
    """回复论坛帖子"""
    from .forum import add_comment
    result = add_comment(post_id=discussion_number, user_id="agent_bot", content=body)
    if result:
        return f"回复成功！已回复帖子 #{discussion_number}。"
    return "回复失败，请检查帖子编号是否正确。"
