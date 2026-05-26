# 非遗大师助手

中国非物质文化遗产大师助手 — MCP Server

精通中国 1500+ 项国家级非物质文化遗产，能帮你发现非遗、学习非遗、讨论非遗。

## 功能

| 功能 | 说明 | 数据来源 |
|------|------|---------|
| 非遗搜索 | 按名称/类别/地区搜索非遗项目 | 中国非遗网 + 内置数据 |
| 场馆查找 | 查找城市的非遗场馆/体验点 | 高德地图 API |
| 知识问答 | 深入了解非遗历史、技艺、传承人 | 百度百科 + RAG 知识库 |
| 非遗论坛 | 浏览/发布/搜索非遗讨论 | GitHub Discussions |
| 路线规划 | 规划非遗主题游览路线 | 高德地图 + 场馆数据 |

## 快速开始

### 安装

```bash
# 方式1：pip 安装
pip install heritage-master

# 方式2：从源码安装
git clone https://github.com/heritage-master/heritage-master.git

cd web && pip install -r requirements.txt
pip install -e .

# 安装 RAG 知识库功能（可选）
pip install heritage-master[rag]
```
conda activate heritage
  cd web
  pip install -r requirements.txt
  python app.py
### 配置

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env，填入你的 API Key
# 至少需要高德地图 API Key（场馆查询功能）
```

### 在 Claude Code 中使用

#### 方式1：MCP Server（推荐）

编辑 `~/.claude/settings.json` 或项目下的 `.mcp.json`：

```json
{
  "mcpServers": {
    "heritage": {
      "command": "python",
      "args": ["-m", "heritage_master.server"],
      "cwd": "/path/to/heritage-master",
      "env": {
        "HERITAGE_AMAP_KEY": "your_amap_key",
        "HERITAGE_GITHUB_TOKEN": "your_github_token",
        "HERITAGE_FORUM_REPO": "your-org/heritage-forum"
      }
    }
  }
}
```

#### 方式2：Skill（轻量版）

将 `heritage-master.md` 复制到 `.claude/skills/` 目录。

### 在 Cursor 中使用

编辑 `.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "heritage": {
      "command": "python",
      "args": ["-m", "heritage_master.server"],
      "env": {
        "HERITAGE_AMAP_KEY": "your_key"
      }
    }
  }
}
```

## 工具列表

| 工具 | 说明 |
|------|------|
| `search_heritage_projects` | 搜索非遗项目 |
| `get_heritage_project_info` | 获取项目详情 |
| `get_heritage_categories` | 列出十大类别 |
| `find_heritage_venues` | 查找附近场馆 |
| `ask_heritage_question` | 知识问答 |
| `get_heritage_knowledge` | 获取项目知识 |
| `browse_heritage_forum` | 浏览论坛 |
| `post_to_heritage_forum` | 发布帖子 |
| `reply_to_heritage_forum` | 回复帖子 |
| `search_heritage_forum` | 搜索论坛 |
| `plan_heritage_trip` | 规划路线 |

## 使用示例

```
你：广州有什么非遗项目？

AI（调用 search_heritage_projects）：
1. 粤剧 [传统戏剧] 第1批 ★UNESCO
   流传地区：广东,广西,海南,香港,澳门
2. 广绣 [传统技艺] 第1批
   流传地区：广东
3. 广东醒狮 [传统体育、游艺与杂技] 第1批
   流传地区：广东,广西
...

你：我想这周末去体验广绣

AI（调用 find_heritage_venues + plan_heritage_trip）：
为你推荐广州的广绣体验点，并规划了周末行程...
```

## 数据来源

| 数据 | 来源 | 更新方式 |
|------|------|---------|
| 非遗名录 | 中国非物质文化遗产网 | 爬虫 + 内置数据 |
| 场馆信息 | 高德地图 API | 实时查询 |
| 知识内容 | 百度百科 | 爬虫 + RAG |
| 论坛数据 | GitHub Discussions | API 实时 |

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/

# 启动开发服务器
python -m heritage_master.server
```

## 许可证

MIT License
