#!/usr/bin/env python3
"""
构建非遗名录本地数据集

从中国非物质文化遗产网 (ihchina.cn) 抓取国家级非遗名录数据，
保存为 JSONL 格式供本地查询使用。

使用：
    # 抓取第五批（2021年）数据
    python scripts/build_dataset.py --batch 5

    # 抓取所有批次
    python scripts/build_dataset.py --all

    # 指定输出路径
    python scripts/build_dataset.py --batch 5 --output data/heritage_items.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

# 添加项目路径
_project_root = Path(__file__).resolve().parent.parent
_src_dir = str(_project_root / "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from heritage_master.data.crawler import (
    CATEGORIES,
    _CATEGORY_TYPE_MAP,
    _IHCHINA_API,
    _get_client,
    _clean_rx_time,
    cache,
)

# 批次与年份的映射
BATCH_MAP = {
    1: "2006",
    2: "2008",
    3: "2011",
    4: "2014",
    5: "2021",
}

# ihchina.cn 的批次筛选参数 (rx_time 字段包含的关键词)
BATCH_KEYWORDS = {
    1: "第一批",
    2: "第二批",
    3: "第三批",
    4: "第四批",
    5: "第五批",
}


async def fetch_batch(batch_num: int = 5, limit_per_page: int = 30) -> list[dict]:
    """
    抓取指定批次的所有非遗项目。

    Args:
        batch_num: 批次号 (1-5)
        limit_per_page: 每页数量

    Returns:
        项目列表
    """
    batch_keyword = BATCH_KEYWORDS.get(batch_num, f"第{batch_num}批")
    all_items = []
    seen_ids = set()

    print(f"[dataset] 开始抓取第{batch_num}批国家级非遗名录...")

    for cat_name in CATEGORIES:
        type_code = _CATEGORY_TYPE_MAP.get(cat_name, "")
        if not type_code:
            continue

        page = 1
        cat_count = 0

        while True:
            params = {
                "p": page,
                "limit": limit_per_page,
                "category_id": "16",
                "type": type_code,
            }

            try:
                async with _get_client() as client:
                    resp = await client.get(_IHCHINA_API, params=params)
                    resp.raise_for_status()
                    data = resp.json()

                    items = data.get("list", [])
                    if not items:
                        break

                    found_in_page = 0
                    for item in items:
                        rx_time = item.get("rx_time", "")
                        item_id = item.get("id", "")

                        # 过滤批次
                        if batch_keyword in rx_time or BATCH_MAP.get(batch_num, "") in rx_time:
                            if item_id and item_id not in seen_ids:
                                seen_ids.add(item_id)
                                project = {
                                    "name": item.get("title", ""),
                                    "category": item.get("type", ""),
                                    "level": item.get("cate", "国家级"),
                                    "region": item.get("province", ""),
                                    "project_num": item.get("project_num", ""),
                                    "protect_unit": item.get("protect_unit", ""),
                                    "batch": _clean_rx_time(rx_time),
                                    "batch_num": batch_num,
                                    "detail_id": item_id,
                                    "detail_url": f"https://www.ihchina.cn/project_details/{item_id}.html",
                                    "source": "ihchina.cn",
                                }
                                all_items.append(project)
                                cat_count += 1
                                found_in_page += 1

                    print(f"  [{cat_name}] 第{page}页: 找到 {found_in_page} 个第{batch_num}批项目")

                    # 如果这页没有找到目标批次的项目，且返回数量不足，可能已经翻完了
                    if found_in_page == 0 and len(items) < limit_per_page:
                        break

                    # 也检查是否已经到了非目标批次的数据
                    # 如果整页都是非目标批次，可以跳过
                    page += 1
                    await asyncio.sleep(0.5)  # 避免请求过快

            except Exception as e:
                print(f"  [{cat_name}] 第{page}页出错: {e}")
                break

        print(f"  [{cat_name}] 共找到 {cat_count} 个项目")

    print(f"\n[dataset] 总计抓取 {len(all_items)} 个第{batch_num}批项目")
    return all_items


async def enrich_details(items: list[dict], max_concurrent: int = 5) -> list[dict]:
    """
    为项目补充详细信息（从详情页抓取）。

    Args:
        items: 项目列表
        max_concurrent: 最大并发数

    Returns:
        补充了详情的项目列表
    """
    from heritage_master.data.crawler import crawl_ihchina_detail

    print(f"[dataset] 开始补充 {len(items)} 个项目的详情...")
    sem = asyncio.Semaphore(max_concurrent)
    enriched = 0

    async def enrich_one(item: dict):
        nonlocal enriched
        detail_id = item.get("detail_id")
        if not detail_id:
            return

        async with sem:
            try:
                detail = await crawl_ihchina_detail(detail_id)
                if detail:
                    if detail.get("description"):
                        item["description"] = detail["description"]
                    # 补充其他可能的字段
                    for k, v in detail.items():
                        if k not in item or not item[k]:
                            item[k] = v
                    enriched += 1
                    if enriched % 20 == 0:
                        print(f"  已补充 {enriched}/{len(items)} 个项目的详情")
                await asyncio.sleep(0.3)
            except Exception as e:
                print(f"  补充详情失败 ({item.get('name')}): {e}")

    tasks = [enrich_one(item) for item in items]
    await asyncio.gather(*tasks)

    print(f"[dataset] 详情补充完成，共 {enriched} 个项目有详细描述")
    return items


def save_jsonl(items: list[dict], output_path: Path):
    """保存为 JSONL 格式"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"[dataset] 已保存到 {output_path} ({len(items)} 条记录)")


async def main():
    parser = argparse.ArgumentParser(description="构建非遗名录本地数据集")
    parser.add_argument("--batch", type=int, default=5, help="批次号 (1-5)，默认5")
    parser.add_argument("--all", action="store_true", help="抓取所有批次")
    parser.add_argument("--no-detail", action="store_true", help="跳过详情页抓取（更快）")
    parser.add_argument("--output", help="输出路径（默认 data/heritage_batch{N}.jsonl）")

    args = parser.parse_args()
    output_dir = _project_root / "src" / "heritage_master" / "data"

    if args.all:
        # 抓取所有批次
        all_items = []
        for batch_num in range(1, 6):
            items = await fetch_batch(batch_num)
            if not args.no_detail and items:
                items = await enrich_details(items)
            all_items.extend(items)
            await asyncio.sleep(1)

        output_path = Path(args.output) if args.output else output_dir / "heritage_items.jsonl"
        save_jsonl(all_items, output_path)
    else:
        # 抓取指定批次
        items = await fetch_batch(args.batch)
        if not args.no_detail and items:
            items = await enrich_details(items)

        output_path = Path(args.output) if args.output else output_dir / f"heritage_batch{args.batch}.jsonl"
        save_jsonl(items, output_path)


if __name__ == "__main__":
    asyncio.run(main())
