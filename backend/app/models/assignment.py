"""作业单 ORM（M2-A.1 · v0.5 §3.6 老师审阅流程第 1 步产物）。

设计要点：
- ``Assignment`` = 一次出题行为的结果(老师选题 → 引擎出题 → 老师审阅前状态)
- ``AssignmentItem`` = 作业中各题(1 assignment : N items;与 Choice/QuestionImage 同构)
- tier_origin 记录"该题是从哪个池抽的"= 反马太审计字段(v0.5 §3.5 判据追溯)
- seed 记录"生成时用的随机种子"= 可复现出题(同 seed 必同结果)
- ondelete:
    - chapter_id → RESTRICT(删 chapter 阻挡,保留历史作业单引用完整)
    - question_id → RESTRICT(删 question 阻挡,避免作业单引用悬空)
    - assignment_id (from items) → CASCADE(删 assignment 自动清 items)
- 归属 owner_user_id → users.id RESTRICT(M1-B B 沿用;D-29 题库个人资产原则)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.academic import Chapter, Question, QuestionDifficulty, User

if TYPE_CHECKING:
    from app.models.academic import Chapter as _Chapter  # noqa: F401


class Assignment(Base):
    """差异化作业单（M2-A.1 · v0.5 §3.6 第 1 步产物）。

    字段语义:
    - tier: 作业目标档位(D/C/B/A);本笔初始档位 = 老师手动设(v0.5 §3.2);
            S2 才会加手动覆盖
    - total_count: 作业总题数(生成时确定;S3 老师审阅可删题 - 留 S3)
    - d_count / c_count / b_count / a_count: 各档池抽题数(反马太判据审计字段;
            D 档作业 100 题 → d_count=80, c_count=20, b_count=0, a_count=0)
    - seed: 随机种子(可复现抽题;同 seed + 同 chapter 题库 → 同 items 列表)
    """

    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    tier: Mapped[QuestionDifficulty] = mapped_column(
        SAEnum(
            QuestionDifficulty,
            name="question_difficulty_enum",
            native_enum=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    total_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # 4 档分布(反马太审计字段;不写业务逻辑,只读)
    d_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    c_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    b_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    a_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # 种子(可复现;None = 用系统时间,不可复现)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 关系
    items: Mapped[list[AssignmentItem]] = relationship(
        "AssignmentItem",
        back_populates="assignment",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AssignmentItem.position",
    )
    chapter: Mapped[Chapter] = relationship("Chapter", lazy="selectin")
    owner: Mapped[User] = relationship("User", lazy="selectin")

    __table_args__ = (
        Index(
            "ix_assignments_owner_chapter_tier",
            "owner_user_id",
            "chapter_id",
            "tier",
        ),
    )


class AssignmentItem(Base):
    """作业单题目行(1 assignment : N items;与 Choice/QuestionImage 同构)。

    tier_origin 记录"该题是从哪个池抽的":
    - D 池抽的题 → D(D 档作业的 80% 基础题)
    - C 池抽的题 → C(D 档作业的 20% 反马太拔高 / 或 C 档作业的 100%)
    - B/A 同理

    position 记录在作业中的位置(0-indexed;按 select_questions 返回顺序)
    """

    __tablename__ = "assignment_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    tier_origin: Mapped[QuestionDifficulty] = mapped_column(
        SAEnum(
            QuestionDifficulty,
            name="question_difficulty_enum",
            native_enum=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )

    assignment: Mapped[Assignment] = relationship(
        "Assignment", back_populates="items"
    )
    question: Mapped[Question] = relationship(
        "Question", lazy="selectin"
    )

    __table_args__ = (
        Index(
            "ix_assignment_items_assignment_position",
            "assignment_id",
            "position",
        ),
    )
