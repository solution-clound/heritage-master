# 快速开始

本指南帮助您快速安装和使用非遗大师助手。

## 环境要求

- Python 3.10 或更高版本
- pip 或 conda 包管理器
- （可选）Docker

## 安装方式

### 方式一：pip 安装（推荐）

```bash
pip install heritage-master
```

### 方式二：从源码安装

```bash
# 克隆仓库
git clone https://github.com/heritage-master/heritage-master.git
cd heritage-master

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows

# 安装依赖
pip install -e ".[dev]"
```

### 方式三：Docker 安装

```bash
# 拉取镜像
docker pull heritage-master/heritage-master:latest

# 运行容器
docker run -p 8000:8000 \
  -e HERITAGE_AMAP_KEY=your_amap_key \
  heritage-master/heritage-master:latest
```

或使用 docker-compose：

```bash
# 复制并编辑配置
cp .env.example .env
# 编辑 .env 文件

# 启动服务
docker-compose up -d
```

## 配置说明

### 环境变量

复制配置模板并编辑：

```bash
cp .env.example .env
```

`.env` 文件配置项：

| 变量名 | 必需 | 说明 |
|--------|------|------|
| `HERITAGE_AMAP_KEY` | 是 | 高德地图 API Key，用于场馆查询 |
| `HERITAGE_GITHUB_TOKEN` | 否 | GitHub Token，用于论坛功能 |
| `HERITAGE_FORUM_REPO` | 否 | 论坛数据仓库，格式：`owner/repo` |
| `HERITAGE_CACHE_DIR` | 否 | 缓存目录，默认 `./heritage_cache` |

### 获取 API Key

1. **高德地图 API Key**
   - 访问 [高德开放平台](https://lbs.amap.com/)
   - 注册账号并创建应用
   - 获取 Web 服务 API Key

2. **GitHub Token**（可选）
   - 访问 [GitHub Settings > Tokens](https://github.com/settings/tokens)
   - 创建 Personal Access Token
   - 勾选 `repo` 和 `discussions` 权限

## 在 Claude Code 中使用

### 方式一：MCP Server（推荐）

编辑 `~/.claude/settings.json`：

```json
{
  "mcpServers": {
    "heritage": {
      "command": "python",
      "args": ["-m", "heritage_master.server"],
      "env": {
        "HERITAGE_AMAP_KEY": "your_amap_key",
        "HERITAGE_GITHUB_TOKEN": "your_github_token",
        "HERITAGE_FORUM_REPO": "your-org/heritage-forum"
      }
    }
  }
}
```

或在项目目录下创建 `.mcp.json`：

```json
{
  "mcpServers": {
    "heritage": {
      "command": "python",
      "args": ["-m", "heritage_master.server"],
      "cwd": "/path/to/heritage-master",
      "env": {
        "HERITAGE_AMAP_KEY": "your_amap_key"
      }
    }
  }
}
```

### 方式二：Skill（轻量版）

将 `heritage-master.md` 复制到 `.claude/skills/` 目录。

## 在 Cursor 中使用

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

## 基本使用示例

### 搜索非遗项目

```
你：广州有什么非遗项目？

AI：我来帮你搜索广州的非遗项目。
（调用 search_heritage_projects）

搜索结果：
1. 粤剧 [传统戏剧] 第1批 ★UNESCO
   流传地区：广东、广西、海南、香港、澳门

2. 广绣 [传统技艺] 第1批
   流传地区：广东

3. 广东醒狮 [传统体育、游艺与杂技] 第1批
   流传地区：广东、广西
```

### 查找体验场馆

```
你：北京哪里可以体验非遗？

AI：我来帮你查找北京的非遗体验场馆。
（调用 find_heritage_venues）

找到以下场馆：
1. 中国国家博物馆 - 东城区东长安街16号
2. 北京民俗博物馆 - 朝阳区朝外大街141号
3. 北京非遗展示中心 - 西城区陶然亭路
```

### 规划非遗之旅

```
你：我想在杭州玩两天，对传统技艺和传统美术感兴趣

AI：我来为你规划杭州非遗之旅。
（调用 plan_heritage_trip）

杭州2日非遗之旅推荐：

【第一天：传统技艺】
上午：中国丝绸博物馆（丝绸织造技艺）
下午：杭州工艺美术博物馆（王星记扇、张小泉剪刀）

【第二天：传统美术】
上午：浙江省博物馆（青瓷、木版年画）
下午：河坊街体验（剪纸、面塑）
```

### 知识问答

```
你：昆曲和京剧有什么区别？

AI：让我来为你解答。
（调用 ask_heritage_question）

昆曲和京剧的主要区别：

1. 历史起源
   - 昆曲：起源于元末明初，有600多年历史
   - 京剧：形成于清代，约200年历史

2. 音乐体系
   - 昆曲：曲牌体，旋律婉转细腻
   - 京剧：板腔体，节奏明快有力

3. 表演风格
   - 昆曲：载歌载舞，注重身段
   - 京剧：唱念做打并重
```

## 启动 Web 服务

```bash
# 进入 web 目录
cd web

# 安装依赖
pip install -r requirements.txt

# 启动服务
python app.py
```

访问 http://localhost:8000 查看 Web 界面。

## 下一步

- 查看 [API 参考文档](api-reference.md) 了解所有可用接口
- 查看 [贡献指南](contributing.md) 参与项目开发
- 查看 [示例文档](../examples/demo.md) 了解更多使用场景
