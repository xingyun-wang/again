"""RequestIDMiddleware 单元测试（M0 retro #3）。

覆盖：
- 每个请求生成唯一 X-Request-ID（uuid4().hex）
- contextvar 在 dispatch 期间被设置，结束后被 reset
- 异常路径也保证 X-Request-ID header 写回
- 与 health endpoint 集成：正常响应也带 header

注意：TestClient 默认 raise_server_exceptions=True，对"故意抛异常"的测试
用 raise_server_exceptions=False 关闭此行为（详见 errors.py）。
"""

# ruff: noqa: UP006, UP007, UP035, UP045, I001, F401
# Reason: 测试文件使用 typing.Dict / Optional 是为了兼容 Python 3.8（pydantic 2
# 在 3.8 上不能评估 dict[str, ...] | None 这种 PEP 604/585 语法）。项目
# pyproject.toml 写 >=3.11 但本地 dev box 是 3.8，与 app/core/errors.py 同理。
# I001 / F401: 这个文件里很多测试不使用 pytest fixtures，但保留 import 是为了将来扩展。
from __future__ import annotations

import re
from typing import Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from app.core.context import request_id_contextvar
from app.core.errors import register_exception_handlers
from app.core.middleware import RequestIDMiddleware


# === 静态行为测试 ===


def test_middleware_generates_uuid_hex_header() -> None:
    """每个响应的 X-Request-ID 是 32-char hex。"""
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/ping")
    def ping() -> PlainTextResponse:
        return PlainTextResponse("pong")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/ping")
    assert resp.status_code == 200
    rid = resp.headers.get("X-Request-ID")
    assert rid is not None
    assert re.fullmatch(r"[0-9a-f]{32}", rid), f"unexpected X-Request-ID: {rid!r}"


def test_middleware_unique_per_request() -> None:
    """两次请求得到不同的 X-Request-ID。"""
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/ping")
    def ping() -> PlainTextResponse:
        return PlainTextResponse("pong")

    client = TestClient(app, raise_server_exceptions=False)
    r1 = client.get("/ping")
    r2 = client.get("/ping")
    assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]


def test_middleware_sets_state_via_request_object() -> None:
    """request.state.request_id 与 X-Request-ID header 一致。"""
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/check")
    def check(request: Request) -> Dict[str, Optional[str]]:
        return {"state_id": request.state.request_id}

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/check")
    assert resp.status_code == 200
    body = resp.json()
    state_id = body["state_id"]
    header_id = resp.headers["X-Request-ID"]
    assert state_id == header_id


# === contextvar 生命周期 ===


def test_middleware_contextvar_set_during_request() -> None:
    """request 处理期间，request_id_contextvar 被 middleware 设为非 None。"""
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    captured: Dict[str, Optional[str]] = {}

    @app.get("/read")
    def read() -> Dict[str, Optional[str]]:
        captured["contextvar"] = request_id_contextvar.get()
        return {"rid": request_id_contextvar.get()}

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/read")
    assert resp.status_code == 200
    assert captured["contextvar"] is not None
    assert re.fullmatch(r"[0-9a-f]{32}", captured["contextvar"])  # type: ignore[arg-type]


def test_middleware_contextvar_isolation_between_requests() -> None:
    """同一 client 连续两次请求的 contextvar 值不同。"""
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    captured: list[Optional[str]] = []

    @app.get("/read")
    def read() -> Dict[str, Optional[str]]:
        rid = request_id_contextvar.get()
        captured.append(rid)
        return {"rid": rid}

    client = TestClient(app, raise_server_exceptions=False)
    client.get("/read")
    client.get("/read")
    assert len(captured) == 2
    assert captured[0] is not None
    assert captured[1] is not None
    assert captured[0] != captured[1]


# === 异常路径 header 仍写回（与 exception handler 集成）===


def test_middleware_writes_header_on_404() -> None:
    """路由 404 → middleware 仍写 X-Request-ID（异常被 ExceptionMiddleware 包装成 response）。"""
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    register_exception_handlers(app)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/nonexistent")
    assert resp.status_code == 404
    assert "X-Request-ID" in resp.headers


def test_middleware_writes_header_on_500() -> None:
    """未处理异常 → 500 + middleware 仍写 X-Request-ID。"""
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("kaboom")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500
    assert "X-Request-ID" in resp.headers


# === contextvar 单元测试 ===


def test_contextvar_default_is_none() -> None:
    """未在 request 上下文时，request_id_contextvar.get() 返回 None。"""
    # 不在 middleware 内，应为 None
    assert request_id_contextvar.get() is None


def test_contextvar_set_and_reset() -> None:
    """手动 set / reset 行为正确。"""
    token = request_id_contextvar.set("manual-id")
    try:
        assert request_id_contextvar.get() == "manual-id"
    finally:
        request_id_contextvar.reset(token)
    assert request_id_contextvar.get() is None