"""
认证中间件 — 支持多 API Key 和 JWT Token

认证策略（按优先级）：
1. Bearer Token (JWT) → 解码获取 user_id
2. X-API-Key header   → 匹配预配置的 key→user 映射
3. 都没有             → 返回 401

开发模式：HERITAGE_API_KEYS 未设置时跳过认证（全部放行）。
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("heritage.auth")

# --- 配置解析 ---------------------------------------------------

# 多 API Key 配置，格式：
#   HERITAGE_API_KEYS={"key-abc-123": "user_alice", "key-def-456": "user_bob"}
# 或简化格式（无用户映射时使用默认用户 ID）：
#   HERITAGE_API_KEY=your-secret-key

_API_KEYS: dict[str, str] = {}  # key -> user_id


def _load_api_keys() -> dict[str, str]:
    """加载 API Key 配置"""
    keys_raw = os.getenv("HERITAGE_API_KEYS", "")
    if keys_raw:
        try:
            return json.loads(keys_raw)
        except json.JSONDecodeError:
            logger.warning("HERITAGE_API_KEYS JSON 解析失败，忽略")
            return {}

    # 单 key 兼容模式
    single_key = os.getenv("HERITAGE_API_KEY", "")
    if single_key:
        return {single_key: "default_user"}

    return {}


def reload_api_keys() -> None:
    """重新加载 API Key（支持运行时刷新）"""
    global _API_KEYS
    _API_KEYS = _load_api_keys()
    if _API_KEYS:
        logger.info("已加载 %d 个 API Key", len(_API_KEYS))


# 启动时加载
reload_api_keys()


# --- JWT 支持 ---------------------------------------------------

# JWT 密钥（生产环境应从环境变量读取）
_JWT_SECRET = os.getenv("HERITAGE_JWT_SECRET", "")
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRE_SECONDS = 86400  # 24 小时


def create_jwt_token(user_id: str) -> str:
    """生成 JWT Token（供登录接口使用）"""
    if not _JWT_SECRET:
        raise RuntimeError("HERITAGE_JWT_SECRET 未配置，无法生成 JWT")

    import jwt
    payload = {
        "sub": user_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + _JWT_EXPIRE_SECONDS,
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def decode_jwt_token(token: str) -> Optional[str]:
    """解码 JWT Token，返回 user_id 或 None"""
    if not _JWT_SECRET:
        return None
    try:
        import jwt
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        return payload.get("sub")
    except Exception as e:
        logger.debug("JWT 解码失败: %s", e)
        return None


# --- 认证逻辑 ---------------------------------------------------

# 不需要认证的公共路径前缀
_PUBLIC_PREFIXES: tuple[str, ...] = (
    "/assets",
    "/static",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/health",
    "/ready",
    "/api/map-config",
    # 用户认证接口（无需 token）
    "/api/user/register",
    "/api/user/login",
    # 公开只读接口
    "/api/search",
    "/api/venue",
    "/api/categories",
    "/api/graph/explore",
)


@dataclass
class AuthResult:
    """认证结果"""
    authenticated: bool
    user_id: str = ""
    method: str = ""  # "jwt" / "api_key" / "none"


def authenticate_request(request: Request) -> AuthResult:
    """执行认证，返回认证结果"""

    # 无配置 = 开发模式，全部放行
    if not _API_KEYS and not _JWT_SECRET:
        return AuthResult(authenticated=True, user_id="dev_user", method="none")

    # 1. 尝试 JWT Bearer Token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user_id = decode_jwt_token(token)
        if user_id:
            return AuthResult(authenticated=True, user_id=user_id, method="jwt")

    # 2. 尝试 API Key
    api_key = request.headers.get("X-API-Key", "")
    if api_key and api_key in _API_KEYS:
        user_id = _API_KEYS[api_key]
        return AuthResult(authenticated=True, user_id=user_id, method="api_key")

    # 3. 认证失败
    return AuthResult(authenticated=False)


# --- FastAPI 中间件 ---------------------------------------------

async def auth_middleware(request: Request, call_next):
    # 跳过 OPTIONS（CORS preflight）
    if request.method == "OPTIONS":
        return await call_next(request)

    path: str = request.url.path

    # 跳过非 API 路径和公共路径
    if not path.startswith("/api/"):
        return await call_next(request)

    for prefix in _PUBLIC_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return await call_next(request)

    # 执行认证
    result = authenticate_request(request)

    if not result.authenticated:
        return JSONResponse(
            status_code=401,
            content={
                "code": 401,
                "message": "未授权：缺少或无效的认证信息",
                "recoverable": False,
            },
        )

    # 将 user_id 注入 request.state，后续 router 可直接使用
    request.state.user_id = result.user_id
    request.state.auth_method = result.method

    return await call_next(request)
