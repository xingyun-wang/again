"""override_student_tier service 测试（M2-S2 brief §七 / §八.4）。

覆盖：
- test_override_student_tier_happy_path: 改 current_tier + audit 字段写入
- test_override_student_tier_cross_teacher: 他人班学生 → 404
- test_override_student_tier_invalid_tier: 非 Tier enum → 422
- test_override_student_tier_nonexistent_student_404: student 不存在 → 404
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

# A2 fix: module-level import 所有模型
from app.models import (  # noqa: F401
    Class,
    GradeLevel,
    Student,
    Subject,
    Tier,
    User,
)
from app.services.student_tier import override_student_tier

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _make_class_session(
    session: Session,
    owner_user_id: int,
    subject_grade: GradeLevel = GradeLevel.SENIOR_HIGH,
) -> Class:
    """helper: 造一个 Subject + Class，owner=owner_user_id。"""
    sub = Subject(
        name="测试学科",
        grade_level=subject_grade,
        owner_user_id=owner_user_id,
    )
    session.add(sub)
    session.commit()
    cls = Class(
        name="测试班级",
        grade_level=subject_grade,
        subject_id=sub.id,
    )
    session.add(cls)
    session.commit()
    session.refresh(cls)
    return cls


class TestOverrideStudentTier:
    """override_student_tier service 单测。"""

    def test_override_student_tier_happy_path(
        self, mock_db_session: Session, mock_user_system_seed
    ) -> None:
        """happy path: 改 current_tier D→A + audit 字段非 NULL。"""
        cls = _make_class_session(mock_db_session, mock_user_system_seed.id)
        stu = Student(
            name="张三",
            class_id=cls.id,
            grade_level=GradeLevel.SENIOR_HIGH,
            current_tier=Tier.D,
        )
        mock_db_session.add(stu)
        mock_db_session.commit()
        mock_db_session.refresh(stu)

        result = override_student_tier(
            session=mock_db_session,
            current_user_id=mock_user_system_seed.id,
            student_id=stu.id,
            new_tier=Tier.A,
        )

        assert result["old"] == Tier.D
        assert result["new"] == Tier.A
        assert result["student_id"] == stu.id
        assert result["tier_changed_by_user_id"] == mock_user_system_seed.id
        assert result["tier_changed_at"] is not None

        # DB 持久化校验
        mock_db_session.refresh(stu)
        assert stu.current_tier == Tier.A
        assert stu.tier_changed_by_user_id == mock_user_system_seed.id
        assert stu.tier_changed_at is not None

    def test_override_student_tier_cross_teacher(
        self, mock_db_session: Session, mock_user_system_seed
    ) -> None:
        """他人班学生 → 404（跨用户隔离）。"""
        # user1 (system-seed) 拥有 cls1
        cls1 = _make_class_session(mock_db_session, mock_user_system_seed.id)
        stu1 = Student(
            name="user1-学生",
            class_id=cls1.id,
            grade_level=GradeLevel.SENIOR_HIGH,
            current_tier=Tier.D,
        )
        mock_db_session.add(stu1)
        mock_db_session.commit()
        mock_db_session.refresh(stu1)

        # 创 user2
        u2 = User(id=2, name="user-2", is_system_owned=False)
        mock_db_session.add(u2)
        mock_db_session.commit()

        # user2 改 user1 的学生 → 404
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            override_student_tier(
                session=mock_db_session,
                current_user_id=u2.id,
                student_id=stu1.id,
                new_tier=Tier.A,
            )
        assert exc_info.value.status_code == 404
        # DB 未被改
        mock_db_session.refresh(stu1)
        assert stu1.current_tier == Tier.D
        assert stu1.tier_changed_by_user_id is None

    def test_override_student_tier_invalid_tier(
        self, mock_db_session: Session, mock_user_system_seed
    ) -> None:
        """非 Tier enum → 422（service 层兜底）。"""
        cls = _make_class_session(mock_db_session, mock_user_system_seed.id)
        stu = Student(
            name="s1",
            class_id=cls.id,
            grade_level=GradeLevel.SENIOR_HIGH,
            current_tier=Tier.D,
        )
        mock_db_session.add(stu)
        mock_db_session.commit()
        mock_db_session.refresh(stu)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            override_student_tier(
                session=mock_db_session,
                current_user_id=mock_user_system_seed.id,
                student_id=stu.id,
                new_tier="X",  # type: ignore[arg-type]
            )
        assert exc_info.value.status_code == 422

    def test_override_student_tier_nonexistent_student_404(
        self, mock_db_session: Session, mock_user_system_seed
    ) -> None:
        """student 不存在 → 404。"""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            override_student_tier(
                session=mock_db_session,
                current_user_id=mock_user_system_seed.id,
                student_id=99999,
                new_tier=Tier.A,
            )
        assert exc_info.value.status_code == 404
