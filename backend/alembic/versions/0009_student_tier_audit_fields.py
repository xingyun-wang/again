"""alembic 迁移：students 表加 2 个 audit 字段（M2-S2 档位管理）。

触发：M2-S2 brief §六（档位管理 = manual override service + 3 student endpoints）
基础：0006_owner_user_id (User 表 + 归属) + 0007_questions + 0008_assignments

字段：
- tier_changed_by_user_id: FK → users.id (ondelete=RESTRICT)
- tier_changed_at: TIMESTAMPTZ (nullable)
两字段 nullable = True ⇒ 既存 Student 行默认 NULL（历史未追踪；不回填）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_student_tier_audit_fields"
down_revision: str | None = "0008_assignments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. tier_changed_by_user_id: FK → users.id (ondelete=RESTRICT)
    op.add_column(
        "students",
        sa.Column(
            "tier_changed_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    # 2. tier_changed_at: TIMESTAMPTZ (nullable)
    op.add_column(
        "students",
        sa.Column("tier_changed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # 倒序拆：先改档时间戳，再改档人
    op.drop_column("students", "tier_changed_at")
    op.drop_column("students", "tier_changed_by_user_id")
