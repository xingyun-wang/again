"""initial migration (M0 placeholder)

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-16

M0 阶段没有真实 model（教材 / 题库 / 班级 / 学生 / 作业 / 提交 / 学情 都在 M1+）。
此 migration 仅作为 alembic 链路起点，让 `alembic upgrade head` 跑得通。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # M0 不建任何业务表（model 还没建）
    # 留 alembic_version 表占位即可
    pass


def downgrade() -> None:
    pass
