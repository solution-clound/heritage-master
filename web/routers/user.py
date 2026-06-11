"""用户 API 路由

提供注册、登录、用户信息、会话管理等接口。
登录成功后签发 JWT Token，后续请求通过 Token 识别身份。
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional

from heritage_master.tools import user_manager
from heritage_master.middleware.auth import create_jwt_token, decode_jwt_token

router = APIRouter()
security = HTTPBearer(auto_error=False)


# ─── 请求模型 ─────────────────────────────────────────

class RegisterRequest(BaseModel):
    nickname: str = Field(..., min_length=2, max_length=20)
    password: str = Field(..., min_length=4, max_length=100)


class LoginRequest(BaseModel):
    nickname: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


# ─── 依赖：从 JWT 获取当前用户 ────────────────────────

async def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """从 Authorization: Bearer <token> 中提取 user_id。
    无 token 或 token 无效时返回空字符串（允许匿名访问）。
    """
    if not credentials:
        return ""
    token = credentials.credentials
    user_id = decode_jwt_token(token)
    return user_id or ""


# ─── 注册 ─────────────────────────────────────────────

@router.post("/api/user/register")
async def api_register(req: RegisterRequest):
    """注册新用户，成功后返回 JWT Token"""
    result = user_manager.create_user(req.nickname.strip(), req.password)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    # 签发 JWT
    token = create_jwt_token(result["id"])
    return {
        "id": result["id"],
        "nickname": result["nickname"],
        "token": token,
    }


# ─── 登录 ─────────────────────────────────────────────

@router.post("/api/user/login")
async def api_login(req: LoginRequest):
    """用户登录，成功后返回 JWT Token"""
    result = user_manager.login_user(req.nickname.strip(), req.password)
    if result is None:
        raise HTTPException(status_code=401, detail="昵称或密码错误")
    # 签发 JWT
    token = create_jwt_token(result["id"])
    return {
        "id": result["id"],
        "nickname": result["nickname"],
        "token": token,
    }


# ─── 获取当前用户信息 ─────────────────────────────────

@router.get("/api/user/me")
async def api_get_me(user_id: str = Depends(get_current_user_id)):
    """获取当前登录用户信息（需 JWT）"""
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    user = user_manager.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {
        "id": user["id"],
        "nickname": user["nickname"],
        "created_at": user["created_at"],
        "last_active_at": user.get("last_active_at", ""),
    }


# ─── 获取用户公开信息 ─────────────────────────────────

@router.get("/api/user/info/{user_id}")
async def api_get_user(user_id: str):
    """获取指定用户公开信息"""
    user = user_manager.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {
        "id": user["id"],
        "nickname": user["nickname"],
        "created_at": user["created_at"],
    }


# ─── 会话管理 ─────────────────────────────────────────

@router.post("/api/user/session/start")
async def api_start_session(data: dict, user_id: str = Depends(get_current_user_id)):
    """开始新会话"""
    uid = user_id or data.get("user_id", "")
    master_id = data.get("master_id", "explorer")
    if not uid:
        raise HTTPException(status_code=400, detail="缺少 user_id")
    session_id = user_manager.start_session(uid, master_id)
    return {"session_id": session_id}


@router.post("/api/user/session/end")
async def api_end_session(session_id: str):
    """结束会话"""
    user_manager.end_session(session_id)
    return {"ok": True}


# ─── 会话历史 ─────────────────────────────────────────

@router.get("/api/user/{user_id}/history")
async def api_user_history(user_id: str, master_id: str = "", limit: int = 50):
    messages = user_manager.get_user_messages(user_id, master_id or "explorer", limit=limit)
    return {"messages": messages}


@router.get("/api/user/{user_id}/sessions")
async def api_user_sessions(user_id: str, master_id: str = "", limit: int = 20):
    sessions = user_manager.get_user_sessions(user_id, master_id, limit=limit)
    return {"conversations": sessions}


@router.get("/api/session/{session_id}/messages")
async def api_session_messages(session_id: str, limit: int = 50):
    messages = user_manager.get_recent_messages(session_id, limit=limit)
    return {"messages": messages}


@router.delete("/api/session/{session_id}")
async def api_delete_session(session_id: str):
    deleted = user_manager.delete_session(session_id)
    return {"deleted": deleted}


# ─── 用户画像 ─────────────────────────────────────────

@router.get("/api/user/{user_id}/profile/{master_id}")
async def api_get_profile(user_id: str, master_id: str):
    profile = user_manager.get_user_profile(user_id, master_id)
    if not profile:
        raise HTTPException(status_code=404, detail="画像不存在")
    return profile


@router.get("/api/user/{user_id}/profiles")
async def api_get_profiles(user_id: str):
    profiles = user_manager.get_all_profiles(user_id)
    return {"profiles": profiles}
