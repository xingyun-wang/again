"""alembic 迁移：建 assignments + assignment_items 表。

触发：M2-A.1 出题引擎 + 作业单（M2-A.1 brief §3 + §4）
基础：0007_questions（题库 CRUD）+ 0006_owner_user_id
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

from alembic import op

revision: str = "0008_assignments"
down_revision: str | None = "0007_questions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 引用 0007 已建的 PG enum（不重建）
    question_difficulty_enum = PG_ENUM(
        "D", "C", "B", "A", name="question_difficulty_enum", create_type=False
    )

    # 1. 建 assignments 表（作业单头）
    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "chapter_id",
            sa.Integer(),
            sa.ForeignKey("chapters.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("tier", question_difficulty_enum, nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False),
        # 4 档分布审计字段（v0.5 §3.5 反马太判据追溯；D 档 100 题 → d=80 c=20 b=0 a=0）
        sa.Column(
            "d_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "c_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "b_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "a_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("seed", sa.Integer(), nullable=True),
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
    # 单列索引（owner_user_id / chapter_id）手动建（model index=True 不会自动生成 alembic index）
    op.create_index(
        op.f("ix_assignments_owner_user_id"),
        "assignments",
        ["owner_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assignments_chapter_id"),
        "assignments",
        ["chapter_id"],
        unique=False,
    )
    # 复合索引（owner + chapter + tier）= model __table_args__ Index
    op.create_index(
        "ix_assignments_owner_chapter_tier",
        "assignments",
        ["owner_user_id", "chapter_id", "tier"],
    )

    # 2. 建 assignment_items 表（作业题行；1 assignment : N items；与 Choice 同构）
    op.create_table(
        "assignment_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "assignment_id",
            sa.Integer(),
            sa.ForeignKey("assignments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            sa.Integer(),
            sa.ForeignKey("questions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("tier_origin", question_difficulty_enum, nullable=False),
    )
    op.create_index(
        op.f("ix_assignment_items_assignment_id"),
        "assignment_items",
        ["assignment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assignment_items_question_id"),
        "assignment_items",
        ["question_id"],
        unique=False,
    )
    op.create_index(
        "ix_assignment_items_assignment_position",
        "assignment_items",
        ["assignment_id", "position"],
    )


def downgrade() -> None:
    # 倒序拆：items → assignments（不 DROP TYPE；0007 拥有 question_difficulty_enum）
    op.drop_index(
        "ix_assignment_items_assignment_position", table_name="assignment_items"
    )
    op.drop_index(
        op.f("ix_assignment_items_question_id"), table_name="assignment_items"
    )
    op.drop_index(
        op.f("ix_assignment_items_assignment_id"), table_name="assignment_items"
    )
    op.drop_table("assignment_items")
    op.drop_index(
        "ix_assignments_owner_chapter_tier", table_name="assignments"
    )
    op.drop_index(op.f("ix_assignments_chapter_id"), table_name="assignments")
    op.drop_index(
        op.f("ix_assignments_owner_user_id"), table_name="assignments"
    )
    op.drop_table("assignments")
