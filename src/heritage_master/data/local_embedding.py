from __future__ import annotations

"""本地 Embedding 模块 - 使用 sentence-transformers 进行文本向量化"""

from typing import Dict, List, Optional

from heritage_master.config import settings

# 模型缓存：避免重复加载
_model_cache: Dict[str, object] = {}


def _get_model(model_name: Optional[str] = None, device: Optional[str] = None):
    """
    加载 sentence-transformers 模型（带缓存）。

    Args:
        model_name: 模型名称，默认使用配置中的 embedding_model
        device: 运算设备，默认使用配置中的 embedding_device

    Returns:
        SentenceTransformer 模型实例
    """
    from sentence_transformers import SentenceTransformer

    model_name = model_name or settings.embedding_model
    device = device or settings.embedding_device

    cache_key = f"{model_name}:{device}"
    if cache_key not in _model_cache:
        _model_cache[cache_key] = SentenceTransformer(model_name, device=device)
    return _model_cache[cache_key]


def embed_text(text: str, model_name: Optional[str] = None, device: Optional[str] = None) -> List[float]:
    """
    将单条文本向量化。

    Args:
        text: 输入文本
        model_name: 模型名称（可选）
        device: 运算设备（可选）

    Returns:
        向量列表
    """
    model = _get_model(model_name, device)
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def embed_batch(
    texts: List[str],
    model_name: Optional[str] = None,
    device: Optional[str] = None,
    batch_size: int = 32,
    show_progress: bool = False,
) -> List[List[float]]:
    """
    批量文本向量化。

    Args:
        texts: 输入文本列表
        model_name: 模型名称（可选）
        device: 运算设备（可选）
        batch_size: 批处理大小
        show_progress: 是否显示进度条

    Returns:
        向量列表
    """
    model = _get_model(model_name, device)
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        normalize_embeddings=True,
    )
    return embeddings.tolist()


# ─── 简易内存缓存 ──────────────────────────────────────
_embedding_cache: Dict[str, List[float]] = {}


def embed_text_cached(text: str, model_name: Optional[str] = None, device: Optional[str] = None) -> List[float]:
    """
    带缓存的单条文本向量化。相同文本不会重复计算。

    Args:
        text: 输入文本
        model_name: 模型名称（可选）
        device: 运算设备（可选）

    Returns:
        向量列表
    """
    cache_key = f"{model_name}:{device}:{text}"
    if cache_key not in _embedding_cache:
        _embedding_cache[cache_key] = embed_text(text, model_name, device)
    return _embedding_cache[cache_key]


def clear_cache():
    """清空向量缓存"""
    global _embedding_cache
    _embedding_cache.clear()
