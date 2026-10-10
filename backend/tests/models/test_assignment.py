"""Assignment model test（M2-A.1 · v0.5 §3.6 + §3.5 反马太审计字段）。

测试覆盖：
- 12 列字段（含 4 档分布审计字段 d_count/c_count/b_count/a_count）
- FK 约束（owner_user_id / chapter_id / question_id）
- cascade（删 Assignment → 自动清 AssignmentItem）
- seed 可空（同 seed 必同结果留 select_questions 单测）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.exc import IntegrityError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TestAssignmentModel:
    """Assignment 表 + AssignmentItem 表 单测（用 mock_db_session fixture）。"""

    def test_create_assignment_basic(
        self, mock_db_session: Session, mock_user_system_seed, mock_textbook
    ) -> None:
        from app.models import Assignment, Chapter

        ch = Chapter(
            textbook_id=mock_textbook.id,
            owner_user_id=mock_user_system_seed.id,
            chapter_number=1,
            title="t1",
            content_summary="sum",
            extraction_source="detected",
        )
        mock_db_session.add(ch)
        mock_db_session.commit()

        a = Assignment(
            owner_user_id=mock_user_system_seed.id,
            chapter_id=ch.id,
            tier="D",
            total_count=100,
            d_count=80,
            c_count=20,
            b_count=0,
            a_count=0,
            seed=42,
        )
        mock_db_session.add(a)
        mock_db_session.commit()
        mock_db_session.refresh(a)

        assert a.id is not None
        assert a.tier.value == "D"
        assert a.total_count == 100
        assert a.d_count == 80
        assert a.c_count == 20
        assert a.b_count == 0
        assert a.a_count == 0
        assert a.seed == 42

    def test_assignment_seed_nullable(
        self, mock_db_session: Session, mock_user_system_seed, mock_textbook
    ) -> None:
        """seed 可空（None = 不可复现 = 系统时间）。"""
        from app.models import Assignment, Chapter

        ch = Chapter(
            textbook_id=mock_textbook.id,
            owner_user_id=mock_user_system_seed.id,
            chapter_number=1,
            title="t1",
            content_summary="sum",
            extraction_source="detected",
        )
        mock_db_session.add(ch)
        mock_db_session.commit()

        a = Assignment(
            owner_user_id=mock_user_system_seed.id,
            chapter_id=ch.id,
            tier="C",
            total_count=50,
            d_count=0,
            c_count=50,
            b_count=0,
            a_count=0,
            seed=None,
        )
        mock_db_session.add(a)
        mock_db_session.commit()
        mock_db_session.refresh(a)
        assert a.seed is None

    def test_assignment_invalid_tier_raises(
        self, mock_db_session: Session, mock_user_system_seed, mock_textbook
    ) -> None:
        """tier 必须 ∈ {D, C, B, A}（PG enum 约束）。"""
        from app.models import Assignment, Chapter

        ch = Chapter(
            textbook_id=mock_textbook.id,
            owner_user_id=mock_user_system_seed.id,
            chapter_number=1,
            title="t1",
            content_summary="sum",
            extraction_source="detected",
        )
        mock_db_session.add(ch)
        mock_db_session.commit()

        a = Assignment(
            owner_user_id=mock_user_system_seed.id,
            chapter_id=ch.id,
            tier="X",  # type: ignore[arg-type]
            total_count=50,
        )
        mock_db_session.add(a)
        with pytest.raises(IntegrityError):
            mock_db_session.commit()
        mock_db_session.rollback()

    def test_assignment_FK_chapter_id(
        self, mock_db_session: Session, mock_user_system_seed
    ) -> None:
        """chapter_id FK 约束：不存在的 chapter_id 应 raise IntegrityError。"""
        from app.models import Assignment

        a = Assignment(
            owner_user_id=mock_user_system_seed.id,
            chapter_id=99999,  # 不存在
            tier="D",
            total_count=50,
        )
        mock_db_session.add(a)
        with pytest.raises(IntegrityError):
            mock_db_session.commit()
        mock_db_session.rollback()

    def test_assignment_FK_owner_user_id(self, mock_db_session: Session) -> None:
        """owner_user_id FK 约束：不存在的 user_id 应 raise。"""
        from app.models import Assignment, Chapter, Textbook

        tb = Textbook(
            name="t", file_path="uploads/0/x.pdf", owner_user_id=1
        )  # owner=1 (system seed)
        mock_db_session.add(tb)
        mock_db_session.commit()
        ch = Chapter(
            textbook_id=tb.id,
            owner_user_id=1,
            chapter_number=1,
            title="t1",
            content_summary="sum",
            extraction_source="detected",
        )
        mock_db_session.add(ch)
        mock_db_session.commit()

        a = Assignment(
            owner_user_id=99999,  # 不存在
            chapter_id=ch.id,
            tier="D",
            total_count=50,
        )
        mock_db_session.add(a)
        with pytest.raises(IntegrityError):
            mock_db_session.commit()
        mock_db_session.rollback()

    def test_assignment_items_cascade(
        self, mock_db_session: Session, mock_user_system_seed, mock_textbook
    ) -> None:
        """删 Assignment → 自动清 AssignmentItem（cascade="all, delete-orphan"）。"""
        from app.models import Assignment, AssignmentItem, Chapter, Question

        # 建 chapter
        ch = Chapter(
            textbook_id=mock_textbook.id,
            owner_user_id=mock_user_system_seed.id,
            chapter_number=1,
            title="t1",
            content_summary="sum",
            extraction_source="detected",
        )
        mock_db_session.add(ch)
        mock_db_session.commit()

        # 建 question
        q = Question(
            owner_user_id=mock_user_system_seed.id,
            chapter_id=ch.id,
            content="q1",
            difficulty="D",
            type="choice",
        )
        mock_db_session.add(q)
        mock_db_session.commit()

        # 建 assignment + item
        a = Assignment(
            owner_user_id=mock_user_system_seed.id,
            chapter_id=ch.id,
            tier="D",
            total_count=1,
            d_count=1,
        )
        mock_db_session.add(a)
        mock_db_session.commit()

        item = AssignmentItem(
            assignment_id=a.id,
            question_id=q.id,
            position=0,
            tier_origin="D",
        )
        mock_db_session.add(item)
        mock_db_session.commit()

        # 删 assignment → items 应被 cascade 清
        mock_db_session.delete(a)
        mock_db_session.commit()

        # 验证 items 没了
        from sqlalchemy import select

        from app.models import AssignmentItem

        stmt = select(AssignmentItem).where(AssignmentItem.assignment_id == a.id)
        assert mock_db_session.execute(stmt).scalars().all() == []
