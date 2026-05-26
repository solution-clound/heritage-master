from __future__ import annotations

"""Milvus 向量存储层"""

from typing import Any, Dict, List, Optional

from heritage_master.config import settings


class MilvusStore:
    """Milvus 向量数据库存储"""

    def __init__(self):
        self._collection = None

    def _get_collection(self):
        """获取或创建 Collection 连接"""
        if self._collection is None:
            try:
                from pymilvus import connections, Collection
                connections.connect(
                    alias="default",
                    host=settings.milvus_host,
                    port=settings.milvus_port,
                )
                self._collection = Collection(settings.milvus_collection)
                self._collection.load()
            except ImportError:
                raise RuntimeError("pymilvus 未安装，请运行: pip install pymilvus")
        return self._collection

    def insert_texts(
        self,
        doc_ids: List[str],
        titles: List[str],
        contents: List[str],
        categories: List[str],
        doc_types: List[str],
        embeddings: List[List[float]],
    ) -> int:
        """批量插入向量数据"""
        collection = self._get_collection()
        data = [doc_ids, titles, contents, categories, doc_types, embeddings]
        result = collection.insert(data)
        collection.flush()
        return result.insert_count

    def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """向量相似度检索"""
        collection = self._get_collection()

        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 16},
        }

        filter_expr = f'category == "{category}"' if category else None

        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=filter_expr,
            output_fields=["doc_id", "title", "content", "category", "doc_type"],
        )

        hits = []
        for hit in results[0]:
            hits.append({
                "doc_id": hit.entity.get("doc_id"),
                "title": hit.entity.get("title"),
                "content": hit.entity.get("content"),
                "category": hit.entity.get("category"),
                "doc_type": hit.entity.get("doc_type"),
                "score": hit.score,
            })
        return hits

    def delete_by_ids(self, ids: List[int]) -> int:
        """按 ID 删除"""
        collection = self._get_collection()
        expr = f"id in {ids}"
        result = collection.delete(expr)
        return result.delete_count

    def get_stats(self) -> Dict[str, Any]:
        """获取 Collection 统计"""
        collection = self._get_collection()
        return {
            "collection": settings.milvus_collection,
            "count": collection.num_entities,
        }
