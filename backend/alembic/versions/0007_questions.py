"""alembic 迁移：建 questions + choices + question_knowledge_points 表。

触发：M2-A.0 题库 CRUD 最小切片（v0.5 §10.2 M2 起步）
基础：0006_owner_user_id + 0005_drop_extraction_source_default +
       fbb7275 P0-N1/P1-5 + 27515d2 P1-1-1
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_questions"
down_revision: str | None = "0006_owner_user_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. 创建 PG native enum 类型（checkfirst=True：重跑幂等）
    question_difficulty_enum = sa.Enum(
        "D", "C", "B", "A", name="question_difficulty_enum"
    )
    question_type_enum = sa.Enum(
        "choice", "fill", "subjective", name="question_type_enum"
    )
    question_difficulty_enum.create(bind, checkfirst=True)
    question_type_enum.create(bind, checkfirst=True)

    # 2. 建 questions 表
    op.create_table(
        "questions",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "chapter_id",
            sa.Integer(),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("difficulty", question_difficulty_enum, nullable=False),
        sa.Column("type", question_type_enum, nullable=False),
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
    # 单列索引（owner_user_id / chapter_id）由 SQLAlchemy index=True 自动建
    # 复合索引（owner + chapter + difficulty）手写
    op.create_index(
        "ix_questions_owner_chapter_difficulty",
        "questions",
        ["owner_user_id", "chapter_id", "difficulty"],
    )

    # 3. 建 choices 表
    op.create_table(
        "choices",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "question_id",
            sa.Integer(),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=8), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "is_correct",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "order_index",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_index(
        "ix_choices_question_order", "choices", ["question_id", "order_index"]
    )

    # 4. 建 question_knowledge_points 关联表（无业务字段）
    op.create_table(
        "question_knowledge_points",
        sa.Column(
            "question_id",
            sa.Integer(),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "knowledge_point_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade() -> None:
    # 倒序拆：关联表 → choices → questions → enum types
    op.drop_table("question_knowledge_points")
    op.drop_index("ix_choices_question_order", table_name="choices")
    op.drop_table("choices")
    op.drop_index(
        "ix_questions_owner_chapter_difficulty", table_name="questions"
    )
    op.drop_table("questions")
    op.execute("DROP TYPE IF EXISTS question_type_enum")
    op.execute("DROP TYPE IF EXISTS question_difficulty_enum")