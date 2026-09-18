"""academic models (M1-A 阶段 1：v0.5 §4.1 + §4.2)

Revision ID: 0002_academic_models
Revises: 0001_initial
Create Date: 2026-09-17

引入 11 张表（学情预留 + 学科知识库）+ 3 个 PG native enum：
- grade_level_enum           (junior_high / senior_high)
- tier_enum                  (D / C / B / A)
- knowledge_review_status_enum (pending / approved / modified)

依赖顺序（FK 拓扑）：
1.  subjects                 (无 FK)
2.  classes                  (FK → subjects)
3.  textbooks                (FK → subjects, nullable)
4.  students                 (FK → classes)
5.  chapters                 (FK → textbooks)
6.  knowledge_points         (FK → chapters)
7.  key_points               (FK → chapters)
8.  difficulties             (FK → chapters)
9.  teaching_suggestions     (FK → chapters)
10. knowledge_reviews        (FK → chapters)
11. student_knowledge_points (FK → students + knowledge_points)

每个表都对 FK 列建索引；高频查询列（name / chapter_number / status）也建。
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_academic_models"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ─────────────────────────── enum types ───────────────────────────
    # 用 sa.Enum 在每个表 column 上声明：第一次出现的 column（create_type=True 默认）
    # 会 CREATE TYPE；后续出现的 column 设 create_type=False 复用，避免
    # DuplicateObject。checkfirst 在 PG CREATE TYPE 上不可靠（Alembic 不发 IF NOT EXISTS），
    # 所以这里不用 Enum.create(checkfirst=True) 显式建。
    grade_level_enum = sa.Enum(
        "junior_high",
        "senior_high",
        name="grade_level_enum",
        native_enum=True,
    )
    tier_enum = sa.Enum(
        "D",
        "C",
        "B",
        "A",
        name="tier_enum",
        native_enum=True,
    )
    knowledge_review_status_enum = sa.Enum(
        "pending",
        "approved",
        "modified",
        name="knowledge_review_status_enum",
        native_enum=True,
    )

    # ─────────────────────────── 1. subjects ───────────────────────────
    # subjects 是 grade_level_enum 的第一个使用点，create_type 默认 True → 自动 CREATE TYPE
    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column(
            "grade_level",
            grade_level_enum,
            nullable=False,
        ),
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
    op.create_index("ix_subjects_grade_level", "subjects", ["grade_level"])
    op.create_index("ix_subjects_name", "subjects", ["name"])

    # ─────────────────────────── 2. classes ────────────────────────────
    op.create_table(
        "classes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "grade_level",
            grade_level_enum.copy(create_type=False),
            nullable=False,
        ),
        sa.Column(
            "subject_id",
            sa.Integer(),
            sa.ForeignKey("subjects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
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
    op.create_index("ix_classes_subject_id", "classes", ["subject_id"])
    op.create_index("ix_classes_grade_level", "classes", ["grade_level"])
    op.create_index("ix_classes_name", "classes", ["name"])

    # ─────────────────────────── 3. textbooks ──────────────────────────
    op.create_table(
        "textbooks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column(
            "subject_id",
            sa.Integer(),
            sa.ForeignKey("subjects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "grade_level",
            grade_level_enum.copy(create_type=False),
            nullable=True,
        ),
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
    op.create_index("ix_textbooks_subject_id", "textbooks", ["subject_id"])
    op.create_index("ix_textbooks_grade_level", "textbooks", ["grade_level"])

    # ─────────────────────────── 4. students ───────────────────────────
    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "class_id",
            sa.Integer(),
            sa.ForeignKey("classes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "grade_level",
            grade_level_enum.copy(create_type=False),
            nullable=False,
        ),
        sa.Column(
            "current_tier",
            tier_enum,
            nullable=False,
        ),
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
    op.create_index("ix_students_class_id", "students", ["class_id"])
    op.create_index("ix_students_grade_level", "students", ["grade_level"])
    op.create_index("ix_students_current_tier", "students", ["current_tier"])
    op.create_index("ix_students_name", "students", ["name"])

    # ─────────────────────────── 5. chapters ───────────────────────────
    op.create_table(
        "chapters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "textbook_id",
            sa.Integer(),
            sa.ForeignKey("textbooks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("content_summary", sa.Text(), nullable=True),
        sa.Column("page_range_start", sa.Integer(), nullable=True),
        sa.Column("page_range_end", sa.Integer(), nullable=True),
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
    op.create_index("ix_chapters_textbook_id", "chapters", ["textbook_id"])
    op.create_index("ix_chapters_chapter_number", "chapters", ["chapter_number"])
    op.create_unique_constraint(
        "uq_chapters_textbook_id_chapter_number", "chapters", ["textbook_id", "chapter_number"]
    )

    # ─────────────────────────── 6. knowledge_points ────────────────────
    op.create_table(
        "knowledge_points",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "chapter_id",
            sa.Integer(),
            sa.ForeignKey("chapters.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("concept", sa.Text(), nullable=False),
        sa.Column("teaching_order", sa.Integer(), nullable=False),
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
    op.create_index("ix_knowledge_points_chapter_id", "knowledge_points", ["chapter_id"])
    op.create_index("ix_knowledge_points_teaching_order", "knowledge_points", ["teaching_order"])

    # ─────────────────────────── 7. key_points ──────────────────────────
    op.create_table(
        "key_points",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "chapter_id",
            sa.Integer(),
            sa.ForeignKey("chapters.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=True),
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
    op.create_index("ix_key_points_chapter_id", "key_points", ["chapter_id"])

    # ─────────────────────────── 8. difficulties ────────────────────────
    op.create_table(
        "difficulties",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "chapter_id",
            sa.Integer(),
            sa.ForeignKey("chapters.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=True),
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
    op.create_index("ix_difficulties_chapter_id", "difficulties", ["chapter_id"])

    # ─────────────────────────── 9. teaching_suggestions ────────────────
    op.create_table(
        "teaching_suggestions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "chapter_id",
            sa.Integer(),
            sa.ForeignKey("chapters.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=True),
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
    op.create_index(
        "ix_teaching_suggestions_chapter_id", "teaching_suggestions", ["chapter_id"]
    )

    # ─────────────────────────── 10. knowledge_reviews ──────────────────
    # knowledge_review_status_enum 第一次出现在这里，create_type 默认 True
    op.create_table(
        "knowledge_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "chapter_id",
            sa.Integer(),
            sa.ForeignKey("chapters.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            knowledge_review_status_enum,
            nullable=False,
        ),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
    op.create_index("ix_knowledge_reviews_chapter_id", "knowledge_reviews", ["chapter_id"])
    op.create_index("ix_knowledge_reviews_status", "knowledge_reviews", ["status"])

    # ─────────────────────────── 11. student_knowledge_points ───────────
    op.create_table(
        "student_knowledge_points",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("students.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "knowledge_point_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_points.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("mastery_score", sa.Float(), nullable=True),
        sa.Column("last_assessed_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index(
        "ix_student_knowledge_points_student_id",
        "student_knowledge_points",
        ["student_id"],
    )
    op.create_index(
        "ix_student_knowledge_points_knowledge_point_id",
        "student_knowledge_points",
        ["knowledge_point_id"],
    )
    op.create_unique_constraint(
        "uq_student_knowledge_points_student_id_kp_id",
        "student_knowledge_points",
        ["student_id", "knowledge_point_id"],
    )


def downgrade() -> None:
    # 反向 drop（按依赖反向）
    op.drop_table("student_knowledge_points")
    op.drop_table("knowledge_reviews")
    op.drop_table("teaching_suggestions")
    op.drop_table("difficulties")
    op.drop_table("key_points")
    op.drop_table("knowledge_points")
    op.drop_table("chapters")
    op.drop_table("students")
    op.drop_table("textbooks")
    op.drop_table("classes")
    op.drop_table("subjects")

    # enum types
    sa.Enum(name="knowledge_review_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="tier_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="grade_level_enum").drop(op.get_bind(), checkfirst=True)