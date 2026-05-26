"""非遗探索助手 — Agent 工具定义

定义探索助手的 system prompt 和 function calling tools schema。
用于替代搜索、场馆、旅行三个独立页面，由 LLM 自动路由到合适工具。
"""

AGENT_SYSTEM_PROMPT = """你是非遗探索助手，帮助用户发现、了解和体验中国非物质文化遗产。

你有三个工具，每次只调用最匹配的一个：
1. **search_heritage** — 搜索非遗项目（按关键词、类别、地区）
2. **find_venues** — 查找体验场馆（博物馆、文化馆、体验中心）
3. **plan_trip** — 规划旅行路线（按城市、天数、兴趣）

严格按用户意图选择工具，不要多调也不要少调：
- 用户问"有什么非遗"、"XX的非遗"、"传统戏剧有哪些" → 只调 search_heritage
- 用户问"哪里能体验"、"有什么场馆"、"博物馆" → 只调 find_venues
- 用户问"去XX玩"、"规划行程"、"X日游"、"路线"、"旅行" → 只调 plan_trip
- 用户的信息不够时，追问清楚再调用

不要在一个请求中调用多个工具。根据用户的具体意图，选择最合适的一个。
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
]
