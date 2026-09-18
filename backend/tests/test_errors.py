"""统一错误响应 + exception handlers 测试（M0 retro #2）。

覆盖：
- 404 / 422 / 业务 HTTPException → 统一 ErrorResponse schema
- 5xx → 不漏 stack trace 到响应体（生产模式）
- request_id 在 body 和 X-Request-ID header 中一致
- production 模式隐藏 stack；development 模式保留 details.stack

注意：TestClient 默认 raise_server_exceptions=True，会把未处理异常透传到测试代码。
对"故意让 route 抛异常"的测试用 raise_server_exceptions=False 关闭此行为，
否则测试会收到原始异常而非我们 handler 返回的 500 响应。
"""

# ruff: noqa: UP006, UP007, UP035, UP045
# Reason: 测试文件使用 typing.Dict / Optional 是为了兼容 Python 3.8（pydantic 2
# 在 3.8 上不能评估 dict[str, ...] | None 这种 PEP 604/585 语法）。项目
# pyproject.toml 写 >=3.11 但本地 dev box 是 3.8，与 app/core/errors.py 同理。
from __future__ import annotations

import re
from typing import Dict  # Python 3.8 + pydantic 2 兼容

import pydantic
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import ErrorResponse, register_exception_handlers
from app.core.middleware import RequestIDMiddleware


# 模块级 Pydantic model：不能放在 test 函数里（pydantic 2 在 Python 3.8 上
# 解析 ForwardRef 会失败：name 'TestPayload' is not defined）
class TestPayload(BaseModel):
    name: str


def _make_app(*, raise_in_route: Exception | None = None) -> FastAPI:
    """构造测试 app：含 RequestIDMiddleware + exception handlers + 一个会爆的路由。

    app_env 由调用方通过 monkeypatch.setenv("APP_ENV", ...) 控制。
    """
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        if raise_in_route is not None:
            raise raise_in_route
        return None

    return app


def _make_client(app: FastAPI, *, raise_server_exceptions: bool = False) -> TestClient:
    """构造 TestClient。

    raise_server_exceptions=False：route 抛异常时不被 TestClient 重新抛出，
    而是让我们 handler 返回的响应回到测试代码。
    """
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def _set_env_and_clear_cache(monkeypatch: pytest.MonkeyPatch, app_env: str) -> None:
    """设置 APP_ENV + 清 settings 缓存（让 handler 下次 get_settings() 读到新值）。"""
    monkeypatch.setenv("APP_ENV", app_env)
    from app.core.config import get_settings as _get_settings

    _get_settings.cache_clear()


# === ErrorResponse schema 自身 ===


def test_error_response_schema_required_fields() -> None:
    """ErrorResponse 必填字段：error_code / message。"""
    body = ErrorResponse(error_code="X", message="y")
    d = body.model_dump()
    assert d["error_code"] == "X"
    assert d["message"] == "y"
    assert d["details"] is None
    assert d["request_id"] is None


def test_error_response_schema_with_details() -> None:
    """ErrorResponse 可选字段 details / request_id。"""
    body = ErrorResponse(
        error_code="X",
        message="y",
        details={"stack": "Traceback..."},
        request_id="abc123",
    )
    d = body.model_dump()
    assert d["details"] == {"stack": "Traceback..."}
    assert d["request_id"] == "abc123"


def test_error_response_schema_rejects_extra() -> None:
    """ErrorResponse 不允许 extra 字段（前端依赖固定 schema）。"""
    with pytest.raises(pydantic.ValidationError):
        ErrorResponse(error_code="X", message="y", unknown_field="z")  # type: ignore[call-arg]


# === HTTPException 路径（StarletteHTTPException + FastAPI HTTPException）===


def test_404_returns_unified_error_format() -> None:
    """GET /nonexistent → 404 + ErrorResponse schema + X-Request-ID。"""
    app = _make_app()
    client = _make_client(app)
    resp = client.get("/nonexistent")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "NOT_FOUND"
    assert isinstance(body["message"], str)
    assert "request_id" in body
    # X-Request-ID header 必须存在
    assert "X-Request-ID" in resp.headers
    # header 和 body.request_id 一致
    assert resp.headers["X-Request-ID"] == body["request_id"]


def test_422_validation_error_returns_unified_format() -> None:
    """FastAPI validation 错误（422）走统一 handler。"""
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    register_exception_handlers(app)

    @app.post("/echo")
    def echo(payload: TestPayload) -> Dict[str, str]:
        return {"name": payload.name}

    client = _make_client(app)
    resp = client.post("/echo", json={})  # 缺 name
    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "VALIDATION_ERROR"
    assert "request_id" in body


def test_business_http_exception_returns_unified_format() -> None:
    """业务代码 raise HTTPException(401) → 401 + ErrorResponse。"""
    app = _make_app(raise_in_route=HTTPException(status_code=401, detail="Unauthorized"))
    client = _make_client(app)
    resp = client.get("/boom")
    assert resp.status_code == 401
    body = resp.json()
    assert body["error_code"] == "UNAUTHORIZED"
    assert body["message"] == "Unauthorized"
    assert "request_id" in body


def test_method_not_allowed_returns_unified_format() -> None:
    """405 Method Not Allowed 也走统一 handler。"""
    app = _make_app()
    client = _make_client(app)
    resp = client.post("/boom")  # /boom 只注册了 GET
    assert resp.status_code == 405
    body = resp.json()
    assert body["error_code"] == "METHOD_NOT_ALLOWED"


# === 兜底 Exception 路径 ===


def test_unhandled_exception_returns_500_unified_format() -> None:
    """未捕获 Exception → 500 + ErrorResponse（INTERNAL_ERROR）+ X-Request-ID。"""
    app = _make_app(raise_in_route=RuntimeError("kaboom"))
    client = _make_client(app)
    resp = client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error_code"] == "INTERNAL_ERROR"
    assert body["message"] == "Internal server error"
    assert "request_id" in body
    assert "X-Request-ID" in resp.headers


# === request_id 一致性 ===


def test_request_id_is_uuid_hex_format() -> None:
    """request_id 形如 uuid4().hex（32 hex 字符）。"""
    app = _make_app()
    client = _make_client(app)
    resp = client.get("/nonexistent")
    rid = resp.json()["request_id"]
    assert isinstance(rid, str)
    assert re.fullmatch(r"[0-9a-f]{32}", rid), f"unexpected request_id: {rid!r}"


def test_request_id_unique_per_request() -> None:
    """两次请求的 X-Request-ID 不同。"""
    app = _make_app()
    client = _make_client(app)
    r1 = client.get("/nonexistent")
    r2 = client.get("/nonexistent")
    assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]


# === 开发模式 vs 生产模式 ===


def test_development_mode_includes_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """开发模式：details.stack 保留。"""
    _set_env_and_clear_cache(monkeypatch, "development")
    app = _make_app(raise_in_route=RuntimeError("dev-kaboom"))
    client = _make_client(app)
    resp = client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["details"] is not None
    assert "stack" in body["details"]
    assert "RuntimeError" in body["details"]["stack"]


def test_production_mode_hides_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """生产模式：details.stack 不出现（防止信息泄露）。"""
    _set_env_and_clear_cache(monkeypatch, "production")
    app = _make_app(raise_in_route=RuntimeError("prod-kaboom"))
    client = _make_client(app)
    resp = client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    # production: details 要么是 None 要么不含 stack
    if body["details"] is not None:
        assert "stack" not in body["details"]


def test_production_mode_message_is_generic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """生产模式：error.message 不暴露内部异常细节。"""
    _set_env_and_clear_cache(monkeypatch, "production")
    app = _make_app(raise_in_route=RuntimeError("super-secret-internal-error-detail"))
    client = _make_client(app)
    resp = client.get("/boom")
    body = resp.json()
    assert body["message"] == "Internal server error"
    assert "super-secret" not in body["message"]