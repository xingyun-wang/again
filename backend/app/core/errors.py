"""统一错误响应 + exception handlers（M0 retro #2 基建）。

- ErrorResponse：所有 4xx/5xx 响应的统一 schema
- http_exception_handler：处理 StarletteHTTPException（含 FastAPI HTTPException 子类）
- exception_handler：兜底，捕获未处理的 Exception
- 生产模式（APP_ENV=production）：不漏 stack trace 到前端，只 logger.exception(...) 写日志
- 开发模式（APP_ENV=development）：details.stack 保留，便于排查
- request_id 从 request_id_contextvar 读取，与 RequestIDMiddleware 配合

调用入口：register_exception_handlers(app)，由 main.create_app() 调用。
"""

# ruff: noqa: UP006, UP007, UP035, UP045
# Reason: 使用 typing 模块的 Dict/Optional 是为了兼容 Python 3.8（pydantic 2 不能
# 评估 dict[str, ...] | None 这种 PEP 604/585 语法）。项目 pyproject.toml 写 >=3.11
# 但本地 dev box 是 3.8，这个文件的成本主要是"开发期能跑"。
# UP035/UP045 同理；待 dev env 升 3.11 后可一并清掉。
from __future__ import annotations

import logging
import traceback
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.context import request_id_contextvar

logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    """统一错误响应 schema。

    所有 4xx/5xx 响应都长这样，方便前端按统一格式处理。
    """

    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None


# 已知 HTTP status → error_code 的固定映射。
# 不在表里的 status code 用 INTERNAL_ERROR（5xx）或 HTTP_<code>（其他）。
_HTTP_ERROR_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
}


def _http_error_code(status_code: int) -> str:
    if status_code in _HTTP_ERROR_CODES:
        return _HTTP_ERROR_CODES[status_code]
    if 500 <= status_code < 600:
        return "INTERNAL_ERROR"
    return f"HTTP_{status_code}"


def _is_dev() -> bool:
    return get_settings().app_env.lower() == "development"


def _build_response_headers(rid: Optional[str]) -> Optional[Dict[str, str]]:
    """构造响应 header（X-Request-ID）。"""
    if rid:
        return {"X-Request-ID": rid}
    return None


def _resolve_request_id(request: Request) -> Optional[str]:
    """优先 request.state.request_id（由 RequestIDMiddleware 设），回落到 contextvar。

    背景：Starlette 0.38.x + BaseHTTPMiddleware 的 BaseHTTPMiddleware.task_group
    会在 dispatch 完成后仍按调度顺序启动新任务，导致 contextvar 在 exception handler
    调度到时已被 reset。request.state 是同一个 Request 对象上的属性，
    不受 asyncio 任务调度影响。这个回退路径是针对该环境的。
    """
    state_rid: Optional[str] = getattr(request.state, "request_id", None)
    if state_rid:
        return state_rid
    return request_id_contextvar.get()


def register_exception_handlers(app: FastAPI) -> None:
    """注册 exception handlers 到 FastAPI app。

    用装饰器形式（而不是 app.add_exception_handler(...)），以便保留异常类型的 narrowing
    （Starlette 的 add_exception_handler 签名要求 Callable[[Request, Exception], ...]）。
    """
    # 顺序：FastAPI/Starlette 按 exc 类型在 MRO 中匹配，
    # StarletteHTTPException handler 优先于 Exception handler。

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        """处理 StarletteHTTPException（覆盖 FastAPI HTTPException 子类）。

        包括：
        - 路由 404 / 405
        - 业务代码 raise HTTPException(...)
        - FastAPI RequestValidationError 转换后的 422
        """
        rid = _resolve_request_id(request)
        message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)

        details: Optional[Dict[str, Any]] = None
        if _is_dev():
            details = {"status_code": exc.status_code}

        body = ErrorResponse(
            error_code=_http_error_code(exc.status_code),
            message=message,
            details=details,
            request_id=rid,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=body.model_dump(),
            headers=_build_response_headers(rid),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """兜底：捕获所有未处理的 Exception，统一返回 500。"""
        rid = _resolve_request_id(request)
        # 写完整 traceback 到日志（生产模式也不漏这里）
        logger.exception(
            "未处理异常 path=%s method=%s",
            request.url.path,
            request.method,
            exc_info=exc,
        )

        details: Optional[Dict[str, Any]] = None
        if _is_dev():
            details = {"stack": traceback.format_exc()}

        body = ErrorResponse(
            error_code="INTERNAL_ERROR",
            message="Internal server error",
            details=details,
            request_id=rid,
        )
        return JSONResponse(
            status_code=500,
            content=body.model_dump(),
            headers=_build_response_headers(rid),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """FastAPI 验证错误（Pydantic 校验失败 / body 解析失败） → 422 + ErrorResponse。

        FastAPI 默认会把 RequestValidationError 包成 {"detail": [...]} 返回，
        这里重写为我们的统一 schema。
        """
        rid = _resolve_request_id(request)

        details: Optional[Dict[str, Any]] = None
        if _is_dev():
            # exc.errors() 是 Pydantic 错误详情列表；直接序列化
            details = {"errors": exc.errors()}

        body = ErrorResponse(
            error_code="VALIDATION_ERROR",
            message="Request validation failed",
            details=details,
            request_id=rid,
        )
        return JSONResponse(
            status_code=422,
            content=body.model_dump(),
            headers=_build_response_headers(rid),
        )