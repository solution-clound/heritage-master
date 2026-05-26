from __future__ import annotations

"""Embedding 客户端 - 文本向量化接口"""

from typing import List, Optional

import httpx

from heritage_master.config import settings


class EmbeddingClient:
    """调用 Embedding API 生成文本向量"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "text-embedding-3-small",
    ) -> None:
        self._api_key = api_key or settings.llm_api_key
        self._base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._model = model

    async def embed_text(self, text: str) -> Optional[List[float]]:
        """单条文本向量化"""
        results = await self.embed_batch([text])
        return results[0] if results else None

    async def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """批量文本向量化"""
        if not self._api_key:
            return [None] * len(texts)

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self._base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "input": texts,
                    },
                )
                data = resp.json()
                # 按 index 排序
                sorted_data = sorted(data["data"], key=lambda x: x["index"])
                return [item["embedding"] for item in sorted_data]
        except Exception as e:
            print(f"[Embedding] 调用失败: {e}")
            return [None] * len(texts)
