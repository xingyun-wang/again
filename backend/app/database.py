"""Database config — W1-T2.

SQLite dev DB，路径 backend/dev.db（相对路径以调用方 CWD 为基准）。
- init-db.py 和 seed-test-data.py 从 backend/ 目录跑 → ./dev.db
- uvicorn 启 app 时也用 --app-dir backend → ./dev.db
- 已加进 .gitignore（*.db），不进版本库
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

# SQLite 需要 check_same_thread=False，否则 FastAPI 多线程下会抛错
DATABASE_URL = "sqlite:///./dev.db"

engine = create_engine(
    DATABASE_URL,
    echo=False,  # True 时打 SQL；关掉省噪音
    connect_args={"check_same_thread": False},
)

# autocommit=False + autoflush=False 是 SQLAlchemy 标准做法，业务侧显式 commit
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

# 确保 Base.metadata 已注册所有 model（从 models 导入即触发）
__all__ = ["engine", "SessionLocal", "Base", "DATABASE_URL"]