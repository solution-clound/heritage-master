"""
健康检查端点

GET /health  -> 快速存活检查（给 load balancer 用）
GET /ready   -> 详细就绪检查（检查各组件连通性）
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger("heritage.health")

router = APIRouter(tags=["health"])

# 服务启动时间（在 lifespan 中设置）
_start_time: float = 0.0


def set_start_time(t: float) -> None:
    global _start_time
    _start_time = t


# --- 组件检查函数 ------------------------------------------------

async def _check_llm() -> dict[str, Any]:
    """检查 LLM 配置是否存在"""
    try:
        from heritage_master.config import settings
        if not settings.llm_api_key:
            return {"status": "down", "error": "API key not configured"}
        return {
            "status": "up",
            "provider": settings.llm_provider,
            "model": settings.llm_model,
        }
    except Exception as e:
        return {"status": "down", "error": str(e)}


async def _check_redis() -> dict[str, Any]:
    """检查 Redis 连通性"""
    try:
        from heritage_master.config import settings
        if not settings.redis_enabled:
            return {"status": "disabled"}
        import redis.asyncio as aioredis
        if settings.redis_password:
            url = (
                "redis://:"
                + settings.redis_password
                + "@"
                + settings.redis_host
                + ":"
                + str(settings.redis_port)
                + "/"
                + str(settings.redis_db)
            )
        else:
            url = (
                "redis://"
                + settings.redis_host
                + ":"
                + str(settings.redis_port)
                + "/"
                + str(settings.redis_db)
            )
        r = aioredis.from_url(url)
        t0 = time.time()
        await r.ping()
        latency = int((time.time() - t0) * 1000)
        await r.aclose()
        return {"status": "up", "latency_ms": latency}
    except Exception as e:
        return {"status": "down", "error": str(e)}


async def _check_neo4j() -> dict[str, Any]:
    """检查 Neo4j 连通性"""
    try:
        from heritage_master.config import settings
        if not settings.neo4j_password:
            return {"status": "disabled", "reason": "password not set"}
        from neo4j import AsyncGraphDatabase
        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        t0 = time.time()
        async with driver.session() as session:
            await session.run("RETURN 1")
        latency = int((time.time() - t0) * 1000)
        await driver.close()
        return {"status": "up", "latency_ms": latency}
    except Exception as e:
        return {"status": "down", "error": str(e)}


async def _check_sqlite() -> dict[str, Any]:
    """检查 SQLite 数据库可读"""
    try:
        from heritage_master.config import settings
        from pathlib import Path
        db_path = Path(settings.sqlite_path)
        if not db_path.exists():
            return {"status": "down", "error": "数据库文件不存在"}
        return {"status": "up", "path": str(db_path)}
    except Exception as e:
        return {"status": "down", "error": str(e)}


# --- 路由端点 ------------------------------------------------

@router.get("/health")
async def health_liveness():
    """存活探针 -- 不检查外部依赖，只证明进程还活着"""
    return {"status": "alive", "uptime_seconds": int(time.time() - _start_time)}


@router.get("/ready")
async def health_readiness():
    """就绪探针 -- 并行检查所有组件连通性"""

    checks = await asyncio.gather(
        _check_llm(),
        _check_redis(),
        _check_neo4j(),
        _check_sqlite(),
        return_exceptions=True,
    )

    components = {}
    labels = ["llm", "redis", "neo4j", "sqlite"]
    for label, result in zip(labels, checks):
        if isinstance(result, Exception):
            components[label] = {"status": "down", "error": str(result)}
        else:
            components[label] = result

    # 判定整体状态
    statuses = [c.get("status", "down") for c in components.values()]
    if all(s in ("up", "disabled") for s in statuses):
        overall = "healthy"
    elif any(s == "down" for s in statuses):
        core_down = (
            components.get("llm", {}).get("status") == "down"
            or components.get("sqlite", {}).get("status") == "down"
        )
        overall = "unhealthy" if core_down else "degraded"
    else:
        overall = "degraded"

    status_code = 200 if overall != "unhealthy" else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall,
            "uptime_seconds": int(time.time() - _start_time),
            "components": components,
        },
    )
