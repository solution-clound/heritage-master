from __future__ import annotations

"""
非遗搜索工具 - 搜索和查询非遗项目
"""

from heritage_master.data.crawler import search_heritage_data, get_heritage_detail, CATEGORIES


def format_heritage_list(items: list[dict]) -> str:
    """格式化非遗项目列表为可读文本"""
    if not items:
        return "未找到匹配的非遗项目。请尝试其他关键词或扩大搜索范围。"

    lines = [f"找到 {len(items)} 个非遗项目：\n"]

    for i, item in enumerate(items, 1):
        name = item.get("name", "未知")
        category = item.get("category", "")
        region = item.get("region", "")
        batch = item.get("batch", "")
        unesco = " ★UNESCO" if item.get("unesco") else ""

        line = f"{i}. **{name}**"
        if category:
            line += f"  [{category}]"
        if batch:
            if "批" in batch:
                line += f"  {batch}"
            else:
                line += f"  第{batch}批"
        if unesco:
            line += unesco
        if region:
            line += f"\n   流传地区：{region}"
        desc = item.get("description", "")
        if desc:
            # 截取前100字
            short_desc = desc[:100] + "..." if len(desc) > 100 else desc
            line += f"\n   {short_desc}"

        lines.append(line)

    return "\n".join(lines)


def format_heritage_detail(item: dict) -> str:
    """格式化单个非遗项目的详细信息"""
    if not item:
        return "未找到该项目的详细信息。"

    name = item.get("name", "未知")
    lines = [f"# {name}\n"]

    # 基本信息
    if item.get("category"):
        lines.append(f"- **类别**：{item['category']}")
    if item.get("batch"):
        b = item["batch"]
        lines.append(f"- **批次**：{b}国家级非遗" if "批" in b else f"- **批次**：第{b}批国家级非遗")
    if item.get("year"):
        lines.append(f"- **入选年份**：{item['year']}年")
    if item.get("region"):
        lines.append(f"- **流传地区**：{item['region']}")
    if item.get("level"):
        lines.append(f"- **级别**：{item['level']}")
    if item.get("unesco"):
        unesco_year = item.get("unesco_year", "")
        year_str = f"（{unesco_year}年）" if unesco_year else ""
        lines.append(f"- **UNESCO**：人类非物质文化遗产代表作{year_str}")

    # 描述
    if item.get("description"):
        lines.append(f"\n## 简介\n{item['description']}")

    if item.get("summary"):
        lines.append(f"\n## 详细\n{item['summary']}")

    if item.get("content"):
        lines.append(f"\n## 更多\n{item['content']}")

    return "\n".join(lines)


async def search_heritage(
    query: str = "",
    category: str = "",
    region: str = "",
    limit: int = 10,
) -> str:
    """
    搜索非遗项目。

    Args:
        query: 搜索关键词，如"昆曲"、"刺绣"
        category: 非遗类别（民间文学/传统音乐/传统舞蹈/传统戏剧/曲艺/传统体育游艺杂技/传统美术/传统技艺/传统医药/民俗）
        region: 地区，如"广东"、"江苏"
        limit: 返回数量，默认10

    Returns:
        格式化的搜索结果
    """
    items = await search_heritage_data(query=query, category=category, region=region, limit=limit)
    return format_heritage_list(items)


async def get_heritage_info(name: str) -> str:
    """
    获取非遗项目的详细信息。

    Args:
        name: 项目名称，如"昆曲"、"广绣"

    Returns:
        项目的详细信息
    """
    detail = await get_heritage_detail(name)
    return format_heritage_detail(detail)


def list_categories() -> str:
    """列出非遗十大类别"""
    lines = ["# 中国非物质文化遗产十大类别\n"]
    for i, cat in enumerate(CATEGORIES, 1):
        lines.append(f"{i}. {cat}")
    lines.append("\n可使用类别名称作为搜索条件筛选。")
    return "\n".join(lines)
