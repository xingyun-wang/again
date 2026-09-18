"""自定义中间件。

RequestIDMiddleware:
- 每个 HTTP 请求生成唯一 request_id（uuid4().hex）
- 写入 request_id_contextvar（供 logging / exception handler 读取）
- 写入响应 header `X-Request-ID`，便于客户端关联日志
- 同时挂到 request.state.request_id，方便路由 / 依赖函数读取
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.context import request_id_contextvar


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个 HTTP 请求注入唯一 request_id。"""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        rid = uuid4().hex
        token = request_id_contextvar.set(rid)
        # 也挂到 request.state，路由 / 依赖函数可以同步访问
        request.state.request_id = rid
        try:
            response = await call_next(request)
        finally:
            request_id_contextvar.reset(token)
        # call_next 已返回（异常已被 ExceptionMiddleware 捕获并包装成 response），
        # 此时给响应追加 header。Exception handler 在自己的 response 上也会写，
        # 两边写的是同一个值，无副作用。
        response.headers["X-Request-ID"] = rid
        return response