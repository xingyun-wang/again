"""alembic 迁移：建 question_images 表（题目图片承载；v0.5 §3.4 + M2-A.1 brief §3.1）。

触发：M2-A.1 内容承载三决策 ① — 题目图片（决策书 §7.2 D-M2-2 + v0.5 §3.4）
基础：0007_questions（题库 CRUD） + 0008_assignments（出题引擎）
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

from alembic import op

revision: str = "0011_question_images"
down_revision: str | None = "0010_assignment_review_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. 幂等建 PG native enum 类型（PG 幂等 DO 块：重跑不报错）
    #    D-46 §1：原 SQLAlchemy-Enum 写法（sa_Enum + .create(checkfirst=True)）
    #    在 SQLAlchemy 2.0 对已存在的 PG enum type 仍必报 DuplicateObject
    #    —— 必须用原生 PG 幂等 DO 块包
    op.execute("""DO $$ BEGIN
      CREATE TYPE question_image_source_enum AS ENUM ('self_built', 'external_imported');
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$""")
    op.execute("""DO $$ BEGIN
      CREATE TYPE desensitization_status_enum AS ENUM ('pending', 'done', 'skipped');
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$""")

    # 列类型引用：PG-ENUM 带 create_type=False 标志 → 不让 SQLAlchemy 再尝试 CREATE TYPE
    question_image_source_enum = PG_ENUM(
        "self_built",
        "external_imported",
        name="question_image_source_enum",
        create_type=False,
    )
    desensitization_status_enum = PG_ENUM(
        "pending",
        "done",
        "skipped",
        name="desensitization_status_enum",
        create_type=False,
    )

    # 2. 建 question_images 表（12 列）
    op.create_table(
        "question_images",
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
        sa.Column(
            "order_index",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("file_ext", sa.String(length=8), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("source", question_image_source_enum, nullable=False),
        sa.Column(
            "desensitization_status",
            desensitization_status_enum,
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "desensitized_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # M3 预留
        sa.Column("oss_object_key", sa.String(length=512), nullable=True),
        sa.Column("oss_uploaded_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 单列索引（question_id / uploaded_by_user_id）手动建（D-46 §2：model
    # index=True 但 alembic 迁移不会自动生成 op.create_index —— 必须显式建）
    op.create_index(
        op.f("ix_question_images_question_id"),
        "question_images",
        ["question_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_question_images_uploaded_by_user_id"),
        "question_images",
        ["uploaded_by_user_id"],
        unique=False,
    )
    # 复合索引（question_id + order_index）= model __table_args__ Index
    op.create_index(
        "ix_question_images_question_order",
        "question_images",
        ["question_id", "order_index"],
    )


def downgrade() -> None:
    # 倒序拆：indexes → table → enum types
    op.drop_index("ix_question_images_question_order", table_name="question_images")
    op.drop_index(
        op.f("ix_question_images_uploaded_by_user_id"), table_name="question_images"
    )
    op.drop_index(op.f("ix_question_images_question_id"), table_name="question_images")
    op.drop_table("question_images")
    op.execute("DROP TYPE IF EXISTS desensitization_status_enum")
    op.execute("DROP TYPE IF EXISTS question_image_source_enum")
