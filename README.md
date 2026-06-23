# 非遗大师助手 · 使用示例与演示文档

本文档展示非遗大师助手的实际功能和使用场景，供答辩演示使用。

---

## 系统概述

非遗大师助手是一个基于 AI 的非物质文化遗产互动学习平台，核心特色：

- **5 位真实非遗大师**：每位大师基于真实国家级非遗传承人人设，有独立的性格、说话风格和专精领域
- **双模式对话**：大师问答（/api/ask）+ 探索助手（/api/agent，LangGraph Agent 自动路由工具）
- **修行系统**：入门期 → 成长期 → 精进期 → 传承期，四阶段渐进式学习
- **长期记忆**：跨会话记忆 + 用户画像自动更新，大师能"记住"学徒
- **知识图谱**：非遗项目、传承人、流派、技艺的关系网络
- **数据来源**：中国非遗网（实时爬取）+ 高德地图 API + 百度百科 + 本地知识库

---

## 五位非遗大师
K
| 大师 | ID | 领域 | 简介 |
|------|----|------|------|
| 🍵 叶汉钟 | chagongfu | 潮州工夫茶艺 | 国家级非遗传承人，精通凤凰单丛和工夫茶二十一式 |
| 🦁 黄钦添 | wushishizi | 广东醒狮 | 国家级非遗传承人，佛山醒狮世家，精通南狮套路百余套 |
| 🎭 蔡正仁 | caizhengren | 昆曲 | 国家级非遗传承人，昆曲表演艺术家 |
| 🪡 王秀英 | wangxiuying | 广绣 | 国家级非遗传承人，广绣大师 |
| ✂️ 高凤莲 | gaofenglian | 剪纸 | 国家级非遗传承人，剪纸大师 |

---

## 场景一：与非遗大师对话

### 与叶汉钟大师聊工夫茶

```
用户：叶大师，潮州工夫茶有什么讲究？

助手（叶汉钟人设回复）：
坐。——你问到点子上了。

潮州工夫茶，讲究的是"工夫"二字。不是说茶有多贵，
是泡茶的人花了多少心思。你看这套茶具——孟臣壶、若琛杯、
砂铫、红泥炉，每一样都有说道。

水温很关键。刚沸，蟹眼泡，刚好。差一度，茶味就不同。
凤凰单丛呢，要看香型——鸭屎香、蜜兰香、芝兰香，
每一种泡法都不太一样。

你先喝一口这杯蜜兰香，感受一下回甘。喝完了咱们再细说。
```

### 与黄钦添大师聊醒狮

```
用户：黄师傅，醒狮和一般的舞狮有什么不同？

助手（黄钦添人设回复）：
来了？坐！这个问题问得好。

醒狮是南狮，跟北狮完全不一样。你看墙上那个红色的狮头——
那是关公狮，代表忠义。还有黑的张飞狮、黄的刘备狮，
各有各的性格。

南狮重"醒"字，讲究神韵，要舞出狮子的喜怒哀乐。
采青是核心技法，高台醒狮更见功夫。
北狮偏技巧杂耍，南狮重武术功底。

你看看这个狮头——这是我父亲留下来的，几十年了。
```

---

## 场景二：搜索非遗项目

### 对话示例

```
用户：广州有什么非遗项目？

助手：我来帮你搜索广州的非遗项目。

[调用 search_heritage(query="", region="广东")]

搜索到以下广州非遗项目：

1. 粤剧 [传统戏剧] 第1批 ★UNESCO
   流传地区：广东、广西、海南、香港、澳门

2. 广绣 [传统技艺] 第1批
   流传地区：广东

3. 广东醒狮 [传统体育、游艺与杂技] 第1批
   流传地区：广东、广西

4. 广彩 [传统美术] 第2批
   流传地区：广东

您对哪个项目感兴趣？我可以为您详细介绍。
```

---

## 场景三：知识问答（/api/ask）

### RAG 检索增强生成

系统会从非遗数据库搜索相关项目作为上下文，结合论坛帖子和实时新闻，由 LLM 生成回答。

```
用户：四大名绣是哪些？有什么区别？

助手：让我为您解答四大名绣的相关知识。

四大名绣是指中国刺绣中最具代表性的四种绣品：

1. 苏绣（江苏）— 精细雅洁，针法细密，代表作《猫》《金鱼》
2. 湘绣（湖南）— 形象生动，色彩鲜艳，擅长动物毛发
3. 粤绣（广东）— 构图饱满，喜用金银线装饰
4. 蜀绣（四川）— 针法严谨，平齐光亮，色彩对比强烈

（注：王秀英大师正是广绣/粤绣的国家级传承人，
您可以拜访她深入了解粤绣技艺。）
```

### 技术实现

```
POST /api/ask
Content-Type: application/json

{
  "question": "四大名绣是哪些？",
  "master_id": "wangxiuying",
  "user_id": "user_001",
  "session_id": "session_abc"
}

响应：
{
  "answer": "四大名绣是指苏绣、湘绣、粤绣、蜀绣..."
}
```

系统流程：
1. 从问题中提取关键词（"刺绣"、"四大名绣"等）
2. 并行搜索非遗数据库，获取相关项目数据
3. 搜索论坛帖子作为补充上下文（2-gram 中文分词）
4. 获取实时新闻/活动数据
5. 根据用户画像选择自适应 prompt（新用户简洁、资深用户深入）
6. 调用 DeepSeek LLM 生成回答
7. 异步提取记忆、更新用户画像

---

## 场景四：探索助手 — LangGraph Agent（/api/agent）

探索助手是基于 LangGraph StateGraph 的智能 Agent，能自动理解用户意图并路由到合适的工具。

### 工作流图

```
START → [agent] → route_after_agent → [tools] → ─┐
                │         │                        │
                │       reply                      │
                │         │                        │
                │      [memory]                    │
                │         │                        │
                └────────→END                      │
                         └─────────────────────────┘
```

### 对话示例：自动搜索 + 场馆 + 路线规划

```
用户：我想周末在广州体验醒狮，有什么好去处？

助手（探索助手）：
[自动调用 find_venues(city="广州", keyword="醒狮")]

为您找到以下醒狮体验场馆：

1. 佛山黄飞鸿狮艺武术馆
   地址：佛山市禅城区黄飞鸿纪念馆
   特色：醒狮表演 + 武术体验

2. 广东醒狮文化传承基地
   地址：广州市荔湾区
   特色：南狮教学、采青体验

[自动调用 plan_trip(city="广州", days=1, interests=["醒狮"])]

已为您规划一日醒狮文化之旅，含路线和时间安排。
需要我把路线保存下来吗？
```

### 探索助手支持的工具

| 工具 | 功能 |
|------|------|
| search_heritage | 搜索非遗项目（按关键词、类别、地区） |
| get_heritage_info | 获取项目详细介绍 |
| find_venues | 查找体验场馆（高德地图） |
| find_events | 查找近期非遗活动 |
| plan_trip | 规划非遗主题旅行路线 |
| query_knowledge_graph | 查询知识图谱 |
| get_inheritance_chain | 查询师承谱系 |
| browse_forum / search_forum | 浏览/搜索论坛 |
| post_to_forum | 发布论坛帖子 |

---

## 场景五：修行系统

修行系统为每位大师的学徒提供渐进式学习路径，分为四个阶段：

### 四阶段体系

| 阶段 | 要求 | 特点 |
|------|------|------|
| 入门期 | 初始阶段 | 培养兴趣，基础认知，大师话少、多观察 |
| 成长期 | 5天功课 + 20次提问 | 深入了解，大师开始主动教学 |
| 精进期 | 15天功课 + 50次提问 | 精进沉淀，大师分享心得 |
| 传承期 | 30天功课 + 100次提问 | 可以传承和分享 |

### 每日功课示例（叶汉钟 · 入门期）

```
今日功课：
"今天泡一杯茶，不急着喝，先闻闻香气，感受一下。"

昨日收获回顾：
您昨天聊到了凤凰单丛的香型分类，今天可以试着
品尝一杯鸭屎香，感受它的独特韵味。
```

### API 调用

```
# 获取今日功课
POST /api/cultivation/practice/assign
{"user_id": "user_001", "master_id": "chagongfu"}

# 提交练习记录
POST /api/cultivation/practice/submit
{"user_id": "user_001", "master_id": "chagongfu", "content": "今天泡了蜜兰香，回甘很好"}

# 查看修行地图
GET /api/cultivation/map?user_id=user_001&master_id=chagongfu

# 查看当前阶段
GET /api/cultivation/stage?user_id=user_001&master_id=chagongfu

# 记录每日收获
POST /api/cultivation/harvest
{"user_id": "user_001", "master_id": "chagongfu", "content": "学会了控水温"}
```

---

## 场景六：长期记忆与用户画像

### 记忆系统架构

```
memory/
├── chagongfu/
│   └── {user_id}.json    ← 叶汉钟大师对该用户的记忆
├── wushishizi/
│   └── {user_id}.json
├── explorer/
│   └── {user_id}.json    ← 探索助手的记忆
└── ...
```

每份记忆文件包含：
- **核心记忆**：从对话中提取的关键信息（兴趣、偏好、里程碑）
- **对话话题**：历史讨论过的话题
- **来访记录**：每次访问的时间和摘要
- **教学进度**：大师教学的进度跟踪
- **用户画像**：兴趣标签、性格观察、审美偏好、关系阶段

### 画像自动更新

系统每 5 次对话自动推断画像更新：
- 兴趣标签（如"茶文化"、"醒狮"）
- 性格观察（如"认真好学"、"喜欢动手实践"）
- 审美偏好（如"喜欢传统风格"）
- 关系阶段（入门期 → 成长期 → 精进期 → 传承期）

### 画像数据复用

探索助手会聚合用户在所有大师处的画像数据：
- 已跟随叶汉钟大师学茶 → 推荐茶文化相关非遗
- 已跟随黄钦添大师学醒狮 → 了解用户对传统体育感兴趣
- 性格观察 → 调整回复语气风格

```
# 查看聚合画像（调试接口）
GET /api/agent/profile-debug?user_id=user_001

响应示例：
{
  "user_id": "user_001",
  "merged_profile": {
    "interest_tags": ["茶文化", "醒狮", "工夫茶"],
    "personality_notes": "认真好学; 喜欢动手实践",
    "aesthetic_pref": "喜欢传统风格",
    "question_count": 25,
    "relationship_stage": "成长期",
    "masters_visited": ["叶汉钟（潮州工夫茶艺大师）", "黄钦添（广东醒狮大师）"]
  }
}
```

---

## 场景七：知识图谱

### 图谱结构

系统构建了非遗文化知识图谱，包含以下节点类型：
- **项目节点**：非遗项目（如昆曲、粤剧）
- **传承人节点**：非遗传承人（如叶汉钟、黄钦添）
- **流派节点**：艺术流派（如南昆、北昆）
- **技艺节点**：核心技艺（如采青、工夫茶二十一式）
- **地区节点**：流传地区

边关系包括：师承、流派归属、代表作品、技艺包含、流传地区等。

### 查询传承谱系

```
# 查询师承链
GET /api/graph/chain?person=黄钦添

响应：
{
  "chain": [
    {"name": "黄钦添", "title": "国家级非遗传承人"},
    {"name": "黄钦（父亲）", "title": "佛山醒狮世家传人"},
    {"name": "黄德华（祖父）", "title": "佛山武术名家"}
  ]
}
```

### 探索知识图谱

```
# 搜索图谱节点
GET /api/graph/search?q=昆曲&type=project

# 获取节点详情及邻居
GET /api/graph/node/project:昆曲

# 从某节点探索（深度 2）
GET /api/graph/explore?node_id=project:昆曲&depth=2

# 查找两节点间路径
GET /api/graph/path?from_id=person:叶汉钟&to_id=project:潮州工夫茶艺

# 图谱统计
GET /api/graph/stats
```

---

## 场景八：非遗论坛

论坛基于 SQLite 实现，支持发帖、评论、点赞、搜索。

### 浏览论坛

```
# 获取帖子列表
GET /api/forum/posts?category=experience&limit=10

# 搜索帖子
GET /api/forum/search?keyword=刺绣

# 获取帖子详情
GET /api/forum/posts/{post_id}

# 获取评论
GET /api/forum/posts/{post_id}/comments
```

### 发帖与互动

```
# 发帖
POST /api/forum/posts
{
  "user_id": "user_001",
  "title": "广州广绣体验分享",
  "content": "今天去了广州非遗展示中心体验了广绣...",
  "category": "experience"
}

# 评论
POST /api/forum/posts/{post_id}/comments
{"user_id": "user_002", "content": "分享得真好！"}

# 点赞/取消
POST /api/forum/posts/{post_id}/like
{"user_id": "user_002"}
```

### 论坛数据融入问答

系统在知识问答时会自动搜索论坛帖子作为补充上下文，让回答更接地气。

---

## 场景十：路线规划

```
# 规划非遗主题旅行
POST /api/trip
{
  "city": "潮州",
  "days": 2,
  "interests": ["工夫茶", "传统技艺"]
}

响应：
{
  "result": "# 潮州2日非遗之旅\n\n## 第一天：工夫茶主题\n...",
  "route_data": {
    "waypoints": [...],
    "total_distance": "15km"
  }
}

# 保存路线
POST /api/trips/save
{
  "user_id": "user_001",
  "city": "潮州",
  "days": 2,
  "interests": ["工夫茶"],
  "itinerary": "...",
  "route_data": {}
}

# 查看已保存路线
GET /api/trips?user_id=user_001
```

---

## 场景十一：用户系统

```
# 注册
POST /api/user/register
{"nickname": "茶友小张", "password": "1234"}

# 登录
POST /api/user/login
{"nickname": "茶友小张", "password": "1234"}

# 开始对话会话（自动加载记忆 + 生成个性化问候）
POST /api/user/session/start
{"user_id": "user_001", "master_id": "chagongfu"}

响应：
{
  "session_id": "session_abc",
  "greeting": "来了？坐。你上次说想了解单丛的香型，今天跟你细说。"
}

# 结束会话（自动生成话题摘要）
POST /api/user/session/end?session_id=session_abc

# 获取大师视角的用户画像
GET /api/user/{user_id}/profile/{master_id}

# 获取所有大师处的画像
GET /api/user/{user_id}/profiles
```

---

## Web API 汇总

### 核心接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/categories | 非遗十大类别 |
| GET | /api/search | 搜索非遗项目 |
| GET | /api/search/enriched | 组合搜索（项目+活动+场馆） |
| GET | /api/project/{name} | 项目详情 |
| POST | /api/ask | 知识问答（RAG + LLM） |
| POST | /api/agent | 探索助手（LangGraph Agent） |
| GET | /api/agent/greeting | 探索助手个性化问候 |
| POST | /api/trip | 路线规划 |

### 场馆与活动

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/venues | 查找非遗场馆（高德地图） |
| GET | /api/venue/detail | 场馆详情 |
| GET | /api/news | 非遗新闻（ihchina.cn） |
| GET | /api/events | 非遗活动 |

### 大师系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/masters | 列出所有大师 |
| GET | /api/masters/{id}/greeting | 大师问候语 |

### 修行系统

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/cultivation/practice/assign | 获取今日功课 |
| POST | /api/cultivation/practice/submit | 提交练习 |
| GET | /api/cultivation/practice/history | 练习历史 |
| GET | /api/cultivation/map | 修行地图 |
| GET | /api/cultivation/stage | 当前阶段 |
| POST | /api/cultivation/stage/transition | 阶段转换 |
| POST | /api/cultivation/harvest | 记录收获 |

### 知识图谱

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/graph/search | 搜索节点 |
| GET | /api/graph/node/{id} | 节点详情 |
| GET | /api/graph/explore | 探索图谱 |
| GET | /api/graph/chain | 师承链 |
| GET | /api/graph/path | 节点路径 |
| GET | /api/graph/stats | 图谱统计 |

### 论坛

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/forum/posts | 帖子列表 |
| POST | /api/forum/posts | 发帖 |
| GET | /api/forum/posts/{id} | 帖子详情 |
| POST | /api/forum/posts/{id}/like | 点赞 |
| GET | /api/forum/posts/{id}/comments | 评论列表 |
| POST | /api/forum/posts/{id}/comments | 发评论 |
| GET | /api/forum/search | 搜索帖子 |

### 用户系统

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/user/register | 注册 |
| POST | /api/user/login | 登录 |
| GET | /api/user/{id} | 用户信息 |
| POST | /api/user/session/start | 开始会话 |
| POST | /api/user/session/end | 结束会话 |
| GET | /api/user/{id}/profile/{master_id} | 用户画像 |
| GET | /api/user/{id}/profiles | 所有画像 |
| GET | /api/agent/profile-debug | 画像调试 |

### 路线管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/trips/save | 保存路线 |
| GET | /api/trips | 路线列表 |
| GET | /api/trips/{id} | 路线详情 |
| DELETE | /api/trips/{id} | 删除路线 |

### 调试与可观测

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/debug/traces | 请求追踪 |
| GET | /api/debug/trace/{id} | 追踪详情 |
| GET | /api/debug/metrics | 请求指标 |
| GET | /api/data-status | 数据源状态 |
| POST | /api/handoff | 转人工请求 |

---

## cURL 测试示例

```bash
# 搜索非遗项目
curl "http://localhost:8000/api/search?q=昆曲&region=广东"

# 知识问答
curl -X POST "http://localhost:8000/api/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "四大名绣是哪些？", "master_id": "wangxiuying"}'

# 探索助手
curl -X POST "http://localhost:8000/api/agent" \
  -H "Content-Type: application/json" \
  -d '{"message": "广州有什么非遗项目？", "user_id": "user_001"}'

# 查找场馆
curl "http://localhost:8000/api/venues?city=广州&keyword=醒狮"

# 列出大师
curl "http://localhost:8000/api/masters"

# 获取大师问候
curl "http://localhost:8000/api/masters/chagongfu/greeting?user_id=user_001"

# 知识图谱 - 搜索节点
curl "http://localhost:8000/api/graph/search?q=昆曲"

# 知识图谱 - 师承链
curl "http://localhost:8000/api/graph/chain?person=黄钦添"

# 论坛 - 帖子列表
curl "http://localhost:8000/api/forum/posts?limit=5"

# 实时新闻
curl "http://localhost:8000/api/news?limit=5"

# 修行 - 获取今日功课
curl -X POST "http://localhost:8000/api/cultivation/practice/assign" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_001", "master_id": "chagongfu"}'

# 路线规划
curl -X POST "http://localhost:8000/api/trip" \
  -H "Content-Type: application/json" \
  -d '{"city": "潮州", "days": 2, "interests": ["工夫茶"]}'
```

---

## Python 调用示例

```python
import httpx

base = "http://localhost:8000"

# 搜索非遗项目
resp = httpx.get(f"{base}/api/search", params={"q": "刺绣", "region": "广东"})
print(resp.json())

# 知识问答（指定大师）
resp = httpx.post(f"{base}/api/ask", json={
    "question": "广绣有什么特点？",
    "master_id": "wangxiuying",
    "user_id": "user_001"
})
print(resp.json()["answer"])

# 探索助手对话
resp = httpx.post(f"{base}/api/agent", json={
    "message": "广州有什么非遗项目？",
    "user_id": "user_001"
})
print(resp.json()["reply"])

# 注册 + 登录
user = httpx.post(f"{base}/api/user/register", json={
    "nickname": "茶友小张", "password": "1234"
}).json()

# 开始与叶汉钟大师对话
session = httpx.post(f"{base}/api/user/session/start", json={
    "user_id": user["id"], "master_id": "chagongfu"
}).json()
print(session["greeting"])  # 大师的个性化问候
```

---

## 技术架构

```
前端 Vue3 SPA ←→ FastAPI 后端
                     │
     ┌───────────────┼───────────────┐
     │               │               │
  LangGraph       RAG Pipeline    修行系统
  Agent (agent)    (ask)          (cultivation)
     │               │               │
  Function       非遗数据库        SQLite
  Calling        + 论坛搜索        记忆文件
     │               │               │
  7个工具         DeepSeek LLM    Redis缓存(可选)
     │
  ┌──┴──┐
  │     │
 高德  知识图谱
 地图  (JSON Graph)
```

### 数据来源

| 数据 | 来源 | 方式 |
|------|------|------|
| 非遗名录 | 中国非遗网 (ihchina.cn) | 实时 JSON API |
| 场馆信息 | 高德地图 API | 实时查询 |
| 知识内容 | 百度百科 + 本地知识库 | 爬虫 + RAG |
| 论坛数据 | SQLite 本地存储 | 本地 CRUD |
| 新闻活动 | 中国非遗网 | HTML 爬取 |
| 知识图谱 | JSON 文件 | 本地图谱引擎 |
| 用户记忆 | JSON 文件 + Redis | 跨会话持久化 |

---

## 更多应用场景

- **非遗教育**：学生跟随大师系统学习，从入门到传承
- **文化旅游**：规划非遗主题旅行，找到体验场馆
- **文化研究**：通过知识图谱探索传承关系和流派脉络
- **社区互动**：非遗爱好者在论坛分享体验和心得
- **个性化推荐**：基于用户画像推荐感兴趣的非遗内容
- **跨大师学习**：画像数据在不同大师间复用，了解用户全貌

---

## 反馈与建议

如果您有新的使用场景或改进建议，欢迎在项目中提出。
