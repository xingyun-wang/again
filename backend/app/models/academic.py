"""学情 + 学科知识库 数据模型（v0.5 §3.2 / §4.1 / §4.2）。

M1-A 阶段 1 引入的所有 11 张表，按 v0.5 §4.1 + §4.2 数据模型定稿：
- 学情预留：Subject / Class / Student / StudentKnowledgePoint
- 学科知识库：Textbook / Chapter / KnowledgePoint / KeyPoint / Difficulty /
  TeachingSuggestion / KnowledgeReview

设计原则（来自 M0 retro §教训 + v0.5 judgment）：
- enum 用 PG native type（`native_enum=True`）+ `values_callable=lambda x: [e.value for e in x]`
  保证存的是字符串值（D/C/B/A）而不是枚举名（TIER_D）。SQLite in-memory 测试时
  SQLAlchemy 会自动 fallback 到 VARCHAR + CHECK，不影响。
- relationship 全部 `back_populates` 双向 + `lazy="selectin"`（集合方向），
  避免 lazy load 陷阱（v0.5 M1 §1.3 judgment call）。
- FK 行为：默认（RESTRICT on non-nullable, SET NULL on nullable）——
  不 cascade，让 FK 报错更安全（M0 retro 教训）。
- 时间戳：`created_at` / `updated_at` 全部 server_default=func.now() + onupdate=func.now()。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

# ─────────────────────────── §7.5 review 语义说明 ─────────────────────
# v0.5 §7.5 教师审阅硬约束：lesson-plan 生成后 = pending；必须 PATCH /review
# 标记 reviewed/modified 后才能用于下次备课（M1+ 闭环；MVP 阶段不消费此状态，
# 仅记录）。Chapter 级用 KnowledgeReview；lesson-plan 级用 KnowledgeReviewStatus
# 复用（三态相同：pending / reviewed / modified）。
# 若后续需要细分，再拆 LessonPlanReviewStatus（本阶段不拆，避免 enum 复杂度膨胀）。

# ─────────────────────────── enums ───────────────────────────


# UP042（py311 推荐 StrEnum）这里保留 (str, Enum)：dev box 是 py3.8 没有 StrEnum，
# 用 (str, Enum) 在 py3.8 + py3.11 都跑得通；prod / CI 是 py3.11。
class GradeLevel(str, Enum):  # noqa: UP042
    """学段（v0.5 §3.2）：初中 / 高中。"""

    JUNIOR_HIGH = "junior_high"
    SENIOR_HIGH = "senior_high"


class Tier(str, Enum):  # noqa: UP042
    """学情分层（v0.5 §3.2）：D < C < B < A。"""

    D = "D"
    C = "C"
    B = "B"
    A = "A"


class KnowledgeReviewStatus(str, Enum):  # noqa: UP042
    """知识审阅状态（M1-B 阶段使用，本阶段仅预留字段）。"""

    PENDING = "pending"
    APPROVED = "approved"
    MODIFIED = "modified"


# ─────────────────────── 学情预留 (§4.1) ──────────────────────


class Subject(Base):
    """学科（如 初中数学 / 高中物理）。"""

    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    grade_level: Mapped[GradeLevel] = mapped_column(
        SAEnum(
            GradeLevel,
            name="grade_level_enum",
            native_enum=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    classes: Mapped[list[Class]] = relationship(
        "Class", back_populates="subject", lazy="selectin"
    )
    textbooks: Mapped[list[Textbook]] = relationship(
        "Textbook", back_populates="subject", lazy="selectin"
    )


class Class(Base):
    """班级。归属一个 Subject，下挂多个 Student。

    表名用 `classes`（PG 关键字避让：PG 里 `class` 是 reserved word）。
    """

    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    grade_level: Mapped[GradeLevel] = mapped_column(
        SAEnum(
            GradeLevel,
            name="grade_level_enum",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    subject: Mapped[Subject] = relationship("Subject", back_populates="classes", lazy="selectin")
    students: Mapped[list[Student]] = relationship(
        "Student", back_populates="class_", lazy="selectin"
    )


class Student(Base):
    """学生。归属一个 Class，有一个 current_tier（v0.5 §3.2）。"""

    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    grade_level: Mapped[GradeLevel] = mapped_column(
        SAEnum(
            GradeLevel,
            name="grade_level_enum",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    current_tier: Mapped[Tier] = mapped_column(
        SAEnum(
            Tier,
            name="tier_enum",
            native_enum=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 注意：`class_` 是因为 `class` 是 Python 关键字
    class_: Mapped[Class] = relationship("Class", back_populates="students", lazy="selectin")
    knowledge_points: Mapped[list[StudentKnowledgePoint]] = relationship(
        "StudentKnowledgePoint", back_populates="student", lazy="selectin", cascade="all, delete-orphan"
    )


class StudentKnowledgePoint(Base):
    """学生 × 知识点 关联表（M1+ 业务用，本阶段仅预留结构）。

    `mastery_score` 字段类型 Float 预留（M1-B 接入 LLM 评估时使用）。
    """

    __tablename__ = "student_knowledge_points"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "knowledge_point_id",
            name="uq_student_knowledge_points_student_id_kp_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    mastery_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_assessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    student: Mapped[Student] = relationship("Student", back_populates="knowledge_points")
    knowledge_point: Mapped[KnowledgePoint] = relationship(
        "KnowledgePoint", back_populates="student_links"
    )


# ─────────────────── 学科知识库 (§4.2) ────────────────────────


class Textbook(Base):
    """教材（PDF 文件路径 + 学科归属）。

    `subject_id` 可空：允许"未归类"教材入库后再补（M1-C ingestion 路径需要）。
    """

    __tablename__ = "textbooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    grade_level: Mapped[GradeLevel | None] = mapped_column(
        SAEnum(
            GradeLevel,
            name="grade_level_enum",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    subject: Mapped[Subject | None] = relationship(
        "Subject", back_populates="textbooks", lazy="selectin"
    )
    chapters: Mapped[list[Chapter]] = relationship(
        "Chapter", back_populates="textbook", lazy="selectin"
    )


class Chapter(Base):
    """教材章节。1-based chapter_number。"""

    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("textbook_id", "chapter_number", name="uq_chapters_textbook_id_chapter_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    textbook_id: Mapped[int] = mapped_column(
        ForeignKey("textbooks.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_range_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_range_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    textbook: Mapped[Textbook] = relationship("Textbook", back_populates="chapters")
    knowledge_points: Mapped[list[KnowledgePoint]] = relationship(
        "KnowledgePoint", back_populates="chapter", lazy="selectin"
    )
    key_points: Mapped[list[KeyPoint]] = relationship(
        "KeyPoint", back_populates="chapter", lazy="selectin"
    )
    difficulties: Mapped[list[Difficulty]] = relationship(
        "Difficulty", back_populates="chapter", lazy="selectin"
    )
    teaching_suggestions: Mapped[list[TeachingSuggestion]] = relationship(
        "TeachingSuggestion", back_populates="chapter", lazy="selectin"
    )
    reviews: Mapped[list[KnowledgeReview]] = relationship(
        "KnowledgeReview", back_populates="chapter", lazy="selectin"
    )
    lesson_plans: Mapped[list[LessonPlan]] = relationship(
        "LessonPlan", back_populates="chapter", lazy="selectin"
    )


class KnowledgePoint(Base):
    """知识点。一个 Chapter 多个知识点，按 `teaching_order` 排序。"""

    __tablename__ = "knowledge_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    concept: Mapped[str] = mapped_column(Text, nullable=False)
    teaching_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    chapter: Mapped[Chapter] = relationship("Chapter", back_populates="knowledge_points")
    student_links: Mapped[list[StudentKnowledgePoint]] = relationship(
        "StudentKnowledgePoint", back_populates="knowledge_point", lazy="selectin"
    )


class KeyPoint(Base):
    """重点（教师 / AI 从教材抽取）。

    表名 `key_points` 而非 `keys`：避开 PG 关键字 `key` / `keys`。
    """

    __tablename__ = "key_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    chapter: Mapped[Chapter] = relationship("Chapter", back_populates="key_points")


class Difficulty(Base):
    """难点（教师 / AI 从教材抽取）。"""

    __tablename__ = "difficulties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    chapter: Mapped[Chapter] = relationship("Chapter", back_populates="difficulties")


class TeachingSuggestion(Base):
    """教学建议（教师 / AI 从教材抽取）。"""

    __tablename__ = "teaching_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    chapter: Mapped[Chapter] = relationship("Chapter", back_populates="teaching_suggestions")


class KnowledgeReview(Base):
    """知识审阅记录（M1-B 阶段由老师触发，pending → approved/modified）。

    本阶段（M1-A 阶段 1）仅预留字段 + 表结构。
    """

    __tablename__ = "knowledge_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[KnowledgeReviewStatus] = mapped_column(
        SAEnum(
            KnowledgeReviewStatus,
            name="knowledge_review_status_enum",
            native_enum=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        index=True,
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    chapter: Mapped[Chapter] = relationship("Chapter", back_populates="reviews")


class LessonPlan(Base):
    """授课建议（M1-B B.2：基于 chapter + 学情 → LLM 生成）。

    §7.4 AI 声明字段：model + generated_at 在创建时写入。
    §7.5 教师审阅：review_status 默认 pending；老师 PATCH /review 标记
    reviewed/modified 后才能用于下次备课（M1+ 闭环，本阶段仅记录，不消费）。
    """

    __tablename__ = "lesson_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=45)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # §7.5 字段（复用 KnowledgeReviewStatus 三态）
    review_status: Mapped[KnowledgeReviewStatus] = mapped_column(
        SAEnum(
            KnowledgeReviewStatus,
            name="knowledge_review_status_enum",
            native_enum=True,
            create_type=False,  # 复用 0002 创建的 enum 类型，不重复 CREATE TYPE
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=KnowledgeReviewStatus.PENDING,
        server_default=KnowledgeReviewStatus.PENDING.value,
        index=True,
    )
    reviewed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    chapter: Mapped[Chapter] = relationship("Chapter", back_populates="lesson_plans")