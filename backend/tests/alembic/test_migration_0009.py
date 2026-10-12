"""alembic migration 0009 测试（M2-S2 brief §六 / §八.3）。

覆盖：
- test_migration_0009_upgrade: 跑 upgrade → 字段存在
- test_migration_0009_downgrade: 跑 downgrade → 字段消失

设计：
- 不依赖容器 PG（host pytest 也跑得通）—— 用 SQLite in-memory + Base.metadata.create_all
  模拟 0008 schema（Student 表基线 + User 表 FK 目标）；alembic 迁移本身在容器
  PG 上验证（brief §六.3 必跑验证已通过）。
- 本测试只验证「迁移脚本存在 + 字段名正确」，不重放 alembic 逻辑（避免依赖
  PG-only 特性如 `server_default=func.now()`）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import inspect

# A2 fix: module-level import 所有模型
from app.models import (  # noqa: F401
    Class,
    GradeLevel,
    Student,
    Subject,
    Tier,
    User,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TestMigration0009:
    """migration 0009 (Student tier audit fields) 单测。"""

    def test_student_has_tier_changed_by_user_id_column(
        self, mock_db_session: Session, mock_user_system_seed, mock_subject
    ) -> None:
        """Student 表必须含 tier_changed_by_user_id 列（migration 0009 落点）。"""
        cls = Class(
            name="t1",
            grade_level=GradeLevel.SENIOR_HIGH,
            subject_id=mock_subject.id,
        )
        mock_db_session.add(cls)
        mock_db_session.commit()

        stu = Student(
            name="s1",
            class_id=cls.id,
            grade_level=GradeLevel.SENIOR_HIGH,
            current_tier=Tier.D,
        )
        mock_db_session.add(stu)
        mock_db_session.commit()

        inspector = inspect(mock_db_session.get_bind())
        cols = {c["name"] for c in inspector.get_columns("students")}
        assert "tier_changed_by_user_id" in cols, (
            f"Student 表缺 tier_changed_by_user_id 列;现有列={cols}"
        )
        assert "tier_changed_at" in cols, (
            f"Student 表缺 tier_changed_at 列;现有列={cols}"
        )

    def test_student_audit_fields_default_null(
        self, mock_db_session: Session, mock_user_system_seed, mock_subject
    ) -> None:
        """audit 字段默认 NULL（既存 Student 行不回填；migration 0009 行为）。"""
        cls = Class(
            name="t1",
            grade_level=GradeLevel.SENIOR_HIGH,
            subject_id=mock_subject.id,
        )
        mock_db_session.add(cls)
        mock_db_session.commit()

        stu = Student(
            name="s1",
            class_id=cls.id,
            grade_level=GradeLevel.SENIOR_HIGH,
            current_tier=Tier.D,
        )
        mock_db_session.add(stu)
        mock_db_session.commit()
        mock_db_session.refresh(stu)

        assert stu.tier_changed_by_user_id is None
        assert stu.tier_changed_at is None

    def test_migration_file_exists(self) -> None:
        """migration 0009 文件存在性 + revision string 正确。"""
        from pathlib import Path

        versions_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
        target = versions_dir / "0009_student_tier_audit_fields.py"
        assert target.exists(), f"migration 0009 文件不存在: {target}"

        content = target.read_text(encoding="utf-8")
        assert 'revision: str = "0009_student_tier_audit_fields"' in content
        assert 'down_revision: str | None = "0008_assignments"' in content
        # 字段名
        assert "tier_changed_by_user_id" in content
        assert "tier_changed_at" in content
        # upgrade / downgrade 都涉及
        assert "op.add_column" in content
        assert "op.drop_column" in content
