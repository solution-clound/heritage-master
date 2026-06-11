"""
令牌桶限流中间件 — 支持 Redis（生产）和内存（开发）两种后端

用法：在 FastAPI app 上以 @app.middleware("http") 方式注册 rate_limit_middleware。
当 settings.redis_enabled=True 时使用 Redis Lua 脚本（跨实例共享），
否则回退到内存令牌桶（重启丢失，仅单实例可用）。
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("heritage.rate_limit")

# --- 抽象接口 ---------------------------------------------------

class RateLimiterBackend(ABC):
    """限流后端抽象接口"""

    @abstractmethod
    async def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """判断请求是否允许，返回 True=放行 / False=限流"""
        ...

    @abstractmethod
    async def close(self) -> None:
        """清理资源"""
        ...


# --- 内存后端（开发环境） ----------------------------------------

class InMemoryRateLimiter(RateLimiterBackend):
    """基于内存的令牌桶限流"""

    def __init__(self) -> None:
        # key -> {"tokens": float, "last_refill": float}
        self.buckets: dict[str, dict] = defaultdict(
            lambda: {"tokens": 0.0, "last_refill": 0.0}
        )

    async def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.time()
        bucket = self.buckets[key]

        # 令牌补充
        elapsed = now - bucket["last_refill"]
        bucket["tokens"] = min(
            max_requests,
            bucket["tokens"] + elapsed * max_requests / window_seconds,
        )
        bucket["last_refill"] = now

        # 消耗令牌
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True
        return False

    async def close(self) -> None:
        self.buckets.clear()


# --- Redis 后端（生产环境） -------------------------------------

# Lua 脚本：原子执行令牌桶算法
_REDIS_LUA_SCRIPT = """
local key = KEYS[1]
local max_requests = tonumber(ARGV[1])
local window_seconds = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or max_requests
local last_refill = tonumber(bucket[2]) or 0

-- 令牌补充
if last_refill > 0 then
    local elapsed = now - last_refill
    tokens = math.min(max_requests, tokens + elapsed * max_requests / window_seconds)
end

local allowed = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
end

redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
redis.call('EXPIRE', key, window_seconds * 2)

return allowed
"""


class RedisRateLimiter(RateLimiterBackend):
    """基于 Redis Lua 脚本的令牌桶限流"""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis = None
        self._script_sha: Optional[str] = None

    async def _ensure_client(self):
        if self._redis is None:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
            # 预加载 Lua 脚本
            self._script_sha = await self._redis.script_load(_REDIS_LUA_SCRIPT)
        return self._redis

    async def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        try:
            r = await self._ensure_client()
            now = time.time()
            result = await r.evalsha(
                self._script_sha, 1, key, max_requests, window_seconds, now
            )
            return int(result) == 1
        except Exception as e:
            logger.warning("Redis 限流异常，降级放行: %s", e)
            return True  # Redis 故障时降级放行，不阻断用户

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None


# --- 限流规则 ---------------------------------------------------

RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/agent": (10, 60),              # 每分钟 10 次
    "/api/agent/graph": (10, 60),
    "/api/agent/graph/stream": (10, 60),
    "/api/ask": (20, 60),               # 每分钟 20 次
    "/api/trip": (5, 60),               # 每分钟 5 次
    "/api/search": (30, 60),            # 每分钟 30 次（只读，放宽）
    "/api/venue": (30, 60),             # 每分钟 30 次
    "/api/forum": (15, 60),             # 每分钟 15 次
    "/api/feedback": (10, 60),          # 每分钟 10 次
}


def _match_rate_limit(path: str) -> Optional[tuple[int, int]]:
    """返回匹配到的限流规则，优先最长前缀匹配"""
    best: Optional[tuple[str, tuple[int, int]]] = None
    for prefix, rule in RATE_LIMITS.items():
        if path == prefix or path.startswith(prefix + "/"):
            if best is None or len(prefix) > len(best[0]):
                best = (prefix, rule)
    return best[1] if best else None


def get_client_ip(request: Request) -> str:
    """优先取 X-Forwarded-For，否则取 client.host"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# --- 全局后端实例 -----------------------------------------------

_backend: Optional[RateLimiterBackend] = None


async def init_rate_limiter(redis_url: Optional[str] = None) -> None:
    """初始化限流后端（在 app lifespan 中调用）"""
    global _backend
    if redis_url:
        _backend = RedisRateLimiter(redis_url)
        logger.info("限流后端: Redis (%s)", redis_url)
    else:
        _backend = InMemoryRateLimiter()
        logger.info("限流后端: 内存（开发模式）")


async def close_rate_limiter() -> None:
    """关闭限流后端（在 app lifespan 中调用）"""
    global _backend
    if _backend:
        await _backend.close()
        _backend = None


# --- FastAPI 中间件 ---------------------------------------------

async def rate_limit_middleware(request: Request, call_next):
    # 跳过 OPTIONS（CORS preflight）
    if request.method == "OPTIONS":
        return await call_next(request)

    # 跳过静态文件和健康检查
    path: str = request.url.path
    if not path.startswith("/api/"):
        return await call_next(request)

    # 跳过健康检查端点
    if path in ("/health", "/ready"):
        return await call_next(request)

    rule = _match_rate_limit(path)
    if rule is None:
        return await call_next(request)

    if _backend is None:
        # 后端未初始化，放行（启动期间的安全兜底）
        return await call_next(request)

    max_requests, window_seconds = rule
    # 按 IP + 路径限流；如果有 user_id 也可以加入 key
    client_key = f"rl:{get_client_ip(request)}:{path}"

    allowed = await _backend.is_allowed(client_key, max_requests, window_seconds)
    if not allowed:
        logger.warning("限流触发: ip=%s path=%s", get_client_ip(request), path)
        return JSONResponse(
            status_code=429,
            content={
                "detail": "请求过于频繁，请稍后再试",
                "retry_after": window_seconds,
            },
            headers={"Retry-After": str(window_seconds)},
        )

    return await call_next(request)
