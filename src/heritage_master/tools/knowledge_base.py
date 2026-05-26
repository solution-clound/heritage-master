from __future__ import annotations

"""
知识库工具 - 非遗知识存储和检索

支持两种模式：
1. 本地 Markdown 文件检索（默认，零依赖）
2. RAG 向量检索（需要 chromadb + sentence-transformers）
"""

import time
from pathlib import Path
from typing import Optional

from heritage_master.config import settings


# ─── 知识库目录 ─────────────────────────────────────────
KNOWLEDGE_DIR = Path(__file__).parent.parent / "rag" / "knowledge"

# 文件内容缓存（TTL 5 分钟）
_file_cache: dict[str, str] = {}
_file_cache_time: float = 0
_FILE_CACHE_TTL = 300  # 秒


def _load_file_cache() -> dict[str, str]:
    """加载知识文件到内存缓存，TTL 5 分钟刷新"""
    global _file_cache, _file_cache_time
    now = time.time()
    if now - _file_cache_time < _FILE_CACHE_TTL and _file_cache:
        return _file_cache
    _file_cache = {}
    if KNOWLEDGE_DIR.exists():
        for md_file in KNOWLEDGE_DIR.glob("**/*.md"):
            try:
                _file_cache[md_file.stem] = md_file.read_text(encoding="utf-8")
            except Exception:
                pass
    _file_cache_time = now
    return _file_cache


def _search_local_files(query: str) -> Optional[str]:
    """
    本地 Markdown 文件搜索。
    使用内存缓存，避免每次查询都读磁盘。
    """
    cache = _load_file_cache()

    results = []
    for stem, content in cache.items():
        if query in stem or query in content:
            snippet = content[:2000]
            if len(content) > 2000:
                snippet += "\n\n... (内容已截断)"
            results.append(f"## 来源：{stem}\n\n{snippet}")

    if results:
        return "\n\n---\n\n".join(results[:3])

    return None


# ─── RAG 向量检索（可选）─────────────────────────────────
_rag_collection = None


def _init_rag():
    """初始化 RAG 向量库（延迟加载）"""
    global _rag_collection

    if not settings.rag_enabled:
        return None

    if _rag_collection is not None:
        return _rag_collection

    try:
        import chromadb

        client = chromadb.PersistentClient(path=settings.chroma_path)
        _rag_collection = client.get_or_create_collection(
            name="heritage_knowledge",
            metadata={"hnsw:space": "cosine"},
        )
        return _rag_collection
    except ImportError:
        print("[knowledge_base] RAG 依赖未安装，使用本地文件搜索。")
        print("  安装：pip install heritage-master[rag]")
        return None


def _search_rag(query: str, top_k: int = 3) -> Optional[str]:
    """RAG 向量检索"""
    collection = _init_rag()
    if collection is None:
        return None

    # 检查集合是否为空
    if collection.count() == 0:
        return None

    try:
        from heritage_master.data.local_embedding import embed_text

        # 使用本地模型生成查询向量
        query_embedding = embed_text(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
        )

        if not results.get("documents") or not results["documents"][0]:
            return None

        parts = []
        for i, (doc, metadata) in enumerate(
            zip(results["documents"][0], results["metadatas"][0])
        ):
            source = metadata.get("source", "未知来源")
            parts.append(f"## 结果 {i+1}（来源：{source}）\n\n{doc[:1500]}")

        return "\n\n---\n\n".join(parts)
    except Exception as e:
        print(f"[knowledge_base] RAG 检索失败: {e}")
        return None


def index_knowledge_files(reset: bool = False) -> str:
    """
    手动触发知识库索引。扫描 knowledge 目录下的 md 文件并存入 ChromaDB。

    Args:
        reset: 是否重置知识库后重建

    Returns:
        操作结果
    """
    collection = _init_rag()
    if collection is None:
        return "RAG 知识库未启用。请安装 rag 依赖（pip install heritage-master[rag]）"

    import chromadb
    from heritage_master.data.local_embedding import embed_batch

    if reset:
        client = chromadb.PersistentClient(path=settings.chroma_path)
        try:
            client.delete_collection("heritage_knowledge")
        except Exception:
            pass
        global _rag_collection
        _rag_collection = None
        collection = _init_rag()

    if not KNOWLEDGE_DIR.exists():
        return f"知识目录不存在：{KNOWLEDGE_DIR}"

    md_files = sorted(KNOWLEDGE_DIR.glob("**/*.md"))
    if not md_files:
        return f"知识目录中没有找到 .md 文件：{KNOWLEDGE_DIR}"

    total_paragraphs = 0
    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip() and len(p.strip()) >= 20]

        if not paragraphs:
            continue

        ids = [f"{md_file.stem}_{i}" for i in range(len(paragraphs))]
        metadatas = [
            {"source": md_file.name, "source_stem": md_file.stem, "paragraph_index": i}
            for i in range(len(paragraphs))
        ]

        embeddings = embed_batch(paragraphs)
        collection.upsert(ids=ids, documents=paragraphs, embeddings=embeddings, metadatas=metadatas)
        total_paragraphs += len(paragraphs)

    return f"已索引 {len(md_files)} 个文件，共 {total_paragraphs} 个段落"


# ─── 对外接口 ───────────────────────────────────────────
async def ask_heritage_expert(question: str) -> str:
    """
    向非遗大师提问。基于知识库回答。

    Args:
        question: 用户的问题

    Returns:
        回答内容
    """
    # 1. 尝试 RAG 检索
    rag_result = _search_rag(question)
    if rag_result:
        return f"根据知识库检索，以下是相关信息：\n\n{rag_result}"

    # 2. 尝试本地文件搜索
    local_result = _search_local_files(question)
    if local_result:
        return f"根据本地知识库：\n\n{local_result}"

    # 3. 降级：提示用户
    return (
        "知识库中暂未找到直接相关信息。\n\n"
        "你可以：\n"
        "1. 尝试用 `search_heritage` 工具搜索具体项目\n"
        "2. 用 `get_heritage_info` 查看某个项目的详细信息\n"
        "3. 将相关文档放入 `src/heritage_master/rag/knowledge/` 目录扩充知识库"
    )


async def get_knowledge(name: str, aspect: str = "overview") -> str:
    """
    获取非遗项目的知识。

    Args:
        name: 项目名称
        aspect: 方面（overview/history/technique/inheritors/works/learning）

    Returns:
        知识内容
    """
    from heritage_master.tools.master_prompt import get_project_knowledge

    # 优先从结构化知识库获取
    knowledge = get_project_knowledge(name)
    if knowledge:
        result = _format_knowledge(knowledge, aspect)
        if result:
            return result

    # 降级：搜索 RAG / 本地文件
    aspect_map = {
        "overview": "概述",
        "history": "历史渊源",
        "technique": "技艺特点",
        "inheritors": "代表性传承人",
        "works": "代表作品",
        "learning": "学习资源",
    }
    aspect_cn = aspect_map.get(aspect, aspect)
    query = f"{name} {aspect_cn}"

    result = _search_rag(query) or _search_local_files(query)

    if result:
        return f"# {name} · {aspect_cn}\n\n{result}"

    # 最终降级：从 ihchina.cn 搜索元数据生成基本信息
    meta_result = await _get_knowledge_from_meta(name, aspect)
    if meta_result:
        return meta_result

    return (
        f"暂未找到「{name}」的{aspect_cn}相关信息。\n\n"
        "你可以：\n"
        f"1. 用 `search_heritage` 搜索「{name}」\n"
        f"2. 用 `get_heritage_info` 查看基本信息\n"
        "3. 将相关知识文档放入 knowledge/ 目录"
    )


async def _get_knowledge_from_meta(name: str, aspect: str) -> str:
    """从搜索元数据生成知识内容"""
    try:
        from heritage_master.data.crawler import search_heritage_data, _get_builtin_data

        items = await search_heritage_data(query=name, limit=10)

        # 如果搜索没有结果，尝试从内置数据中精确查找
        if not items:
            builtin = _get_builtin_data()
            items = [item for item in builtin if name in item.get("name", "") or item.get("name", "") in name]

        if not items:
            return ""

        # 找到最匹配的项目（必须精确匹配或包含关键词）
        matched = None
        for item in items:
            if item.get("name") == name:
                matched = item
                break
        if not matched:
            # 模糊匹配：项目名包含查询词或查询词包含项目名
            for item in items:
                item_name = item.get("name", "")
                if name in item_name or item_name in name:
                    matched = item
                    break
        if not matched:
            return ""  # 没有匹配项，不返回无关内容

        project_name = matched.get("name", name)
        category = matched.get("category", "")
        region = matched.get("region", "")
        batch = matched.get("batch", "")
        project_num = matched.get("project_num", "")
        protect_unit = matched.get("protect_unit", "")

        if aspect == "overview":
            lines = [f"# {project_name}\n"]
            lines.append(f"「{project_name}」是国家级非物质文化遗产项目。")
            if category:
                lines.append(f"\n**类别**：{category}")
            if region:
                lines.append(f"**地区**：{region}")
            if batch:
                lines.append(f"**批次**：{batch}")
            if project_num:
                lines.append(f"**项目编号**：{project_num}")
            if protect_unit:
                lines.append(f"**保护单位**：{protect_unit}")
            # 列出相关项目
            related = [i["name"] for i in items if i["name"] != project_name][:3]
            if related:
                lines.append(f"\n**相关项目**：{'、'.join(related)}")
            return "\n".join(lines)

        if aspect == "history":
            lines = [f"# {project_name} · 历史渊源\n"]
            lines.append(f"「{project_name}」的历史渊源信息正在整理中。")
            if batch:
                lines.append(f"\n该项目于{batch}列入国家级非物质文化遗产名录。")
            if region:
                lines.append(f"流传地区：{region}")
            return "\n".join(lines)

        if aspect == "technique":
            lines = [f"# {project_name} · 技艺特点\n"]
            lines.append(f"「{project_name}」的技艺特点信息正在整理中。")
            if category:
                lines.append(f"\n该项目属于{category}类别。")
            return "\n".join(lines)

        if aspect == "inheritors":
            lines = [f"# {project_name} · 代表性传承人\n"]
            lines.append(f"「{project_name}」的代表性传承人信息正在整理中。")
            if protect_unit:
                lines.append(f"\n保护单位：{protect_unit}")
            return "\n".join(lines)

        if aspect == "works":
            lines = [f"# {project_name} · 代表作品\n"]
            lines.append(f"「{project_name}」的代表作品信息正在整理中。")
            return "\n".join(lines)

        if aspect == "learning":
            lines = [f"# {project_name} · 学习资源\n"]
            lines.append(f"「{project_name}」的学习资源信息正在整理中。")
            if protect_unit:
                lines.append(f"\n可联系保护单位了解：{protect_unit}")
            return "\n".join(lines)

    except Exception:
        pass

    return ""


def _format_knowledge(k: dict, aspect: str) -> str:
    """将结构化知识格式化为可读文本"""
    name = k.get("name", "")

    if aspect == "overview":
        lines = [f"# {name}\n"]
        if k.get("description"):
            lines.append(k["description"])
        if k.get("category"):
            lines.append(f"\n**类别**：{k['category']}")
        region = k.get("region", [])
        if region:
            lines.append(f"**地区**：{'、'.join(region) if isinstance(region, list) else region}")
        if k.get("unesco"):
            lines.append(f"**UNESCO**：{k['unesco'].get('type', '')}（{k['unesco'].get('year', '')}年）")
        if k.get("status"):
            lines.append(f"**现状**：{k['status']}")
        return "\n".join(lines)

    if aspect == "history":
        origin = k.get("origin", {})
        if not origin:
            return ""
        lines = [f"# {name} · 历史渊源\n"]
        if origin.get("period"):
            lines.append(f"**起源时期**：{origin['period']}")
        if origin.get("place"):
            lines.append(f"**发源地**：{origin['place']}")
        if origin.get("founder"):
            lines.append(f"**创始人**：{origin['founder']}")
        if origin.get("reformer"):
            lines.append(f"**改革者**：{origin['reformer']}")
        if origin.get("event"):
            lines.append(f"**重要事件**：{origin['event']}")
        if origin.get("key_figure"):
            kf = origin["key_figure"]
            if isinstance(kf, list):
                kf = "、".join(kf)
            lines.append(f"**关键人物**：{kf}")
        return "\n".join(lines)

    if aspect == "technique":
        chars = k.get("characteristics", [])
        if not chars:
            return ""
        lines = [f"# {name} · 技艺特点\n"]
        for c in chars:
            lines.append(f"- {c}")
        schools = k.get("schools")
        if schools:
            lines.append("\n## 流派")
            if isinstance(schools, dict):
                for sname, svals in schools.items():
                    lines.append(f"- **{sname}**：{'、'.join(svals[:3])}")
            elif isinstance(schools, list):
                for s in schools:
                    lines.append(f"- {s}")
        return "\n".join(lines)

    if aspect == "inheritors":
        inheritors = k.get("inheritors", [])
        if not inheritors:
            return ""
        lines = [f"# {name} · 代表性传承人\n"]
        for h in inheritors:
            line = f"- **{h['name']}**"
            if h.get("title"):
                line += f"（{h['title']}）"
            if h.get("specialty"):
                line += f" — {h['specialty']}"
            lines.append(line)
        return "\n".join(lines)

    if aspect == "works":
        works = k.get("masterpieces", [])
        if not works:
            return ""
        lines = [f"# {name} · 代表作品\n"]
        for w in works:
            lines.append(f"- {w}")
        related = k.get("related", [])
        if related:
            lines.append(f"\n**相关项目**：{'、'.join(related)}")
        return "\n".join(lines)

    if aspect == "learning":
        lines = [f"# {name} · 学习资源\n"]
        learning = k.get("learning", [])
        if learning:
            for l in learning:
                lines.append(f"- {l}")
        status = k.get("status", "")
        if status:
            lines.append(f"\n**传承现状**：{status}")
        return "\n".join(lines) if len(lines) > 1 else ""

    return ""


async def add_knowledge_to_rag(file_path: str) -> str:
    """
    将文档添加到 RAG 知识库。

    Args:
        file_path: 文档文件路径（Markdown/TXT）

    Returns:
        操作结果
    """
    collection = _init_rag()
    if collection is None:
        return "RAG 知识库未启用。请安装 rag 依赖（pip install heritage-master[rag]）"

    path = Path(file_path)
    if not path.exists():
        return f"文件不存在：{file_path}"

    content = path.read_text(encoding="utf-8")

    # 分段（按段落拆分，过滤过短段落）
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip() and len(p.strip()) >= 20]

    if not paragraphs:
        return "文件内容为空或段落过短。"

    from heritage_master.data.local_embedding import embed_batch

    # 生成 ID、元数据和向量
    ids = [f"{path.stem}_{i}" for i in range(len(paragraphs))]
    metadatas = [{"source": path.name, "source_stem": path.stem, "paragraph_index": i} for i in range(len(paragraphs))]
    embeddings = embed_batch(paragraphs)

    collection.upsert(
        ids=ids,
        documents=paragraphs,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    return f"已将 {len(paragraphs)} 个段落添加到知识库（来源：{path.name}）"
