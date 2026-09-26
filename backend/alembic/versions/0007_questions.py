"""alembic 迁移：建 questions + choices + question_knowledge_points 表。

触发：M2-A.0 题库 CRUD 最小切片（v0.5 §10.2 M2 起步）
基础：0006_owner_user_id + 0005_drop_extraction_default +
       fbb7275 P0-N1/P1-5 + 27515d2 P1-1-1
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

revision: str = "0007_questions"
down_revision: str | None = "0006_owner_user_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. 幂等建 PG native enum 类型（PG 幂等 DO 块：重跑不报错）
    #    D-46 §1：原 SQLAlchemy-Enum 写法（sa_Enum + .create(checkfirst=True)）
    #    在 SQLAlchemy 2.0 对已存在的 PG enum type 仍必报 DuplicateObject
    #    —— 必须用原生 PG 幂等 DO 块包
    op.execute("""DO $$ BEGIN
      CREATE TYPE question_difficulty_enum AS ENUM ('D', 'C', 'B', 'A');
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$""")
    op.execute("""DO $$ BEGIN
      CREATE TYPE question_type_enum AS ENUM ('choice', 'fill', 'subjective');
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$""")

    # 列类型引用：PG-ENUM 带 create_type=False 标志 → 不让 SQLAlchemy 再尝试 CREATE TYPE
    question_difficulty_enum = PG_ENUM(
        "D", "C", "B", "A", name="question_difficulty_enum", create_type=False
    )
    question_type_enum = PG_ENUM(
        "choice", "fill", "subjective", name="question_type_enum", create_type=False
    )

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
    # 单列索引（owner_user_id / chapter_id）手动建（D-46 §2：model academic.py:729/735
    # index=True 但 alembic 迁移不会自动生成 op.create_index —— 必须显式建）
    op.create_index(
        op.f("ix_questions_owner_user_id"),
        "questions",
        ["owner_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_questions_chapter_id"),
        "questions",
        ["chapter_id"],
        unique=False,
    )
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
    # 单列索引（question_id）手动建（D-46 §2：model academic.py:808 index=True）
    op.create_index(
        op.f("ix_choices_question_id"),
        "choices",
        ["question_id"],
        unique=False,
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
    op.drop_index(op.f("ix_choices_question_id"), table_name="choices")
    op.drop_table("choices")
    op.drop_index(
        "ix_questions_owner_chapter_difficulty", table_name="questions"
    )
    op.drop_index(op.f("ix_questions_owner_user_id"), table_name="questions")
    op.drop_index(op.f("ix_questions_chapter_id"), table_name="questions")
    op.drop_table("questions")
    op.execute("DROP TYPE IF EXISTS question_type_enum")
    op.execute("DROP TYPE IF EXISTS question_difficulty_enum")