"""
统一异常处理体系

定义 HeritageException 业务异常层次 + 全局异常处理器。
所有 API 错误返回统一 JSON 格式：{code, message, trace_id, recoverable}
"""

from __future__ import annotations

import logging
import traceback
from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("heritage.errors")

# ─── Trace ID（每个请求唯一） ─────────────────────────────

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


# ─── 业务异常基类 ─────────────────────────────────────────

class HeritageException(Exception):
    """业务异常基类 — 所有可预见的业务错误都用这个或其子类"""

    def __init__(
        self,
        message: str,
        code: int = 400,
        recoverable: bool = False,
        detail: Any = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.recoverable = recoverable
        self.detail = detail


# ─── 具体业务异常 ─────────────────────────────────────────

class LLMTimeoutError(HeritageException):
    """LLM 调用超时"""
    def __init__(self, message: str = "大师正在思考中，请稍后重试"):
        super().__init__(message=message, code=503, recoverable=True)


class LLMRateLimitError(HeritageException):
    """LLM 服务限流"""
    def __init__(self, message: str = "大师太忙了，请稍后再来"):
        super().__init__(message=message, code=429, recoverable=True)


class ToolExecutionError(HeritageException):
    """工具调用失败"""
    def __init__(self, tool_name: str, reason: str):
        super().__init__(
            message=f"工具 {tool_name} 执行失败: {reason}",
            code=502,
            recoverable=True,
        )
        self.tool_name = tool_name


class ResourceNotFoundError(HeritageException):
    """资源不存在（非遗项目、用户、会话等）"""
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} '{identifier}' 不存在",
            code=404,
            recoverable=False,
        )


class AuthenticationError(HeritageException):
    """认证失败"""
    def __init__(self, message: str = "未授权：缺少或无效的认证信息"):
        super().__init__(message=message, code=401, recoverable=False)


class RateLimitExceeded(HeritageException):
    """API 请求限流"""
    def __init__(self, retry_after: int = 60):
        super().__init__(
            message="请求过于频繁，请稍后再试",
            code=429,
            recoverable=True,
        )
        self.retry_after = retry_after


class InputValidationError(HeritageException):
    """输入校验失败"""
    def __init__(self, message: str, detail: Any = None):
        super().__init__(message=message, code=422, recoverable=False, detail=detail)


# ─── 统一 JSON 响应构建 ───────────────────────────────────

def error_response(
    code: int,
    message: str,
    trace_id: str = "",
    recoverable: bool = False,
    detail: Any = None,
) -> JSONResponse:
    """构建统一错误 JSON"""
    body: dict[str, Any] = {
        "code": code,
        "message": message,
        "trace_id": trace_id,
        "recoverable": recoverable,
    }
    if detail is not None:
        body["detail"] = detail
    return JSONResponse(status_code=code, content=body)


# ─── 全局异常处理器注册 ───────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    """在 FastAPI app 上注册所有全局异常处理器"""

    @app.exception_handler(HeritageException)
    async def heritage_exception_handler(request: Request, exc: HeritageException):
        """处理所有 HeritageException 业务异常"""
        tid = trace_id_var.get("")
        logger.warning(
            "业务异常: %s | code=%d trace_id=%s",
            exc.message, exc.code, tid,
        )
        headers = {}
        if isinstance(exc, RateLimitExceeded):
            headers["Retry-After"] = str(exc.retry_after)
        return error_response(
            code=exc.code,
            message=exc.message,
            trace_id=tid,
            recoverable=exc.recoverable,
            detail=exc.detail,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理 Pydantic 入参校验失败 → 422"""
        tid = trace_id_var.get("")
        # 提取可读的校验错误信息
        errors = exc.errors()
        messages = []
        for err in errors:
            loc = " -> ".join(str(l) for l in err.get("loc", []))
            msg = err.get("msg", "校验失败")
            messages.append(f"{loc}: {msg}")
        readable = "; ".join(messages) if messages else "请求参数校验失败"

        logger.warning("入参校验失败: %s | trace_id=%s", readable, tid)
        return error_response(
            code=422,
            message=readable,
            trace_id=tid,
            recoverable=False,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """处理 FastAPI/Starlette HTTPException（404 等）"""
        tid = trace_id_var.get("")
        return error_response(
            code=exc.status_code,
            message=str(exc.detail),
            trace_id=tid,
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """兜底：处理所有未捕获异常 → 500"""
        tid = trace_id_var.get("")
        tb = traceback.format_exc()
        logger.error(
            "未捕获异常: %s | trace_id=%s\n%s",
            str(exc), tid, tb,
        )
        # 不暴露内部细节给客户端
        return error_response(
            code=500,
            message="服务器内部错误，请稍后重试",
            trace_id=tid,
            recoverable=True,
        )
