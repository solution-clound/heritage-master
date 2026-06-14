# 非遗修行录

中国非物质文化遗产智能探索平台 — 基于 LangGraph Agent 的多大师对话系统

## 项目简介

非遗修行录是一个集非遗知识问答、智能探索、修行成长于一体的 Web 平台。用户可以跟随 5 位非遗大师学习传统文化，使用 AI 探索助手搜索非遗项目、规划旅行路线、查询知识图谱，并通过修行系统记录学习进度。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12 + FastAPI |
| 前端 | Vue 3 + Vue Router + Vite |
| Agent | LangGraph StateGraph + LangChain |
| LLM | DeepSeek API (ChatOpenAI 兼容) |
| 向量库 | ChromaDB (RAG 检索) |
| 数据库 | SQLite |
| 地图 | 高德地图 API |
| 爬虫 | ihchina.cn (中国非遗网) |

## 系统架构

```
前端 (Vue3)
  ├── 用户注册/登录
  ├── 大师对话页 (KnowledgeView) — 5位非遗大师人格对话
  ├── 探索助手页 (AgentView) — LangGraph Agent 全能助手
  ├── 修行页 (CultivationView) — 每日修行/收获/阶段
  ├── 论坛页 (ForumView) — 社区交流
  └── 行程页 (TripView) — 非遗主题路线
        │
后端 (FastAPI REST API)
  ├── /api/user/*       用户系统 (注册/登录/画像)
  ├── /api/ask          RAG 问答 (纯检索，非 Agent)
  ├── /api/agent        LangGraph Agent (工具调用)
  ├── /api/search       非遗项目搜索
  ├── /api/venues       场馆查询 (高德 POI)
  ├── /api/trip         行程规划
  ├── /api/graph/*      知识图谱查询
  ├── /api/forum/*      论坛 CRUD
  ├── /api/cultivation/* 修行系统
  └── /api/debug/*      可观测性 (Tracer/指标)
        │
Agent 层 (LangGraph StateGraph)
  classify_and_plan → agent_node → tool_node → validate_node → memory_node
        │
工具层 (14 个 Function Calling Tools)
  search_heritage / find_venues / plan_trip / query_knowledge_graph /
  browse_forum / post_to_forum / find_events / ...
        │
数据层
  ├── SQLite (heritage_data.db)
  ├── knowledge.json + graph.json (知识库)
  ├── 高德地图 API (POI/路线)
  ├── DeepSeek API (LLM 推理)
  └── ihchina.cn (新闻爬虫)
```

## 核心功能

### 1. 五位非遗大师

| 大师 | ID | 领域 |
|------|-----|------|
| 叶汉钟 | chagongfu | 潮州工夫茶艺 |
| 黄钦添 | wushishizi | 广东醒狮 |
| 蔡正仁 | caizheng | 昆曲 |
| 王秀英 | wangxiuying | 剪纸 |
| 高凤莲 | gaofenglian | 延川剪纸 |

每位大师有独立人格、对话风格和专业知识体系。

### 2. LangGraph Agent 探索助手

基于 LangGraph StateGraph 构建的智能助手，支持：
- **意图识别**：规则匹配(0.85) + 上下文感知(0.75) + LLM分类(0.70)
- **任务规划**：复杂任务自动生成多步执行计划
- **工具调用**：14个 Function Calling 工具
- **结果校验**：自动检测回复质量，连续失败触发人工交接
- **记忆系统**：会话记忆 → 用户画像 → 长期记忆三层架构

### 3. 修行系统

跟随大师的修行成长体系：
- 每日修行任务 (入门/成长/精进/传承 四阶段)
- 修行收获记录
- 阶段晋升机制

### 4. 知识图谱

非遗项目、传承人、流派、技艺、地区之间的关系网络，支持：
- 节点搜索与详情
- 师承谱系追溯
- 关系路径查询

### 5. 论坛社区

基于 SQLite 的社区交流：
- 发帖/评论/点赞
- 分类浏览与搜索
- 路线分享

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+ (前端构建)
- conda 或 venv

### 安装

```bash
# 克隆项目
git clone https://github.com/solution-clound/heritage-master.git
cd heritage-master

# 创建 conda 环境
conda create -n heritage python=3.12
conda activate heritage

# 安装后端依赖
cd web
pip install -r requirements.txt
cd ..

# 安装前端依赖并构建
cd web/frontend
npm install
npm run build
cd ../..
```

### 配置

创建 `.env` 文件：

```env
# DeepSeek API (必需)
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 高德地图 API (场馆/路线功能)
AMAP_KEY=your_amap_key

# SQLite 数据库路径 (默认 heritage_data.db)
SQLITE_PATH=heritage_data.db
```

### 启动

```bash
conda activate heritage
cd heritage-master
PYTHONPATH='src;web;.' python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

浏览器访问 http://localhost:8000

### 运行测试

```bash
conda activate heritage
pytest tests/
```

## 项目结构

```
heritage-master/
├── src/heritage_master/
│   ├── agent/           # LangGraph Agent
│   │   ├── graph.py     # StateGraph 构建
│   │   ├── nodes.py     # 图节点 (意图/规划/工具/校验/记忆)
│   │   ├── state.py     # AgentState 定义
│   │   └── tools.py     # 工具注册
│   ├── tools/           # 业务工具
│   │   ├── agent_tools.py    # 14个 Function Calling 工具
│   │   ├── master_prompt.py  # 5位大师人格定义
│   │   ├── cultivation.py    # 修行系统
│   │   ├── forum.py          # 论坛 CRUD
│   │   ├── memory.py         # 记忆管理器
│   │   └── user_manager.py   # 用户管理
│   ├── data/            # 数据层
│   │   ├── db.py              # SQLite 连接
│   │   ├── knowledge.json     # 非遗知识库
│   │   └── graph.json         # 知识图谱
│   ├── llm/             # LLM 客户端
│   ├── rag/             # RAG 检索
│   └── observability/   # 可观测性 (Tracer)
├── web/
│   ├── app.py           # FastAPI 主入口
│   ├── routers/         # API 路由
│   └── frontend/        # Vue3 前端
│       └── src/views/   # 页面组件
├── tests/               # 测试用例
├── docs/                # 文档
│   ├── functional-test-cases.md  # 功能测试用例表
│   └── diagrams/        # Excalidraw 架构图
├── heritage_data.db     # SQLite 数据库
└── .env                 # 环境变量
```

## API 文档

详见 [docs/api-reference.md](docs/api-reference.md)

## 测试用例

详见 [docs/functional-test-cases.md](docs/functional-test-cases.md) (20条功能测试用例)

## 架构图

Excalidraw 格式，拖拽到 https://excalidraw.com 打开：

- [系统架构图](docs/diagrams/system-architecture.excalidraw)
- [StateGraph 流程图](docs/diagrams/stategraph-flow.excalidraw)
- [数据流图](docs/diagrams/data-flow.excalidraw)
- [意图识别流程图](docs/diagrams/intent-recognition.excalidraw)

## 许可证

MIT License
