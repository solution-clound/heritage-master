"""共享 HTTP 客户端 — 复用连接池，避免每次请求重建 TCP/TLS"""

from __future__ import annotations

from typing import Optional

import httpx

# 模块级单例，惰性初始化
_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    """获取共享的 AsyncClient（连接池复用）"""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=15,
            trust_env=False,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client


async def close_client():
    """关闭共享客户端（应用退出时调用）"""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
