"""alembic 迁移：assignments 表加 4 个 §7.5 审阅字段（M2-S3）。

触发：M2-S3 brief §6.2（v0.5 §3.6 第 3 步 + §7.5 教师审阅硬约束）
基础：0008_assignments（assignments 表既有）+ 0002_academic_models
（knowledge_review_status_enum 由 0002 拥有）

字段：
- review_status: knowledge_review_status_enum（复用 0002，不重建）+ NOT NULL
  + server_default='pending'（既存 assignment 行默认 pending）
- reviewed_by: INTEGER NULL（FK → users.id 由 ORM 端保证；migration 不加 FK
  约束以保持 §十三 严禁不修既有债，且不引入新 FK 行为）
- reviewed_at: TIMESTAMPTZ NULL
- review_notes: TEXT NULL

加单列索引 ix_assignments_review_status（model index=True 不会自动生成
alembic index；同 0008 owner_user_id / chapter_id 模式）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

from alembic import op

revision: str = "0010_assignment_review_fields"
down_revision: str | None = "0009_student_tier_audit_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 引用 0002 已建的 PG enum（不重建）
    knowledge_review_status_enum = PG_ENUM(
        "pending",
        "approved",
        "modified",
        name="knowledge_review_status_enum",
        create_type=False,
    )

    # 1. review_status: enum + NOT NULL + server_default='pending'（既存行兜底）
    op.add_column(
        "assignments",
        sa.Column(
            "review_status",
            knowledge_review_status_enum,
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
    )
    # 2. reviewed_by: INTEGER NULL（不显式建 FK；ORM 端保证；§十三 不修既有债）
    op.add_column(
        "assignments",
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
    )
    # 3. reviewed_at: TIMESTAMPTZ NULL
    op.add_column(
        "assignments",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 4. review_notes: TEXT NULL
    op.add_column(
        "assignments",
        sa.Column("review_notes", sa.Text(), nullable=True),
    )

    # 单列索引（model index=True 不会自动生成 alembic index；同 0008 模式）
    op.create_index(
        op.f("ix_assignments_review_status"),
        "assignments",
        ["review_status"],
        unique=False,
    )


def downgrade() -> None:
    # 倒序拆：先拆索引 + 后 3 字段，再拆 review_status
    op.drop_index(
        op.f("ix_assignments_review_status"), table_name="assignments"
    )
    op.drop_column("assignments", "review_notes")
    op.drop_column("assignments", "reviewed_at")
    op.drop_column("assignments", "reviewed_by")
    op.drop_column("assignments", "review_status")
