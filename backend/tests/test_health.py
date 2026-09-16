"""健康检查端点测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok() -> None:
    """GET /api/health 返回 status=ok 和 version=0.1.0。"""
    client = TestClient(create_app())
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"


def test_health_response_schema() -> None:
    """响应 schema 校验。"""
    client = TestClient(create_app())
    resp = client.get("/api/health")
    body = resp.json()
    assert set(body.keys()) == {"status", "version"}
    assert isinstance(body["status"], str)
    assert isinstance(body["version"], str)
