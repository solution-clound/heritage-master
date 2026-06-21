# 非遗修行录

> 中国非物质文化遗产智能探索平台 — 基于 LangGraph Agent 的多大师对话系统

[![CI](https://github.com/solution-clound/heritage-master/actions/workflows/ci.yml/badge.svg)](https://github.com/solution-clound/heritage-master/actions)

## 项目简介

非遗修行录是一个集非遗知识问答、智能探索、修行成长于一体的 Web 平台。用户可以跟随 **5 位真实非遗大师**学习传统文化，使用 AI 探索助手搜索非遗项目、规划旅行路线、查询知识图谱，并通过修行系统记录学习进度。

**核心特色：**
- 🎭 **5 位真实非遗大师**：基于国家级非遗传承人人设，独立性格、说话风格和专精领域
- 🤖 **LangGraph Agent**：7 类意图识别 + 12 种追问模式，自动路由 14 个工具
- 🧠 **长效记忆**：跨会话记忆 + 用户画像自动构建，大师能"记住"学徒
- 🗺️ **多源融合**：对话 + 地图 POI + 知识图谱，单页完成全链路体验
- 📊 **可观测性**：Trace 追踪，结构化日志，快速定位多步执行问题

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12 + FastAPI + SQLite |
| 前端 | Vue 3 + Vue Router + Vite |
| Agent | LangGraph StateGraph + LangChain |
| LLM | DeepSeek API (ChatOpenAI 兼容) |
| 向量库 | ChromaDB (RAG 检索) |
| 地图 | 高德地图 API |
| 爬虫 | ihchina.cn (中国非遗网) |

---

## 功能演示

### 🎭 与非遗大师对话

5 位大师各有独立人设，基于真实采访素材提炼说话风格：

| 大师 | 领域 | 简介 |
|------|------|------|
| 🍵 叶汉钟 | 潮州工夫茶艺 | 国家级非遗传承人，精通凤凰单丛和工夫茶二十一式 |
| 🦁 黄钦添 | 广东醒狮 | 国家级非遗传承人，佛山醒狮世家，精通南狮套路百余套 |
| 🎭 蔡正仁 | 昆曲 | 国家级非遗传承人，昆曲表演艺术家 |
| 🪡 王秀英 | 广绣 | 国家级非遗传承人，广绣大师 |
| ✂️ 高凤莲 | 剪纸 | 国家级非遗传承人，剪纸大师 |

**对话示例（叶汉钟 · 工夫茶）：**

```
用户：叶大师，潮州工夫茶有什么讲究？

叶汉钟：
坐。——你问到点子上了。

潮州工夫茶，讲究的是"工夫"二字。不是说茶有多贵，
是泡茶的人花了多少心思。你看这套茶具——孟臣壶、若琛杯、
砂铫、红泥炉，每一样都有说道。

水温很关键。刚沸，蟹眼泡，刚好。差一度，茶味就不同。
凤凰单丛呢，要看香型——鸭屎香、蜜兰香、芝兰香，
每一种泡法都不太一样。

你先喝一口这杯蜜兰香，感受一下回甘。喝完了咱们再细说。
```

---

### 🤖 探索助手（LangGraph Agent）

探索助手能自动理解用户意图，拆分复合请求，调用合适工具：

```
用户：我想周末在广州体验醒狮，有什么好去处？

助手：
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
```

**支持的工具（14 个）：**

| 工具 | 功能 |
|------|------|
| search_heritage | 搜索非遗项目（按关键词、类别、地区） |
| find_venues | 查找体验场馆（高德地图 POI） |
| plan_trip | 规划非遗主题旅行路线 |
| query_knowledge_graph | 查询知识图谱 |
| get_inheritance_chain | 查询师承谱系 |
| browse_forum / post_to_forum | 论坛浏览/发帖 |
| find_events | 查找近期非遗活动 |

---

### 🧘 修行系统

四阶段渐进式学习路径：

| 阶段 | 要求 | 特点 |
|------|------|------|
| 入门期 | 初始阶段 | 培养兴趣，基础认知 |
| 成长期 | 5天功课 + 20次提问 | 深入了解，大师主动教学 |
| 精进期 | 15天功课 + 50次提问 | 精进沉淀，大师分享心得 |
| 传承期 | 30天功课 + 100次提问 | 可以传承和分享 |

---

### 🧠 长效记忆与用户画像

```
记忆系统：
├── chagongfu/{user_id}.json    ← 叶汉钟对该用户的记忆
├── wushishizi/{user_id}.json   ← 黄钦添对该用户的记忆
├── explorer/{user_id}.json     ← 探索助手的记忆
└── ...

每份记忆包含：
- 核心记忆：从对话中提取的关键信息
- 对话话题：历史讨论过的话题
- 用户画像：兴趣标签、性格观察、审美偏好
- 教学进度：大师教学的进度跟踪
```

画像自动聚合：跟随叶汉钟学茶 → 推荐茶文化非遗；跟随黄钦添学醒狮 → 了解用户对传统体育感兴趣。

---

### 🗺️ 知识图谱

构建非遗文化关系网络，支持师承谱系查询、知识探索：

```
查询师承链：GET /api/graph/chain?person=黄钦添

响应：
黄钦添 → 黄钦（父亲）→ 黄德华（祖父）
国家级传承人   佛山醒狮世家传人   佛山武术名家
```

---

## 系统架构

```
前端 (Vue3)
  ├── 大师对话页 — 5位非遗大师人格对话
  ├── 探索助手页 — LangGraph Agent 全能助手
  ├── 修行页    — 每日修行/收获/阶段
  ├── 论坛页    — 社区交流
  └── 行程页    — 非遗主题路线
        │
后端 (FastAPI REST API)
  ├── /api/ask        RAG 问答
  ├── /api/agent      LangGraph Agent（工具调用）
  ├── /api/search     非遗项目搜索
  ├── /api/venues     场馆查询（高德 POI）
  ├── /api/trip       行程规划
  ├── /api/graph/*    知识图谱查询
  ├── /api/forum/*    论坛 CRUD
  ├── /api/cultivation/* 修行系统
  └── /api/debug/*    可观测性（Trace/指标）
        │
Agent 层 (LangGraph StateGraph)
  classify_and_plan → agent_node → tool_node → validate_node → memory_node
        │
工具层 (14 个 Function Calling Tools)
```

---

## 快速启动

```bash
# 1. 克隆项目
git clone https://github.com/solution-clound/heritage-master.git
cd heritage-master

# 2. 安装依赖
pip install -e ".[dev]"

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key 和高德地图 Key

# 4. 启动后端
PYTHONPATH=src uvicorn heritage_master.web.app:app --reload --port 8000

# 5. 启动前端
cd web/frontend
npm install
npm run dev
```

---

## 项目结构

```
heritage-master/
├── src/heritage_master/
│   ├── agent/          # LangGraph Agent 核心（意图识别、节点、状态）
│   ├── tools/          # 14 个工具实现（搜索、场馆、路线、论坛等）
│   ├── data/           # 数据层（爬虫、知识图谱、向量库、数据库）
│   ├── memory/         # 长效记忆系统（画像、对话记忆）
│   ├── observability/  # 可观测性（Trace、指标、日志）
│   └── config.py       # 配置管理
├── web/
│   ├── app.py          # FastAPI 应用入口
│   ├── routers/        # API 路由
│   └── frontend/       # Vue 3 前端
├── personas/           # 5 位大师人设（JSON + 采访素材）
├── scripts/            # 工具脚本（人设蒸馏、RAG 构建）
├── tests/              # 测试用例
└── pyproject.toml      # 项目配置
```

---

## License

MIT
