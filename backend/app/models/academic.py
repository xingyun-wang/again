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

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy import false as SAFalse
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

    __table_args__ = (
        Index(
            "ix_questions_owner_chapter_difficulty",
            "owner_user_id",
            "chapter_id",
            "difficulty",
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