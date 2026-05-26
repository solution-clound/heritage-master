# 贡献指南

感谢您对非遗大师助手项目的关注！我们欢迎任何形式的贡献。

## 如何报告问题

### 使用 GitHub Issues

1. 访问 [Issues 页面](https://github.com/heritage-master/heritage-master/issues)
2. 点击 "New Issue"
3. 选择合适的模板（Bug 报告或功能请求）
4. 填写详细信息

### Bug 报告应包含

- **环境信息**
  - 操作系统版本
  - Python 版本
  - 依赖版本（运行 `pip freeze`）

- **复现步骤**
  - 清晰的操作步骤
  - 相关代码或命令

- **期望行为**
  - 您期望发生什么

- **实际行为**
  - 实际发生了什么
  - 错误信息或日志

- **截图**（如适用）

### 功能请求应包含

- **问题描述**
  - 您想要解决什么问题

- **解决方案**
  - 您期望的实现方式

- **备选方案**
  - 您考虑过的其他方案

- **附加信息**
  - 相关文档或示例

## 如何提交 PR

### 1. Fork 项目

```bash
# Fork 项目到您的 GitHub 账号
# 然后克隆到本地
git clone https://github.com/YOUR_USERNAME/heritage-master.git
cd heritage-master
```

### 2. 创建分支

```bash
# 从 main 分支创建新分支
git checkout -b feature/your-feature-name

# 或修复 bug
git checkout -b fix/your-bug-fix
```

### 3. 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 进行修改...

# 运行测试
pytest tests/

# 运行 lint
ruff check src/ tests/
```

### 4. 提交

```bash
# 添加修改
git add .

# 提交（遵循 Commit 规范）
git commit -m "feat: add new feature"

# 推送到远程
git push origin feature/your-feature-name
```

### 5. 创建 Pull Request

1. 访问您的 Fork 仓库
2. 点击 "Compare & pull request"
3. 填写 PR 描述
4. 等待代码审查

### PR 描述应包含

- **变更说明**
  - 这个 PR 做了什么
  - 为什么做这个变更

- **相关 Issue**
  - 关联的 Issue 编号（如 `Fixes #123`）

- **测试**
  - 如何测试这个变更

- **截图**（如适用）

## 代码规范

### Python 风格

- 遵循 [PEP 8](https://peps.python.org/pep-0008/) 规范
- 使用 4 空格缩进
- 行长度限制：88 字符（Black 默认）

### 命名规范

- **变量和函数**: `snake_case`
- **类名**: `PascalCase`
- **常量**: `UPPER_SNAKE_CASE`
- **私有成员**: `_leading_underscore`

### 文档字符串

使用 Google 风格：

```python
def search_projects(query: str, limit: int = 10) -> list[dict]:
    """搜索非遗项目。

    Args:
        query: 搜索关键词
        limit: 返回数量，默认 10

    Returns:
        匹配的项目列表

    Raises:
        ValueError: 当参数无效时
    """
    pass
```

### 类型注解

- 使用类型注解提高代码可读性
- 支持 Python 3.10+ 语法

```python
# 好的做法
def get_project(name: str) -> dict | None:
    pass

# 避免
def get_project(name):
    pass
```

### 导入顺序

```python
# 1. 标准库
import os
from pathlib import Path

# 2. 第三方库
import httpx
from pydantic import BaseModel

# 3. 本地模块
from heritage_master.config import settings
from heritage_master.utils import helper
```

### 工具配置

项目使用以下工具：

- **Ruff**: 代码检查和格式化
- **Pytest**: 测试框架
- **MyPy**: 类型检查（可选）

配置在 `pyproject.toml` 中：

```toml
[tool.ruff]
line-length = 88
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

## 开发环境设置

### 1. 克隆项目

```bash
git clone https://github.com/heritage-master/heritage-master.git
cd heritage-master
```

### 2. 创建虚拟环境

```bash
# 使用 venv
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows

# 或使用 conda
conda create -n heritage python=3.12
conda activate heritage
```

### 3. 安装依赖

```bash
# 安装项目和开发依赖
pip install -e ".[dev]"

# 安装 RAG 功能（可选）
pip install -e ".[rag]"
```

### 4. 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置
# 至少需要配置 HERITAGE_AMAP_KEY
```

### 5. 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_search.py

# 运行并显示覆盖率
pytest --cov=heritage_master --cov-report=html
```

### 6. 启动开发服务器

```bash
# MCP Server
python -m heritage_master.server

# Web 服务
cd web
python app.py
```

## 项目结构

```
heritage-master/
├── src/
│   └── heritage_master/
│       ├── __init__.py
│       ├── server.py          # MCP Server 入口
│       ├── config.py          # 配置管理
│       ├── tools/             # MCP 工具实现
│       ├── services/          # 业务逻辑
│       └── utils/             # 工具函数
├── web/
│   ├── app.py                 # Web 应用
│   ├── requirements.txt       # Web 依赖
│   └── frontend/              # 前端代码
├── tests/                     # 测试文件
├── docs/                      # 文档
├── examples/                  # 示例
├── pyproject.toml             # 项目配置
└── README.md
```

## 添加新功能

### 1. 添加 MCP 工具

```python
# src/heritage_master/tools/your_tool.py
from heritage_master.server import mcp

@mcp.tool()
async def your_tool_name(param: str) -> str:
    """工具描述。

    Args:
        param: 参数说明

    Returns:
        返回值说明
    """
    # 实现逻辑
    return result
```

### 2. 添加测试

```python
# tests/test_your_tool.py
import pytest
from heritage_master.tools.your_tool import your_tool_name

@pytest.mark.asyncio
async def test_your_tool():
    result = await your_tool_name("test")
    assert result is not None
```

### 3. 更新文档

- 更新 `README.md` 工具列表
- 更新 `docs/api-reference.md` API 文档
- 添加使用示例（如适用）

## 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**类型：**
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具相关

**示例：**
```
feat(search): add region filter support

fix(api): handle empty response from amap

docs(readme): update installation instructions

test(venues): add unit tests for venue search
```

## 发布流程

1. 更新版本号（`pyproject.toml`）
2. 更新 `CHANGELOG.md`
3. 创建 Git Tag
4. 推送到 GitHub
5. GitHub Actions 自动发布到 PyPI

## 社区准则

- 尊重他人
- 欢迎新手
- 建设性反馈
- 保持专业

## 获取帮助

- **GitHub Issues**: 报告问题或提出建议
- **GitHub Discussions**: 讨论和问答
- **Email**: your-email@example.com

## 许可证

贡献即表示您同意您的代码将在 [MIT License](../LICENSE) 下发布。
