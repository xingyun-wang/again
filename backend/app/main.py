"""FastAPI 应用入口（M0）。

负责：
- 创建 FastAPI app 实例
- 配置 CORS（开发期允许本地前端）
- 注册路由（health + v1）
- 暴露 app 供 uvicorn 启动
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """构造 FastAPI 应用实例。"""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="差异化作业系统 — 后端 API（M0 骨架）",
    )

    # CORS（开发期放开；M1+ 收紧到生产前端域名）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(health_router)
    # M0 不挂 v1 业务路由（v1 目录留空，M1 才有真实端点）

    return app


# uvicorn app.main:app 入口
app = create_app()
