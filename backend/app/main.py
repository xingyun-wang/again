"""FastAPI 应用入口（M0）。

负责：
- 创建 FastAPI app 实例
- 配置 CORS（开发期允许本地前端）
- 注册 RequestIDMiddleware（注入唯一 request_id 到 contextvar + header）
- 注册统一 exception handlers（errors.py）
- lifespan startup：configure_logging() + DB connect 验证
- lifespan shutdown：engine.dispose()
- 注册路由（health + v1）
- 暴露 app 供 uvicorn 启动
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1.routers.academic import router as academic_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期（M0 retro #3 + #4 合并）。

    startup:
    - configure_logging() 配 root logger（生产 JSON / 开发 plain）
    - engine.connect() 验证 DB 可达；失败 logger.warning 但不阻塞启动

    shutdown:
    - engine.dispose() 释放连接池

    engine 在 lifespan 内延迟导入：模块加载时不触发 SQLAlchemy 对 postgresql 的
    DBAPI 探测（避免测试环境无 psycopg 时也无法 import app.main）。
    """
    # === startup ===
    configure_logging()
    settings = get_settings()
    logger.info(
        "应用启动中 name=%s version=%s env=%s log_level=%s",
        settings.app_name,
        settings.app_version,
        settings.app_env,
        settings.log_level,
    )
    # 延迟导入 + 兜底：避免模块加载时强依赖 psycopg（postgresql driver）
    # ——本地 dev 没装 postgres / docker 时，服务仍能起来（只是 DB 验证跳过）。
    engine: object | None = None
    try:
        from app.db.session import engine as _engine  # noqa: F811

        engine = _engine
    except Exception as e:  # noqa: BLE001
        logger.warning("DB engine 导入失败（不阻塞启动）: %s", e)

    if engine is not None:
        try:
            with engine.connect() as _conn:  # type: ignore[attr-defined]
                pass
            logger.info("数据库连接验证成功")
        except Exception as e:  # noqa: BLE001
            logger.warning("数据库连接验证失败（不阻塞启动）: %s", e)

    yield

    # === shutdown ===
    logger.info("应用关闭中...")
    if engine is not None:
        engine.dispose()  # type: ignore[attr-defined]
        logger.info("数据库连接已释放")


def create_app() -> FastAPI:
    """构造 FastAPI 应用实例。"""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="差异化作业系统 — 后端 API（M0 骨架）",
        lifespan=lifespan,
    )

    # Middleware 顺序：后加的外层。
    # RequestIDMiddleware 先加 → 内层 → 在所有路由（包括 ExceptionMiddleware 触发的错误响应）
    # 之后才被 CORS 包住，但 CORS 只追加自己的 header，不会移除 X-Request-ID。
    app.add_middleware(RequestIDMiddleware)

    # CORS（开发期放开；M1+ 收紧到生产前端域名）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 统一异常处理（M0 retro #2）
    register_exception_handlers(app)

    # 注册路由
    app.include_router(health_router)
    # M1-B B.2：业务 API 路由挂载（v0.5 §10 M1 范围 = 学科知识库 + AI 备课助手）
    # 7+1 endpoints：
    #   POST   /api/v1/academic/textbooks/upload
    #   GET    /api/v1/academic/textbooks/{id}/chapters
    #   POST   /api/v1/academic/chapters/{id}/extract
    #   GET    /api/v1/academic/chapters/{id}
    #   PATCH  /api/v1/academic/chapters/{id}/review
    #   POST   /api/v1/academic/lesson-plans/generate
    #   GET    /api/v1/academic/lesson-plans/{id}
    #   PATCH  /api/v1/academic/lesson-plans/{id}/review  ← judgment call（B.2 spec 漏写）
    app.include_router(academic_router, prefix="/api/v1/academic", tags=["academic"])

    return app


# uvicorn app.main:app 入口
app = create_app()