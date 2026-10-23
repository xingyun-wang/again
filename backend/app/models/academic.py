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
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy import false as SAFalse
from sqlalchemy.dialects import postgresql
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


# ─────────────────────── M1-B retro 工单 B：归属（D-29 B 项） ──────────
#
# 工单 B 落「题库属于教师个人资产」建模：
# - 新增 ``User`` 表（id / name / is_system_owned / created_at / updated_at）
# - Subject / Textbook / Chapter 三个表加 ``owner_user_id`` FK → users.id
#   （ondelete=``RESTRICT``：删 user 阻挡，避免连坐丢数据）
# - system seed user（id=1, name='system-seed'）由 alembic 0005 插，
#   代持 M3+ 用户系统接入前的既有数据
#
# 设计要点：
# - ``is_system_owned``：标记系统种子用户；M3+ 接入真 user 系统后，迁移
#   ``is_system_owned=True`` 行到对应真用户即可（owner_user_id 不动 schema）
# - 关系方向：Subject / Textbook / Chapter 都加 ``relationship("User",
#   lazy="selectin")``，让 ORM 访问 owner 时不触发额外 lazy load（v0.5 §1.3
#   教训：避免 N+1）
# - 不引入鉴权：本表只承担"归属元数据 + FK 完整性"，user 注册 / 登录 /
#   JWT 都是 M3+ 范围（brief 明确划界）


class User(Base):
    """教师 / 系统用户（M1-B 工单 B：归属最小骨架，M3+ 才接鉴权）。

    字段语义：
    - id INTEGER PK auto：保持自增；alembic 0005 显式插入 id=1 作为 system-seed
    - name VARCHAR(128) NOT NULL：用户显示名（暂未做唯一约束；M3+ 加）
    - is_system_owned BOOLEAN NOT NULL DEFAULT false：标记系统种子用户；
      M3+ 接入真 user 系统后，迁移此标志 = true 的行即可
    - created_at / updated_at TIMESTAMPTZ NOT NULL server_default=now()
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_system_owned: Mapped[bool] = mapped_column(
        # server_default 兜底：手写 INSERT / fixture 偶发省略时仍能落库
        Boolean,
        nullable=False,
        server_default="false",
        default=False,
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
    # M2-A.0：User 下挂本老师拥有的所有 Question（无 cascade：删 user 触发 RESTRICT FK 拦下）
    questions: Mapped[list[Question]] = relationship(
        "Question", back_populates="owner"
    )


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
    # M1-B retro 工单 B（D-29 B 项）：归属字段。跨用户可见性 404（不是 403）。
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
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
    owner: Mapped[User] = relationship("User", lazy="selectin")


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
    """学生。归属一个 Class，有一个 current_tier（v0.5 §3.2）。

    S2 audit 字段（migration 0009）：
    - tier_changed_by_user_id: 谁把 current_tier 改了（users.id FK，RESTRICT）
    - tier_changed_at: 改档位时间戳（timestamptz，nullable）
    既存 Student 行这两个字段默认 NULL（历史未追踪；不回填）。
    """

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
    # S2 audit 字段（migration 0009）：手动覆盖档位时记录
    tier_changed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    tier_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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
    # M1-B retro 工单 B（D-29 B 项）：归属字段。跨用户访问返 404。
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
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
    owner: Mapped[User] = relationship("User", lazy="selectin")


class Chapter(Base):
    """教材章节。1-based chapter_number。

    `extraction_source`（M2 工单 A 落地）：
        标记该章节的章节骨架 + content_summary 来源
        0.5 §9.1 §10 + D-28 硬规则：链路真实性必须可降级留痕
        取值（snake_case；保守 default='detected'，让未显式 set 的 Chapter
        也能落库；测试 fixture 在 conftest.py 也可显式覆盖）：
        - detected                — PyMuPDF/pdfplumber 主路径正常识别章节 + 抽到正文
        - pdfplumber_fallback     — PyMuPDF 主路径失败，pdfplumber fallback 接管
        - equal_split_placeholder — 主路径 + fallback 都识别不足，等分造章节（**真实造假，必须标记**）
        - scanned_pdf_empty       — 文本为空（扫描型 PDF，需 OCR，§6.4 TWAIN 实测 blocker）
    """

    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("textbook_id", "chapter_number", name="uq_chapters_textbook_id_chapter_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    textbook_id: Mapped[int] = mapped_column(
        ForeignKey("textbooks.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # M1-B retro 工单 B（D-29 B 项）：归属字段。跨用户访问返 404。
    # 与 textbook.owner 冗余（chapter → textbook → owner），但保留 chapter
    # 级 owner_user_id 让章节级过滤不必 JOIN textbook，避免 lesson-plan 路径
    # 多走一次 join（lesson-plan → chapter → textbook → owner）。
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_range_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_range_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # extraction_source：M2 工单 A 新增；nullable=False。
    # M1-B retro Step 1（2026-09-21，D-37 G2 解封）：删 ORM Python default
    # 与 server_default——fail-open 防护收口在 service 路径（textbook_upload
    # 显式 set extraction_source = src；conftest fixture 不再依赖 ORM 兜底）。
    # 若 service 漏传 → PG NOT NULL violation（fail-closed，与 0005 迁移行为一致）。
    extraction_source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
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

    textbook: Mapped[Textbook] = relationship("Textbook", back_populates="chapters")
    owner: Mapped[User] = relationship("User", lazy="selectin")
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
    # M2-A.0：Chapter 下挂本老师的所有 Question（cascade 自动清空 chapter 删除时连带题目）
    questions: Mapped[list[Question]] = relationship(
        "Question", back_populates="chapter", cascade="all, delete-orphan", lazy="selectin"
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
    # M2-A.0：KP 反向题目集合（多对多关联表 question_knowledge_points）
    questions: Mapped[list[Question]] = relationship(
        "Question", secondary="question_knowledge_points", back_populates="knowledge_points"
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


# ──────────────────── M2-A.0 题库 CRUD（v0.5 §3 / D-29 §1.4） ───────────────
#
# 范围锁定（brief §3 / v0.5 §3）：
# - Question 数据模型（题库基础）— 老师个人资产（D-29 §1.4）
# - Choice 数据模型（多选项题目）
# - KnowledgePoint 多对多关联（题目 → 知识点）
# - 4 档位 D/C/B/A（字母升序=难度升序，v0.5 §3.2）
# - 题型 choice / fill / subjective（v0.5 §3.4）
# - owner_user_id 字段（D-29 跨用户隔离）
#
# 范围外（brief §3 锁）：
# - 4 档差异化引擎（M2-A.1）
# - 反马太逻辑（M2-A.1）
# - PDF 导出（M2-A.2）
# - 外部题库导入（M2-A.3）
# - AI 出题（v0.5 §3.3 永久禁用）
# - 共建题库 is_public（M2-A.0 不启用，v0.5 §5.4 lock MVP）


class QuestionDifficulty(str, Enum):  # noqa: UP042
    """v0.5 §3.2 4 档位（字母升序 = 难度升序）。

    D = 基础（最易）
    C = 进阶
    B = 挑战
    A = 扩展（最难）

    字母升序 = 难度升序：和现有 Tier enum（学术场景）共用值空间。
    本 enum 命名用 QuestionDifficulty 避免与学情 Tier 字段同名（属背景，
    Tier 用于 Student.current_tier；QuestionDifficulty 用于 Question.difficulty）。
    """

    D = "D"
    C = "C"
    B = "B"
    A = "A"


class QuestionType(str, Enum):  # noqa: UP042
    """v0.5 §3.4 题型标签。

    - CHOICE = 选择题（单选 / 多选；M2-A.0 仅支持单选，多选为后续切片）
    - FILL = 填空题
    - SUBJECTIVE = 主观题
    """

    CHOICE = "choice"
    FILL = "fill"
    SUBJECTIVE = "subjective"


class QuestionImageSource(str, Enum):  # noqa: UP042
    """题目图片来源（M2-A.1 brief §3.1）。

    - SELF_BUILT = 教师自建（如地理教师画地图示意图、标注图）
    - EXTERNAL_IMPORTED = 外部导入（如截图 / 教材扫描 / 共享图库）

    区别于 1:N vs ARRAY 判据中"上传者追溯"列：source 是图像本身的来源
    （who drew / where from），uploaded_by_user_id 是系统动作的归属
    （who uploaded this row to system）。两者独立字段，分别追溯。
    """

    SELF_BUILT = "self_built"
    EXTERNAL_IMPORTED = "external_imported"


class DesensitizationStatus(str, Enum):  # noqa: UP042
    """图片脱敏状态（M2-A.1 brief §3.1 + §6.3）。

    - PENDING = 脱敏未做（M3 实际跑脱敏处理；S1/M2 阶段默认值）
    - DONE = 脱敏已完成（脱敏时间戳落 desensitized_at）
    - SKIPPED = 主动跳过脱敏（题目图片通常不含 PII；v0.5 §6.5）

    S1/M2 阶段：所有新建行 = PENDING；无实际脱敏处理（M3 范围）。
    """

    PENDING = "pending"
    DONE = "done"
    SKIPPED = "skipped"


# 题目-知识点多对多关联表（M2-A.0 新增）。
# KnowledgePoint 自身无 owner_user_id（KP 归属 = chapter.owner_user_id），
# 因此 KP 的归属校验走 chapter 路径（router 层 _enforce_owner_or_404 chapter）。
# 关联表本身无业务归属字段。
question_knowledge_points = Table(
    "question_knowledge_points",
    Base.metadata,
    Column(
        "question_id",
        Integer,
        ForeignKey("questions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "knowledge_point_id",
        Integer,
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Question(Base):
    """题库基础模型（v0.5 §3 差异化作业）。

    归属（D-29 §1.4 题库属于教师个人资产）：owner_user_id FK → users.id，
    RESTRICT 阻止删除 user 时连坐丢题（与 Subject/Textbook/Chapter 行为一致）。

    4 档位：D/C/B/A 字母升序 = 难度升序（v0.5 §3.2）。

    题型：v0.5 §3.4 不限制，choice / fill / subjective 都可。

    KnowledgePoint 多对多：题目可关联 0+ 个知识点（沿用 M1 已有 KnowledgePoint）。
    Choice 1 对多：选择题 0+ 个选项（仅 choice 类型使用）。
    """

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[QuestionDifficulty] = mapped_column(
        SAEnum(
            QuestionDifficulty,
            name="question_difficulty_enum",
            native_enum=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    type: Mapped[QuestionType] = mapped_column(
        SAEnum(
            QuestionType,
            name="question_type_enum",
            native_enum=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    # M3-1a brief §1.1（2026-10-19 21:02 拍）：points + answer_text 两列
    # - points: Numeric(5,1) NOT NULL server_default='2.0'（默认 2 分）
    # - answer_text: Text NULL（仅 fill / subjective 用；choice 答案走 Choice.is_correct）
    # 严格两列，不夹带 batch / student / barcode（属 0013 推迟）
    points: Mapped[float] = mapped_column(
        Numeric(5, 1),
        nullable=False,
        default=2.0,
        server_default="2.0",
    )
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # M3-1a-2（brief §1 改表 4 + 补遗 §丙-2）：
    # - group_id FK → question_groups.id CASCADE NULL index
    #   NULL = 单题（现有题全部保持 NULL ⇒ 行为零变化，判据 9）
    # - group_order 题组内题序（0 起）；NULL = 不在题组内
    # - 唯一写入源是题组：小题的 difficulty 是**组难度的派生缓存**（补遗 §乙-4），
    #   挂小题时由 API 层同步写入，改组难度时批量更新 —— 本 model 不自动同步。
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("question_groups.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    group_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    knowledge_points: Mapped[list[KnowledgePoint]] = relationship(
        KnowledgePoint,
        secondary="question_knowledge_points",
        back_populates="questions",
        lazy="selectin",
    )
    choices: Mapped[list[Choice]] = relationship(
        "Choice",
        back_populates="question",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    # M2-A.1（brief §3.1）：题目图片承载（1:N，图像密集学科图像）
    # - cascade="all, delete-orphan": 删 Question 时 QuestionImage 自动清空
    # - lazy="selectin": 与 choices/knowledge_points 同款 selectin eager load
    # - order_by="QuestionImage.order_index": 渲染时按 order_index 排（同 Choice）
    images: Mapped[list[QuestionImage]] = relationship(
        "QuestionImage",
        back_populates="question",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="QuestionImage.order_index",
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

    chapter: Mapped[Chapter] = relationship("Chapter", back_populates="questions")
    owner: Mapped[User] = relationship("User", lazy="selectin")
    # M3-1a-2：反向到题组。注意**不写 delete-orphan**（补遗 §丙-2）：
    # group_id 可空 + delete-orphan ⇒ "把小题移出题组"会被 ORM **删题**而不是置
    # NULL。删除一律交给 DB 的 ON DELETE CASCADE + passive_deletes=True。
    group: Mapped[QuestionGroup | None] = relationship(
        "QuestionGroup", back_populates="questions"
    )

    @property
    def knowledge_point_ids(self) -> list[int]:
        """题目关联的 KP id 列表（D-43 review8 P1 + QuestionRead 字段需求）。

        SQLAlchemy 2.0 docs（selectin eager loading）：knowledge_points 已
        lazy="selectin"，访问时触发单条 IN 子查询批量加载（selectin strategy），
        不触发 N+1。配合 FastAPI response_model=QuestionRead 序列化（Depends
        get_db yield 内）确保访问期间 session 仍开放，selectin load 可成功。
        """
        return [kp.id for kp in self.knowledge_points]

    @property
    def knowledge_point_names(self) -> list[str]:
        """题目关联的 KP 名列表（M3-1b brief §1 改动 3 — 表格"知识点标签"列）。

        同 knowledge_point_ids：knowledge_points 是 lazy="selectin"，
        访问时批量加载，不触发 N+1。Pydantic v2 from_attributes=True
        自动读本 property，QuestionRead 无需额外 validator。
        """
        return [kp.name for kp in self.knowledge_points]

    @property
    def image_count(self) -> int:
        """题目图片数（M3-1b brief §1 改动 3 — 表格"图片数"列）。

        images 同为 lazy="selectin"，无 N+1；只读 property，不加列不加迁移。
        """
        return len(self.images)

    __table_args__ = (
        Index(
            "ix_questions_owner_chapter_difficulty",
            "owner_user_id",
            "chapter_id",
            "difficulty",
        ),
        # M3-1a-2 补遗 §丙-3：题序唯一。PG 对 NULL 不做唯一判定 ⇒
        # 多行 group_id IS NULL 互不冲突，单题不受影响。
        UniqueConstraint(
            "group_id", "group_order", name="uq_questions_group_order"
        ),
    )


class Choice(Base):
    """选择题选项（仅 choice 类型题目有）。

    label：A/B/C/D 字母标签（最大 8 字符为后续"选项 K" 留位）。
    content：选项正文。
    is_correct：是否为正确选项。
    order_index：排序（M2-A.0 渲染按此字段排序）。

    与 Question 是 1 对多；删 Question 时 cascade 自动清空。
    """

    __tablename__ = "choices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(8), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=SAFalse()
    )
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    question: Mapped[Question] = relationship("Question", back_populates="choices")

    __table_args__ = (
        Index("ix_choices_question_order", "question_id", "order_index"),
    )


# ──────────────────── S2 tier → difficulty 显式映射（v0.5 §3.2 / M2-S2 brief §五）────────
#
# 落点理由：紧贴 Tier + QuestionDifficulty 两 enum 定义（同一文件末），让 reader
# 看到「两 enum 同值空间」的契约。
#
# 为什么不直接 `return QuestionDifficulty(t.value)` 后用 type 强制：
# - Pydantic / mypy 都不强制 Tier == QuestionDifficulty；两个 enum 独立定义
#   + 独立 SAEnum 列。
# - 显式 mapping 函数 = 单一来源契约，避免后续任一 enum 改动后悄悄漂移。
# - 同值空间恒等（D=D / C=C / B=B / A=A）= brief §三 §五 拍板定论。
def tier_to_difficulty(t: Tier) -> QuestionDifficulty:
    """Tier → QuestionDifficulty 显式映射（同值空间恒等映射）。

    两 enum 值空间必须同构（顺序 + 元素 + 唯一），由 ``test_tier_difficulty_value_space_isomorphic``
    守住；本函数是「同构的具体兑现」= 单一来源契约。

    Raises:
        ValueError: 当 enum 值漂移（brief §五 开工核对项）时显式报错。
    """
    return QuestionDifficulty(t.value)


# ──────────────── M2-A.1 题目图片承载（v0.5 §3.4 / brief §3.1） ───────────────
#
# 范围锁定（brief §3.1）：
# - 独立 ``question_images`` 表（1:N，与 choices 同构）
# - 12 列：id / question_id / order_index / file_ext / storage_path /
#   source / desensitization_status / desensitized_at / uploaded_at /
#   uploaded_by_user_id / oss_object_key / oss_uploaded_at
# - 2 enum：QuestionImageSource (self_built | external_imported) +
#           DesensitizationStatus (pending | done | skipped)
# - svg 不收（v0.5 §3.4 风险 + brief §3.1 file_ext 注释）；
#   文件后缀限定 png/jpg/jpeg/webp（接口层 MIME 校验，model 层仅做长度约束）
#
# 字段语义：
# - question_id FK → questions.id CASCADE（删 Question 自动清图）
# - uploaded_by_user_id FK → users.id RESTRICT（删 user 阻挡；与 Question 同款）
# - order_index：渲染顺序（与 Choice.order_index 同款语义；1-based 排序由接口层
#   控制，model 层仅存整数）
# - storage_path：本地相对路径（接口层写；UPLOAD_ROOT-based 路径模板
#   ``{UPLOAD_ROOT}/{chapter_id}/{question_id}/{image_id}.{ext}``）
# - source / desensitization_status：M2-A.1 新增独立 enum（不与
#   KnowledgeReviewStatus 复用——语义不同：source 是"来源"，desens status
#   是"脱敏进度"；与 review 状态"老师审阅"是另一维度）
# - desensitized_at：脱敏完成时间戳（M3 实际写入；S1/M2 = NULL）
# - uploaded_at：上传时间戳（server_default=func.now()；不暴露 client 写）
# - oss_object_key + oss_uploaded_at：M3 预留字段；S1/M2 阶段 NULL
#
# 1:N vs ARRAY（brief §3.3 拍板）：1:N。判据 = 排序/单图删除/脱敏标记/
# 来源追溯/OSS 状态/上传者追溯 —— ARRAY 无法满足任一项。
#
# 范围外（brief §3 锁 + §6 锁）：
# - 实际文件 IO（接口层走 service 路径；本阶段 model 仅承载元数据）
# - MIME 校验 / 实际大小校验（接口层；本 model 信任 file_ext 字符串）
# - OSS 实际上传（M3 范围）
# - 脱敏实际处理（M3 范围）
# - 共建 is_public（M2-A.0 lock MVP）


class QuestionImage(Base):
    """题目图片承载（地理等图像密集学科；v0.5 §3.4 + brief §3.1 硬约束）。

    与 Question 是 1 对多（与 Choice 同构）；删 Question 时 cascade 自动清空。
    字段语义详见上方节注释。
    """

    __tablename__ = "question_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # M3-1a-2（brief §1 改表 5 + 补遗 §乙-1）：D4(a) 两入口同一张表。
    # - question_id 改可空：材料图挂题组时为 NULL
    # - group_id 新增：小题图为 NULL
    # - CHECK 防孤儿图（两者都 NULL 的行无处可挂）
    question_id: Mapped[int | None] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("question_groups.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # 8 字符 = 够 png/jpg/jpeg/webp/gif/bmp/tiff；svg 不收（brief §3.1）
    file_ext: Mapped[str] = mapped_column(String(8), nullable=False)
    # 512 字符 = 足够 ${UPLOAD_ROOT}/{chapter_id}/{question_id}/{image_id}.{ext}
    # 留余量给未来 UPLOAD_ROOT 变长（如 OSS bucket prefix）
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    source: Mapped[QuestionImageSource] = mapped_column(
        SAEnum(
            QuestionImageSource,
            name="question_image_source_enum",
            native_enum=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    desensitization_status: Mapped[DesensitizationStatus] = mapped_column(
        SAEnum(
            DesensitizationStatus,
            name="desensitization_status_enum",
            native_enum=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=DesensitizationStatus.PENDING,
        server_default=DesensitizationStatus.PENDING.value,
    )
    desensitized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    uploaded_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # M3 预留：OSS object key（阿里云 OSS bucket = thp-images-{env}）
    oss_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # M3 预留：OSS 上传完成时间
    oss_uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    question: Mapped[Question | None] = relationship(
        "Question", back_populates="images"
    )
    # M3-1a-2：材料图的归属（挂组时 question=None）
    group: Mapped[QuestionGroup | None] = relationship(
        "QuestionGroup", back_populates="images"
    )

    __table_args__ = (
        # 渲染按 (question_id, order_index) 排；同 Choice 模式
        Index(
            "ix_question_images_question_order",
            "question_id",
            "order_index",
        ),
        # 防孤儿图（补遗 §乙-1 / brief §1 改表 5）
        # D4(a) 要的是**互斥**不是"至少一个非空"（星轨 P2 2026-10-23）：
        # (question_id IS NULL) <> (group_id IS NULL)
        # - 两者都 NULL = 孤儿图，拒绝
        # - 两者都有值 = 同一张图既算小题图又算材料图 ⇒ 渲染两次 + 删题连带删材料图，拒绝
        # 旧写法 OR 只挡住前者。
        CheckConstraint(
            "(question_id IS NULL) <> (group_id IS NULL)",
            name="ck_question_images_owner_not_null",
        ),
    )

# ──────────────────── M3-1a-2 题组模型（brief §1 + 补遗与定稿 2026-10-23） ────────────────────
#
# 题组 = 材料 + 全部小题的容器（星轨 08:14 §三）。
#
# 为什么不用 questions 自引用（brief §0.8）：
# 材料不是题 —— 没有题型、没有答案，不该进"题目列表 / 题量统计"。
# 自引用会让每处查询都得记得排除"假题"，迟早漏。
#
# 明确不建的列（brief §1，防止实现时"顺手加"）：
# ❌ title  —— 模型方案未列；材料在块里，列表页显示「题组（N 小题）」+ 首块摘要
# ❌ type   —— 题组内允许混合题型，题组本身不设题型
# ❌ points —— 分值按小题各自设，题组总分 = 小题之和，材料不计分
# ❌ content—— 材料统一走 content_blocks 块序列，留 content 会双源真相


# 块类型取值白名单（补遗 §丙-1：DB 用 String(16) 不建 enum 类型，
# 取值校验放这里 + Pydantic Literal）。
# 刻意**不建 PG native enum**：加块类型要 ALTER TYPE，而 0002 的 CREATE TYPE
# 非幂等就是现成的坑（MEMORY §3）；且《材料结构方案》§二的立论就是
# "以后加公式块/音频块不改表"。DB 允许脏值、应用层拒绝 —— 有意的取舍。
OWNER_TYPE_GROUP = "group"
OWNER_TYPE_QUESTION = "question"  # 预留：题干将来也能图文混排（1a-2 不做 UI）

BLOCK_TYPE_TEXT = "text"
BLOCK_TYPE_IMAGE = "image"
BLOCK_TYPE_TABLE = "table"
# 注意：BLOCK_TYPE_FORMULA / _AUDIO **不列** —— 它们是"以后加"的情形，
# 不写进常量才能体现"加块类型不改表"。真要用时再加常量 + Pydantic Literal。

# 题组-知识点多对多关联表：照抄 question_knowledge_points 结构（brief §0.5）。
# KnowledgePoint 自身无 owner_user_id（KP 归属 = chapter.owner_user_id），
# 关联表本身无业务归属字段。
group_knowledge_points = Table(
    "group_knowledge_points",
    Base.metadata,
    Column(
        "group_id",
        Integer,
        ForeignKey("question_groups.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "knowledge_point_id",
        Integer,
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class QuestionGroup(Base):
    """题组（材料 + 全部小题；D1(a) 详情一次返回两者）。

    归属（D-29 题库属教师个人资产）：owner_user_id FK → users.id RESTRICT，
    与 Question 同款。chapter_id FK → chapters.id CASCADE。

    难度（D2(a) / 补遗 §乙-4）：**难度只存组上**。小题的 difficulty 列是
    **组难度的派生缓存**，唯一写入源 = 本表的 difficulty。挂小题时 API 层写
    三字段（group_id / group_order / difficulty），改组难度时同事务批量更新。
    本 model 不自动同步 —— 同步逻辑抽在 API 层 _sync_group_difficulty 一处，
    两个调用点，不写两遍。

    已知限制（补遗 §戊-1）：本笔不提供"移出题组"端点。将来移出后小题保留
    最后一次同步的 difficulty，需人工重设。留给 1c-2。
    """

    __tablename__ = "question_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    difficulty: Mapped[QuestionDifficulty] = mapped_column(
        SAEnum(
            QuestionDifficulty,
            name="question_difficulty_enum",
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

    # 🔴 绝不能写 cascade="delete-orphan"（补遗 §丙-2）：
    # group_id 可空 + delete-orphan ⇒ "把小题移出题组"会被 ORM **删题**。
    # 删除一律交给 DB 的 ON DELETE CASCADE（passive_deletes=True）。
    questions: Mapped[list[Question]] = relationship(
        back_populates="group",
        cascade="save-update, merge",
        passive_deletes=True,
        lazy="selectin",
        order_by="Question.group_order",
    )
    images: Mapped[list[QuestionImage]] = relationship(
        back_populates="group",
        cascade="save-update, merge",
        passive_deletes=True,
        lazy="selectin",
        order_by="QuestionImage.order_index",
    )
    knowledge_points: Mapped[list[KnowledgePoint]] = relationship(
        KnowledgePoint,
        secondary="group_knowledge_points",
        lazy="selectin",
    )
    chapter: Mapped[Chapter] = relationship("Chapter")
    owner: Mapped[User] = relationship("User", lazy="selectin")

    @property
    def small_question_count(self) -> int:
        """小题数（D3(a) 题量按小题数累加 —— 这就是计数口径）。"""
        return len(self.questions)

    @property
    def total_points(self) -> float:
        """题组总分 = 小题 points 之和（材料不计分）。"""
        return float(sum(q.points or 0 for q in self.questions))

    @property
    def knowledge_point_ids(self) -> list[int]:
        return [kp.id for kp in self.knowledge_points]


class ContentBlock(Base):
    """材料块序列（块模型；MVP 只用 group，question 预留）。

    ⚠️ **owner_type / owner_id 是多态裸列，不建 FK**（补遗 §乙-2）。
    这意味着 DB 层没有任何东西把块绑到题组上：
    - questions.group_id FK CASCADE ✅ 会删小题
    - question_images.group_id FK CASCADE ✅ 会删组图
    - content_blocks ❌ **没人管** —— text / table 块会留下来成孤儿

    更糟的是 **image 块会被 image_id 的 CASCADE 带走**（图没了）⇒ 结果是
    "3 块里删掉 1 块、留 2 块"，只数块数或只看图会**假绿**。

    ⇒ 删题组时**必须显式** delete content_blocks（API 层，commit B）。
    ⇒ 验收时三张表**分开查**残留，不能合并成一个数（判据 13）。

    block_type 用 String(16) 而非 native enum（补遗 §丙-1），理由见上方常量区。
    取值校验放应用层（Pydantic Literal），DB 允许脏值 —— 有意的取舍。
    """

    __tablename__ = "content_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_type: Mapped[str] = mapped_column(String(16), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    block_type: Mapped[str] = mapped_column(String(16), nullable=False)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # image 块只引用不存文件（图本体在 question_images）
    image_id: Mapped[int | None] = mapped_column(
        ForeignKey("question_images.id", ondelete="CASCADE"),
        nullable=True,
    )
    # 块模型的 JSON 坑（brief §0.7）：直接写 JSONB 会让 SQLite 建表崩
    # （本地红 / CI 绿）⇒ 必须 with_variant。**全仓 0 先例**，本笔首次引入。
    # 🔴 none_as_null=True（**必加**，2026-10-23 B 笔实测踩到）：
    # SQLAlchemy 的 JSON 列默认 none_as_null=False ⇒ Python 的 None 被序列化成
    # JSON 字面量 `null` 存进列里，**不是 SQL NULL**。
    # 于是 CHECK 判据 `table_json IS NULL` 恒为 false ⇒ 任何 text / table 块
    # （另一个 JSON 列为 None）都会被 CHECK 误拒 —— 建表能过，**写入全炸**。
    # 加 none_as_null=True ⇒ None 落成真正的 SQL NULL，CHECK 判据成立。
    # PG 侧同理（JSONB 也是 JSON 语义，`IS NULL` 对 JSON null 为 false）。
    table_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON(none_as_null=True).with_variant(
            postgresql.JSONB(none_as_null=True), "postgresql"
        ),
        nullable=True,
    )
    # 图片宽度 50/75/100 存这里（补遗 §乙-3 现在加，省一次迁移）；
    # table 块预留 {"col_widths": [...]}。本笔只保证列存在，不做取值校验
    # —— 宽度取值属 1c-2 编辑器的职责，且 JSON 上的 CHECK 在 SQLite 侧难验。
    # none_as_null=True —— 同 table_json 的理由（否则 meta=None 落成 JSON null）
    meta: Mapped[dict[str, Any] | None] = mapped_column(
        JSON(none_as_null=True).with_variant(
            postgresql.JSONB(none_as_null=True), "postgresql"
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

    __table_args__ = (
        UniqueConstraint(
            "owner_type",
            "owner_id",
            "order_index",
            name="uq_content_blocks_owner_order",
        ),
        Index("ix_content_blocks_owner", "owner_type", "owner_id"),
        # 字段自洽 CHECK（按 block_type 验字段）。
        # 注意这**不是**取值白名单 —— 取值白名单刻意不加（换扩展性），
        # 只保证"text 块必须有正文"这类结构不变量。
        CheckConstraint(
            "block_type != 'text' OR (text_content IS NOT NULL "
            "AND image_id IS NULL AND table_json IS NULL)",
            name="ck_content_blocks_text_shape",
        ),
        CheckConstraint(
            "block_type != 'image' OR (image_id IS NOT NULL "
            "AND text_content IS NULL AND table_json IS NULL)",
            name="ck_content_blocks_image_shape",
        ),
        CheckConstraint(
            "block_type != 'table' OR (table_json IS NOT NULL "
            "AND text_content IS NULL AND image_id IS NULL)",
            name="ck_content_blocks_table_shape",
        ),
    )
