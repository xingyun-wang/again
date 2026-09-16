"""健康检查端点（GET /api/health）。

用于：
- docker-compose healthcheck
- 前端首页连接性检测
- 运维监控
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(prefix="/api", tags=["health"])


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """健康检查。返回 200 + 状态 + 版本号。"""
    settings = get_settings()
    return HealthResponse(status="ok", version=settings.app_version)
