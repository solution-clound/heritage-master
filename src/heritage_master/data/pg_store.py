from __future__ import annotations

"""PostgreSQL 存储层 - 替代 SQLite 的用户/会话/修行数据存储"""

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from heritage_master.config import settings

# 连接池（延迟初始化）
_pool = None


async def get_pool():
    """获取或创建 asyncpg 连接池"""
    global _pool
    if _pool is None:
        try:
            import asyncpg
            _pool = await asyncpg.create_pool(
                host=settings.pg_host,
                port=settings.pg_port,
                database=settings.pg_database,
                user=settings.pg_user,
                password=settings.pg_password,
                min_size=2,
                max_size=10,
            )
        except ImportError:
            raise RuntimeError("asyncpg 未安装，请运行: pip install asyncpg")
    return _pool


@asynccontextmanager
async def get_pg_conn():
    """获取 PostgreSQL 连接的异步上下文管理器"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


async def close_pool():
    """关闭连接池"""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
