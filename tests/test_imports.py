"""导入和基础功能测试"""

import sys
import asyncio
import pytest

sys.path.insert(0, "src")


def test_imports():
    """测试所有模块导入"""
    from heritage_master.config import settings
    print("[OK] config 导入成功")

    from heritage_master.data.crawler import _get_builtin_data, CATEGORIES
    data = _get_builtin_data()
    print(f"[OK] crawler 导入成功，内置数据 {len(data)} 条")

    from heritage_master.tools.heritage_search import search_heritage, format_heritage_list
    print("[OK] heritage_search 导入成功")

    from heritage_master.tools.venue_finder import format_venue_list
    print("[OK] venue_finder 导入成功")

    from heritage_master.tools.knowledge_base import ask_heritage_expert
    print("[OK] knowledge_base 导入成功")

    from heritage_master.tools.forum import _check_config
    print("[OK] forum 导入成功")

    from heritage_master.tools.route_planner import plan_heritage_route
    print("[OK] route_planner 导入成功")

    from mcp.server.fastmcp import FastMCP
    print("[OK] FastMCP 导入成功")


@pytest.mark.asyncio
async def test_search():
    """测试搜索功能"""
    from heritage_master.data.crawler import search_heritage_data

    results = await search_heritage_data(query="广绣")
    print(f"[OK] 搜索'广绣'返回 {len(results)} 条结果")
    for r in results:
        print(f"   - {r['name']} [{r['category']}] {r['region']}")

    results = await search_heritage_data(region="广东")
    print(f"[OK] 搜索'广东'返回 {len(results)} 条结果")

    results = await search_heritage_data(category="传统戏剧")
    print(f"[OK] 搜索'传统戏剧'返回 {len(results)} 条结果")


if __name__ == "__main__":
    test_imports()
    print()
    asyncio.run(test_search())
    print()
    print("[DONE] 所有测试通过！")
