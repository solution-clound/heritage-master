# API 参考文档

本文档列出非遗大师助手提供的所有 MCP 工具和 Web API 端点。

## MCP 工具

MCP (Model Context Protocol) 工具供 AI 助手调用，实现非遗相关功能。

### 搜索与查询

#### search_heritage_projects

搜索中国非物质文化遗产项目。

**参数：**
- `query` (string, 可选): 搜索关键词，如"昆曲"、"刺绣"
- `category` (string, 可选): 非遗类别，可选值：民间文学/传统音乐/传统舞蹈/传统戏剧/曲艺/传统体育游艺杂技/传统美术/传统技艺/传统医药/民俗
- `region` (string, 可选): 地区，如"广东"、"江苏"
- `limit` (integer, 可选): 返回数量，默认 10

**返回：** 匹配的非遗项目列表

**示例：**
```json
{
  "query": "刺绣",
  "region": "江苏",
  "limit": 5
}
```

---

#### get_heritage_project_info

获取非遗项目的详细信息。

**参数：**
- `name` (string, 必需): 项目名称，如"昆曲"、"广绣"

**返回：** 项目的详细信息，包含历史渊源、技艺特点、传承人、代表作品等

**示例：**
```json
{
  "name": "昆曲"
}
```

---

#### get_heritage_categories

列出中国非物质文化遗产的十大类别。

**参数：** 无

**返回：** 十大类别列表

---

#### get_heritage_knowledge

获取非遗项目某方面的知识。

**参数：**
- `name` (string, 必需): 项目名称
- `aspect` (string, 可选): 想了解的方面，默认 "overview"
  - `overview`: 概述
  - `history`: 历史渊源
  - `technique`: 技艺特点
  - `inheritors`: 代表性传承人
  - `works`: 代表作品
  - `learning`: 学习资源

**返回：** 对应方面的知识内容

**示例：**
```json
{
  "name": "广绣",
  "aspect": "technique"
}
```

---

### 场馆查找

#### find_heritage_venues

查找某个城市的非遗场馆/体验点。

**参数：**
- `city` (string, 必需): 城市名，如"广州"、"北京"
- `keyword` (string, 可选): 搜索关键词，默认"非遗"
- `lng` (number, 可选): 经度
- `lat` (number, 可选): 纬度
- `radius` (integer, 可选): 搜索半径（米），默认 5000
- `limit` (integer, 可选): 返回数量，默认 10

**返回：** 场馆列表，包含名称、地址、电话、评分等

**示例：**
```json
{
  "city": "广州",
  "keyword": "博物馆",
  "limit": 5
}
```

---

### 知识问答

#### ask_heritage_question

向非遗大师提问。

**参数：**
- `question` (string, 必需): 你的问题

**返回：** 基于 RAG 知识库的回答内容

**示例：**
```json
{
  "question": "四大名绣是哪些？"
}
```

---

### 论坛功能

#### browse_heritage_forum

浏览非遗论坛的讨论帖。

**参数：**
- `category` (string, 可选): 论坛分类
  - `experience`: 体验分享
  - `guide`: 攻略推荐
  - `qna`: 知识问答
  - `stories`: 传承人故事
  - `events`: 活动信息
- `keyword` (string, 可选): 搜索关键词
- `limit` (integer, 可选): 返回数量，默认 5

**返回：** 讨论列表

---

#### post_to_heritage_forum

在非遗论坛发布帖子。

**参数：**
- `title` (string, 必需): 帖子标题
- `body` (string, 必需): 帖子内容（Markdown 格式）
- `category` (string, 可选): 分类，默认 "experience"

**返回：** 发布结果

---

#### reply_to_heritage_forum

回复非遗论坛的帖子。

**参数：**
- `discussion_number` (integer, 必需): 讨论编号
- `body` (string, 必需): 回复内容

**返回：** 回复结果

---

#### search_heritage_forum

搜索非遗论坛讨论。

**参数：**
- `keyword` (string, 必需): 搜索关键词
- `limit` (integer, 可选): 返回数量，默认 5

**返回：** 搜索结果

---

### 路线规划

#### plan_heritage_trip

规划非遗主题游览路线。

**参数：**
- `city` (string, 必需): 城市名
- `days` (integer, 可选): 游玩天数（1-7），默认 1
- `interests` (array, 可选): 感兴趣的非遗类别列表
- `start_point` (string, 可选): 出发地点

**返回：** 路线规划文本

**示例：**
```json
{
  "city": "杭州",
  "days": 2,
  "interests": ["传统技艺", "传统美术"]
}
```

---

### 知识图谱

#### query_knowledge_graph

搜索文化知识图谱。

**参数：**
- `query` (string, 必需): 搜索关键词
- `node_type` (string, 可选): 节点类型过滤
  - `person`: 人物
  - `school`: 流派
  - `technique`: 技艺
  - `work`: 作品
  - `project`: 项目
  - `region`: 地区
- `limit` (integer, 可选): 返回数量，默认 10

**返回：** 匹配的节点列表

---

#### get_inheritance_chain

获取某位传承人的师承链。

**参数：**
- `person_name` (string, 必需): 传承人姓名

**返回：** 师承链文本

**示例：**
```json
{
  "person_name": "陈少峰"
}
```

---

#### explore_cultural_graph

从某节点出发探索文化图谱。

**参数：**
- `node_id` (string, 必需): 节点 ID，如 "person:陈少峰"、"project:醒狮"
- `depth` (integer, 可选): 探索深度（1-3），默认 2

**返回：** 图谱探索结果文本

**示例：**
```json
{
  "node_id": "project:昆曲",
  "depth": 2
}
```

---

## Web API

Web API 提供 HTTP 接口，供前端应用或其他服务调用。

### 基础信息

- **Base URL**: `http://localhost:8000/api`
- **认证**: 部分接口需要 API Key
- **格式**: JSON

### 搜索与查询

#### GET /api/search

搜索非遗项目。

**查询参数：**
- `q` (string): 搜索关键词
- `category` (string): 非遗类别
- `region` (string): 地区
- `limit` (integer): 返回数量

**响应示例：**
```json
{
  "success": true,
  "data": [
    {
      "name": "昆曲",
      "category": "传统戏剧",
      "batch": "第1批",
      "region": "江苏",
      "unesco": true
    }
  ]
}
```

---

#### GET /api/project/{name}

获取项目详情。

**路径参数：**
- `name` (string): 项目名称

**响应示例：**
```json
{
  "success": true,
  "data": {
    "name": "昆曲",
    "category": "传统戏剧",
    "batch": "第1批",
    "unesco": true,
    "description": "...",
    "history": "...",
    "technique": "...",
    "inheritors": [...]
  }
}
```

---

### 场馆查询

#### GET /api/venues

查找非遗场馆。

**查询参数：**
- `city` (string, 必需): 城市名
- `keyword` (string): 搜索关键词
- `lng` (number): 经度
- `lat` (number): 纬度
- `radius` (integer): 搜索半径
- `limit` (integer): 返回数量

**响应示例：**
```json
{
  "success": true,
  "data": [
    {
      "name": "中国丝绸博物馆",
      "address": "杭州市西湖区玉皇山路73-1号",
      "phone": "0571-87035150",
      "rating": 4.8,
      "distance": 1200
    }
  ]
}
```

---

### 知识问答

#### POST /api/ask

向非遗大师提问。

**请求体：**
```json
{
  "question": "四大名绣是哪些？"
}
```

**响应示例：**
```json
{
  "success": true,
  "data": {
    "answer": "四大名绣是指中国刺绣中最具代表性的四种绣品..."
  }
}
```

---

### 知识获取

#### GET /api/knowledge

获取项目知识。

**查询参数：**
- `name` (string, 必需): 项目名称
- `aspect` (string): 知识方面

**响应示例：**
```json
{
  "success": true,
  "data": {
    "name": "广绣",
    "aspect": "technique",
    "content": "广绣的技艺特点..."
  }
}
```

---

### 论坛功能

#### GET /api/forum

获取论坛帖子列表。

**查询参数：**
- `category` (string): 分类
- `keyword` (string): 搜索关键词
- `limit` (integer): 返回数量

**响应示例：**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "title": "广州非遗体验分享",
      "author": "user123",
      "created_at": "2026-05-20T10:00:00Z",
      "category": "experience"
    }
  ]
}
```

---

#### POST /api/forum

发布新帖子。

**请求体：**
```json
{
  "title": "广州非遗体验分享",
  "body": "今天去了广州非遗展示中心...",
  "category": "experience"
}
```

---

#### GET /api/forum/{id}

获取帖子详情。

---

#### POST /api/forum/{id}/reply

回复帖子。

**请求体：**
```json
{
  "body": "我也去过那里，体验很棒！"
}
```

---

### 路线规划

#### POST /api/trip

规划非遗之旅。

**请求体：**
```json
{
  "city": "杭州",
  "days": 2,
  "interests": ["传统技艺", "传统美术"]
}
```

**响应示例：**
```json
{
  "success": true,
  "data": {
    "itinerary": [
      {
        "day": 1,
        "activities": [
          {
            "time": "09:00",
            "venue": "中国丝绸博物馆",
            "activity": "参观丝绸织造技艺展"
          }
        ]
      }
    ]
  }
}
```

---

### 知识图谱

#### GET /api/graph/search

搜索知识图谱。

**查询参数：**
- `q` (string, 必需): 搜索关键词
- `type` (string): 节点类型
- `limit` (integer): 返回数量

---

#### GET /api/graph/inheritance/{name}

获取传承人师承链。

**路径参数：**
- `name` (string): 传承人姓名

---

#### GET /api/graph/explore

探索知识图谱。

**查询参数：**
- `node_id` (string, 必需): 节点 ID
- `depth` (integer): 探索深度

---

### 用户功能

#### POST /api/user/register

用户注册。

**请求体：**
```json
{
  "username": "user123",
  "email": "user@example.com",
  "password": "password123"
}
```

---

#### POST /api/user/login

用户登录。

**请求体：**
```json
{
  "username": "user123",
  "password": "password123"
}
```

---

#### GET /api/user/profile

获取用户信息。

---

### 传承培养

#### GET /api/cultivation/projects

获取培养项目列表。

---

#### GET /api/cultivation/projects/{id}

获取培养项目详情。

---

#### POST /api/cultivation/apply

申请加入培养项目。

**请求体：**
```json
{
  "project_id": 1,
  "user_id": 123,
  "reason": "对传统技艺有浓厚兴趣..."
}
```

---

## 错误响应

所有 API 在出错时返回统一格式：

```json
{
  "success": false,
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "参数错误：city 不能为空"
  }
}
```

**常见错误码：**
- `INVALID_PARAMETER`: 参数错误
- `NOT_FOUND`: 资源未找到
- `UNAUTHORIZED`: 未授权
- `RATE_LIMITED`: 请求过于频繁
- `INTERNAL_ERROR`: 服务器内部错误

## 速率限制

- 未认证用户：60 次/小时
- 已认证用户：600 次/小时
- MCP 工具：无限制（本地运行）
