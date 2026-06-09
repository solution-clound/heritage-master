from __future__ import annotations

"""
非遗数据爬虫 - 从中国非物质文化遗产网实时获取国家级非遗名录数据

数据源：
1. 中国非物质文化遗产网 (ihchina.cn) - 国家级非遗名录 JSON API
2. 百度百科 - 非遗项目详细介绍

支持本地缓存，避免重复请求。
"""

import json
import hashlib
import time
import re
from pathlib import Path
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from heritage_master.config import settings


# ─── 非遗十大类别 ───────────────────────────────────────
CATEGORIES = [
    "民间文学",
    "传统音乐",
    "传统舞蹈",
    "传统戏剧",
    "曲艺",
    "传统体育、游艺与杂技",
    "传统美术",
    "传统技艺",
    "传统医药",
    "民俗",
]

# 类别名称到 ihchina.cn type 参数的映射
_CATEGORY_TYPE_MAP = {name: str(i + 1) for i, name in enumerate(CATEGORIES)}

# 常用省份行政区划代码
_PROVINCE_CODE_MAP = {
    "北京": "110000", "天津": "120000", "河北": "130000", "山西": "140000",
    "内蒙古": "150000", "辽宁": "210000", "吉林": "220000", "黑龙江": "230000",
    "上海": "310000", "江苏": "320000", "浙江": "330000", "安徽": "340000",
    "福建": "350000", "江西": "360000", "山东": "370000", "河南": "410000",
    "湖北": "420000", "湖南": "430000", "广东": "440000", "广西": "450000",
    "海南": "460000", "重庆": "500000", "四川": "510000", "贵州": "520000",
    "云南": "530000", "西藏": "540000", "陕西": "610000", "甘肃": "620000",
    "青海": "630000", "宁夏": "640000", "新疆": "650000",
}

# 省份代码反向映射
_CODE_PROVINCE_MAP = {v: k for k, v in _PROVINCE_CODE_MAP.items()}


# ─── 缓存管理 ──────────────────────────────────────────
class CacheManager:
    """本地文件缓存"""

    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir or settings.crawler_cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = settings.crawler_cache_ttl

    def _key_path(self, key: str) -> Path:
        safe_key = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str) -> Optional[dict]:
        path = self._key_path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - data.get("_cached_at", 0) > self.ttl:
                return None
            return data.get("payload")
        except Exception:
            return None

    def set(self, key: str, payload):
        path = self._key_path(key)
        path.write_text(
            json.dumps({"_cached_at": time.time(), "payload": payload}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


cache = CacheManager()


# ─── HTTP 客户端 ────────────────────────────────────────
def _get_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={
            "User-Agent": settings.user_agent,
            "Referer": "https://www.ihchina.cn/project.html",
        },
        timeout=settings.request_timeout,
        follow_redirects=True,
    )


# ─── 中国非遗网 JSON API 爬虫 ──────────────────────────
_IHCHINA_API = "https://www.ihchina.cn/getProject.html"


def _clean_rx_time(raw: str) -> str:
    """清理 rx_time 字段中的 HTML 标签"""
    cleaned = re.sub(r"<[^>]+>", "", raw).strip().rstrip(")")
    # 尝试提取年份和批次信息
    # 格式可能是 "2006(第一批" 或 "2008(第二批" 等
    m = re.match(r"(\d{4})\((.+)", cleaned)
    if m:
        return f"{m.group(1)}({m.group(2)})"
    return cleaned


def _map_province_code(province_name: str) -> str:
    """将省份名称映射为行政区划代码"""
    for name, code in _PROVINCE_CODE_MAP.items():
        if name in province_name:
            return code
    return ""


async def crawl_ihchina_list(
    keyword: str = "",
    category: str = "",
    region: str = "",
    page: int = 1,
    limit: int = 20,
) -> list[dict]:
    """
    从中国非遗网 JSON API 获取国家级非遗名录。

    Args:
        keyword: 搜索关键词
        category: 非遗类别（十大类之一）
        region: 地区（省份名称）
        page: 页码（1-based）
        limit: 返回数量

    Returns:
        非遗项目列表
    """
    # 构建缓存 key
    cache_key = f"ihchina_list_{keyword}_{category}_{region}_{page}_{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        print(f"[crawler] ✓ 列表缓存命中: {len(cached)} 条 (keyword={keyword})")
        return cached

    params = {
        "p": page,
        "limit": min(limit, 30),
        "category_id": "16",
    }

    if keyword:
        params["keywords"] = keyword
    if category:
        type_code = _CATEGORY_TYPE_MAP.get(category, "")
        if type_code:
            params["type"] = type_code
    if region:
        province_code = _map_province_code(region)
        if province_code:
            params["province"] = province_code

    results = []

    try:
        async with _get_client() as client:
            resp = await client.get(_IHCHINA_API, params=params)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("list", []):
                project = {
                    "name": item.get("title", ""),
                    "category": item.get("type", ""),
                    "level": item.get("cate", "国家级"),
                    "region": item.get("province", ""),
                    "project_num": item.get("project_num", ""),
                    "protect_unit": item.get("protect_unit", ""),
                    "batch": _clean_rx_time(item.get("rx_time", "")),
                    "detail_id": item.get("id", ""),
                    "detail_url": f"https://www.ihchina.cn/project_details/{item.get('id', '')}.html",
                    "source": "ihchina.cn",
                }
                results.append(project)

    except Exception as e:
        print(f"[crawler] 爬取中国非遗网失败: {e}")

    if results:
        cache.set(cache_key, results)
        print(f"[crawler] ✓ ihchina.cn 返回 {len(results)} 条 (keyword={keyword}, category={category}, region={region})")
    else:
        print(f"[crawler] ✗ ihchina.cn 返回 0 条 (keyword={keyword}, category={category}, region={region})，将使用内置数据")

    return results


async def crawl_ihchina_detail(detail_id: str) -> dict:
    """
    爬取单个非遗项目的详细信息。

    Args:
        detail_id: 项目 ID

    Returns:
        项目详细信息
    """
    cache_key = f"ihchina_detail_{detail_id}"
    cached = cache.get(cache_key)
    if cached:
        print(f"[crawler] ✓ 详情缓存命中: {detail_id}")
        return cached

    detail = {}

    try:
        url = f"https://www.ihchina.cn/project_details/{detail_id}.html"
        async with _get_client() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            # 强制使用 UTF-8 解码，避免编码问题
            html_text = resp.content.decode("utf-8", errors="replace")
            soup = BeautifulSoup(html_text, "html.parser")

            # 提取表格中的元信息
            for td in soup.select("td"):
                text = td.get_text(strip=True)
                for label in ["项目序号", "项目编号", "公布时间", "类别", "所属地区", "类型", "申报地区或单位", "保护单位"]:
                    if text.startswith(label):
                        value = text[len(label):].strip().lstrip("：:").strip()
                        detail[label] = value

            # 提取正文描述 - 尝试多种选择器
            for selector in [
                ".x-container",
                ".project-content",
                ".detail-content",
                ".project-detail",
                ".detail-text",
                ".introduce",
                ".project-introduce",
            ]:
                content_div = soup.select_one(selector)
                if content_div:
                    paragraphs = content_div.find_all("p")
                    text = "\n".join(
                        p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)
                    )
                    if text and len(text) > 20:
                        detail["description"] = text
                        break

            if not detail.get("description"):
                # 尝试从页面中提取大段文本
                main_content = soup.select_one("article, .content, main")
                if main_content:
                    text = main_content.get_text(strip=True)[:2000]
                    if text and len(text) > 20:
                        detail["description"] = text

            # 如果仍然没有描述，尝试从所有 <p> 标签中提取
            if not detail.get("description"):
                all_paragraphs = soup.find_all("p")
                texts = [p.get_text(strip=True) for p in all_paragraphs if len(p.get_text(strip=True)) > 20]
                if texts:
                    detail["description"] = "\n".join(texts[:10])

    except Exception as e:
        print(f"[crawler] 爬取详情页失败 ({detail_id}): {e}")

    if detail:
        cache.set(cache_key, detail)
        print(f"[crawler] ✓ 详情爬取成功: {detail.get('name', detail_id)}")

    return detail


# ─── 百度百科爬虫 ──────────────────────────────────────
async def crawl_baike(keyword: str) -> Optional[dict]:
    """
    从百度百科获取非遗项目的知识信息。

    Args:
        keyword: 搜索关键词，如 "昆曲"、"广绣"

    Returns:
        百科信息字典
    """
    cache_key = f"baike_{keyword}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        async with _get_client() as client:
            url = f"https://baike.baidu.com/item/{keyword}"
            resp = await client.get(url)

            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")

            result = {"name": keyword, "source": "baidu_baike"}

            # 摘要
            summary = soup.select_one(".lemma-summary, .card-summary-content")
            if summary:
                result["summary"] = summary.get_text(strip=True)

            # 信息卡片
            items = soup.select(".basicInfo-item")
            for item in items:
                name_el = item.select_one(".name, .basicInfo-item-name")
                value_el = item.select_one(".value, .basicInfo-item-value")
                if name_el and value_el:
                    key = name_el.get_text(strip=True).rstrip("：:")
                    result[key] = value_el.get_text(strip=True)

            # 正文前几段
            content_div = soup.select_one("#lemmaContent-0, .lemmaWgt-lemmaContent")
            if content_div:
                paragraphs = content_div.select("p")[:5]
                result["content"] = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

            if len(result) > 2:
                cache.set(cache_key, result)
                return result

    except Exception as e:
        print(f"[crawler] 百度百科爬取失败 ({keyword}): {e}")

    return None


# ─── 聚合搜索 ──────────────────────────────────────────
async def search_heritage_data(
    query: str = "",
    category: str = "",
    region: str = "",
    limit: int = 10,
) -> list[dict]:
    """
    搜索非遗项目。从 ihchina.cn 实时获取。

    Args:
        query: 搜索关键词
        category: 非遗类别
        region: 地区
        limit: 返回数量

    Returns:
        非遗项目列表
    """
    # 从 ihchina.cn API 获取
    items = await crawl_ihchina_list(
        keyword=query,
        category=category,
        region=region,
        limit=limit,
    )

    # 如果 API 返回为空，使用内置数据降级
    if not items:
        items = _get_builtin_data()
        # 本地过滤
        filtered = []
        for item in items:
            if query and query not in item.get("name", "") and query not in item.get("description", ""):
                continue
            if category and category not in item.get("category", ""):
                continue
            if region and region not in item.get("region", ""):
                continue
            filtered.append(item)
        items = filtered

    return items[:limit]


async def get_heritage_detail(name: str) -> dict:
    """
    获取非遗项目的详细信息。优先从 ihchina.cn 获取。

    Args:
        name: 项目名称

    Returns:
        详细信息字典
    """
    # 先搜索获取项目 ID，优先精确匹配
    items = await crawl_ihchina_list(keyword=name, limit=10)
    matched = None
    for item in items:
        if item.get("name") == name:
            matched = item
            break
    if not matched and items:
        matched = items[0]

    result = {}
    if matched and matched.get("detail_id"):
        detail = await crawl_ihchina_detail(matched["detail_id"])
        if detail:
            result = {**matched, **detail}
        else:
            result = matched or {}

    if not result:
        result = matched or {}

    # 如果 description 为空，从知识库补充
    if not result.get("description"):
        result = _enrich_from_knowledge(name, result)

    # 如果仍然没有 description，降级到百度百科
    if not result.get("description"):
        baike = await crawl_baike(name)
        if baike:
            if not result.get("description"):
                result["description"] = baike.get("description", baike.get("summary", ""))
            # 保留其他字段
            for k, v in baike.items():
                if k not in result and k not in ("source",):
                    result[k] = v

    # 最终降级：从内置数据获取
    builtin = _get_builtin_data()
    for item in builtin:
        if item["name"] == name:
            # 复制所有缺失的字段
            for k, v in item.items():
                if k not in result or not result[k]:
                    result[k] = v
            break

    # 如果仍然没有描述，根据元数据生成基本信息
    if result and not result.get("description"):
        result["description"] = _generate_meta_description(result)

    # 确保至少返回名称
    if not result:
        result = {"name": name}

    if not result.get("description"):
        result["description"] = "暂无详细信息"

    return result


def _generate_meta_description(item: dict) -> str:
    """根据项目元数据生成基本描述"""
    name = item.get("name", "")
    category = item.get("category", "")
    region = item.get("region", "")
    batch = item.get("batch", "")
    protect_unit = item.get("protect_unit", "")

    parts = [f"「{name}」"]
    if category:
        parts.append(f"属于{category}类非物质文化遗产")
    if region:
        parts.append(f"，流传于{region}地区")
    if batch:
        parts.append(f"，于{batch}列入国家级非物质文化遗产名录")
    if protect_unit:
        parts.append(f"。保护单位为{protect_unit}")

    return "".join(parts) + "。" if len(parts) > 1 else ""


def _enrich_from_knowledge(name: str, detail: dict) -> dict:
    """从本地知识库补充项目描述"""
    try:
        from heritage_master.tools.master_prompt import get_project_knowledge
        knowledge = get_project_knowledge(name)
        if knowledge and knowledge.get("description"):
            detail["description"] = knowledge["description"]
            # 补充其他可能缺失的字段
            if not detail.get("category") and knowledge.get("category"):
                detail["category"] = knowledge["category"]
            if not detail.get("region") and knowledge.get("region"):
                region = knowledge["region"]
                detail["region"] = "、".join(region) if isinstance(region, list) else region
    except Exception:
        pass
    return detail


# ─── 内置基础数据（爬虫失败时的降级方案）────────────────
# ─── 内置基础数据（爬虫失败时的降级方案）────────────────

_BUILTIN_DATA: Optional[list[dict]] = None


def _get_builtin_data() -> list[dict]:
    """
    内置的国家级非遗基础数据（186 项，覆盖十大类别）。
    从 builtin_heritage.json 加载，懒加载 + 内存缓存。
    """
    global _BUILTIN_DATA
    if _BUILTIN_DATA is not None:
        return _BUILTIN_DATA

    json_path = Path(__file__).parent / "builtin_heritage.json"
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        _BUILTIN_DATA = data
        return _BUILTIN_DATA
    except Exception as e:
        print(f"[crawler] 加载内置数据失败: {e}")

    _BUILTIN_DATA = [
        {"name": "昆曲", "category": "传统戏剧", "batch": "第一批", "region": "江苏,浙江,上海", "level": "国家级", "unesco": True, "unesco_year": 2001, "description": "昆曲被誉为百戏之祖。"},
        {"name": "京剧", "category": "传统戏剧", "batch": "第一批", "region": "北京", "level": "国家级", "unesco": True, "unesco_year": 2010, "description": "京剧是中国影响最大的戏曲剧种。"},
        {"name": "春节", "category": "民俗", "batch": "第一批", "region": "全国", "level": "国家级", "description": "春节是中国最重要的传统节日。"},
    ]
    return _BUILTIN_DATA
