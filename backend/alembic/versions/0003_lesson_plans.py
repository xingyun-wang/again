"""lesson_plans 表（M1-B B.2：§7.4 AI 声明 + §7.5 教师审阅）。

Revision ID: 0003_lesson_plans
Revises: 0002_academic_models
Create Date: 2026-09-18

引入 lesson_plans 表：
- chapter_id FK → chapters.id
- content TEXT（LLM 生成的授课建议）
- duration_minutes INTEGER（课时长度，默认 45）
- model VARCHAR(128)（生成模型名，§7.4）
- generated_at TIMESTAMPTZ（生成时间，§7.4）
- review_status ENUM(pending/reviewed/modified)（§7.5，默认 pending）
- reviewed_by INTEGER（teacher user_id；可空）
- reviewed_at TIMESTAMPTZ（审阅时间；可空）
- review_notes TEXT（审阅备注；可空）
- created_at / updated_at TIMESTAMPTZ

复用 0002 已建的 knowledge_review_status_enum（create_type=False）。

注意：
- review_status 默认值在 PG 上由 server_default 提供；这里不用 SQLAlchemy 的
  default=KnowledgeReviewStatus.PENDING（因为它是 Python enum，PG enum 列
  server_default 需要字符串值）。
- reviewed_by 是 INTEGER 而非 VARCHAR（与 KnowledgeReview.reviewed_by 不同，
  KnowledgeReview 用 VARCHAR(128) 接受 email-like 标识；LessonPlan 用纯
  INTEGER 表示 X-User-Id 整数）。
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_lesson_plans"
down_revision: str | None = "0002_academic_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 复用 0002 已建的 enum 类型（create_type=False）。
    # 调试记录：构造器传 create_type=False 与 .copy(create_type=False) 在 alembic 1.20
    # + SQLAlchemy 2.0 + PG15 这套组合下均不生效，CREATE TYPE 仍被 emit。降级方案：
    # 直接用 sa.dialects.postgresql.ENUM（这是 alembic 内部最终调用 create_table 时
    # 检查的类型，对 create_type 属性的检查是 strict 的）。
    from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

    review_status_enum = PG_ENUM(
        "pending",
        "approved",
        "modified",
        name="knowledge_review_status_enum",
        create_type=False,
    )

    op.create_table(
        "lesson_plans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "chapter_id",
            sa.Integer(),
            sa.ForeignKey("chapters.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="45"),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # §7.5 review 字段
        sa.Column(
            "review_status",
            review_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_lesson_plans_chapter_id", "lesson_plans", ["chapter_id"])
    op.create_index("ix_lesson_plans_review_status", "lesson_plans", ["review_status"])
    op.create_index(
        "ix_lesson_plans_chapter_id_review_status",
        "lesson_plans",
        ["chapter_id", "review_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_lesson_plans_chapter_id_review_status", table_name="lesson_plans")
    op.drop_index("ix_lesson_plans_review_status", table_name="lesson_plans")
    op.drop_index("ix_lesson_plans_chapter_id", table_name="lesson_plans")
    op.drop_table("lesson_plans")