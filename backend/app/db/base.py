"""SQLAlchemy Declarative Base。

所有 ORM model 继承此 Base。M0 阶段 model 目录留空（model 在 M1 引入）。
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 风格 Declarative Base。"""

    pass
