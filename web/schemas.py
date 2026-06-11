"""
统一请求/响应 Pydantic 模型

所有 API 端点使用这些模型做入参校验和响应格式化。
统一响应格式：{code, message, data, trace_id, latency_ms}
"""

from __future__ import annotations

import time
import uuid
from contextvars import ContextVar
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

# --- Trace ID 上下文 --------------------------------------------

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def get_trace_id() -> str:
    """获取当前请求的 trace_id"""
    tid = trace_id_var.get("")
    if not tid:
        tid = uuid.uuid4().hex[:16]
        trace_id_var.set(tid)
    return tid


# --- 统一响应模型 ------------------------------------------------

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""

    code: int = Field(default=200, description="业务状态码")
    message: str = Field(default="ok", description="响应消息")
    data: Optional[T] = Field(default=None, description="响应数据")
    trace_id: str = Field(default="", description="请求追踪 ID")
    latency_ms: int = Field(default=0, description="处理耗时(毫秒)")

    @classmethod
    def success(
        cls,
        data: Any = None,
        message: str = "ok",
        latency_ms: int = 0,
    ) -> "ApiResponse":
        """构建成功响应"""
        return cls(
            code=200,
            message=message,
            data=data,
            trace_id=get_trace_id(),
            latency_ms=latency_ms,
        )

    @classmethod
    def error(
        cls,
        code: int = 500,
        message: str = "服务器内部错误",
        detail: Any = None,
    ) -> "ApiResponse":
        """构建错误响应"""
        return cls(
            code=code,
            message=message,
            data=detail,
            trace_id=get_trace_id(),
        )


# --- 计时器工具 --------------------------------------------------

class LatencyTimer:
    """请求计时器，用于记录处理耗时"""

    def __init__(self) -> None:
        self._start = time.perf_counter()

    def elapsed_ms(self) -> int:
        """返回已过去的时间（毫秒）"""
        return int((time.perf_counter() - self._start) * 1000)


# --- 通用请求模型 ------------------------------------------------

class AgentRequest(BaseModel):
    """Agent 对话请求"""
    message: str = Field(
        ..., min_length=1, max_length=2000, description="用户消息"
    )
    session_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="会话 ID（不传则自动生成）",
    )
    master_id: str = Field(
        default="ye_hanzhong", description="大师 ID"
    )
    stream: bool = Field(
        default=False, description="是否流式输出",
    )


class SearchRequest(BaseModel):
    """非遗搜索请求"""
    query: str = Field(default="", max_length=200, description="搜索关键词")
    category: str = Field(default="", description="非遗类别")
    region: str = Field(default="", description="地区")
    limit: int = Field(default=10, ge=1, le=100, description="返回数量上限")


class VenueSearchRequest(BaseModel):
    """场馆搜索请求"""
    city: str = Field(..., min_length=1, max_length=50, description="城市名")
    keyword: str = Field(default="非遗", max_length=100, description="搜索关键词")
    lng: Optional[float] = Field(default=None, description="经度")
    lat: Optional[float] = Field(default=None, description="纬度")
    radius: int = Field(default=5000, ge=100, le=50000, description="搜索半径(米)")
    limit: int = Field(default=10, ge=1, le=50, description="返回数量上限")


class ForumPostRequest(BaseModel):
    """论坛发帖请求"""
    title: str = Field(..., min_length=1, max_length=200, description="帖子标题")
    body: str = Field(..., min_length=1, max_length=10000, description="帖子内容")
    category: str = Field(
        default="experience",
        description="分类",
        pattern=r"^(experience|guide|qna|stories|events)$",
    )


class ForumReplyRequest(BaseModel):
    """论坛回复请求"""
    body: str = Field(..., min_length=1, max_length=5000, description="回复内容")


class FeedbackRequest(BaseModel):
    """用户反馈请求"""
    trace_id: str = Field(..., description="被评价请求的 trace_id")
    accepted: bool = Field(..., description="用户是否接受结果")
    comment: str = Field(default="", max_length=500, description="用户评论")


class LoginRequest(BaseModel):
    """登录请求（生成 JWT Token）"""
    user_id: str = Field(..., min_length=1, max_length=100, description="用户 ID")
    secret: str = Field(..., description="登录密钥")
