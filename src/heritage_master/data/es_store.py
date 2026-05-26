from __future__ import annotations

"""Elasticsearch 存储层 - 非遗文献全文检索"""

from typing import Any, Dict, List, Optional

from heritage_master.config import settings


class ESStore:
    """Elasticsearch 存储"""

    def __init__(self):
        self._es = None

    def _get_es(self):
        """获取 ES 连接"""
        if self._es is None:
            try:
                from elasticsearch import Elasticsearch
                self._es = Elasticsearch(settings.es_host)
            except ImportError:
                raise RuntimeError("elasticsearch 未安装，请运行: pip install elasticsearch")
        return self._es

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        region: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """全文检索"""
        es = self._get_es()

        must = []
        filters = []

        if query:
            must.append({
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "content"],
                    "type": "best_fields",
                }
            })

        if category:
            filters.append({"term": {"category": category}})
        if region:
            filters.append({"term": {"region": region}})

        body = {
            "query": {
                "bool": {
                    "must": must if must else [{"match_all": {}}],
                    "filter": filters,
                }
            },
            "size": limit,
        }

        try:
            resp = es.search(index=settings.es_index, body=body)
            return [
                {
                    "id": hit["_id"],
                    "score": hit["_score"],
                    **hit["_source"],
                }
                for hit in resp["hits"]["hits"]
            ]
        except Exception as e:
            print(f"[ES] 搜索失败: {e}")
            return []

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """精确获取文档"""
        es = self._get_es()
        try:
            resp = es.get(index=settings.es_index, id=doc_id)
            return {"id": resp["_id"], **resp["_source"]}
        except Exception:
            return None

    def bulk_index(self, documents: List[Dict[str, Any]]) -> int:
        """批量索引"""
        from elasticsearch import helpers

        es = self._get_es()
        actions = [
            {
                "_index": settings.es_index,
                "_id": doc.get("id", doc.get("title", "")),
                "_source": doc,
            }
            for doc in documents
        ]
        success, _ = helpers.bulk(es, actions, raise_on_error=False)
        return success

    def suggest(self, prefix: str, field: str = "title") -> List[str]:
        """搜索建议"""
        es = self._get_es()
        body = {
            "suggest": {
                "title_suggest": {
                    "prefix": prefix,
                    "completion": {
                        "field": f"{field}.suggest",
                        "size": 5,
                    },
                }
            }
        }
        try:
            resp = es.search(index=settings.es_index, body=body)
            return [
                s["text"]
                for s in resp.get("suggest", {}).get("title_suggest", [{}])[0].get("options", [])
            ]
        except Exception:
            return []
