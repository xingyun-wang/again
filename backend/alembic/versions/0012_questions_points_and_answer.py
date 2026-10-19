"""alembic 迁移：questions 表加 2 列（points + answer_text）。

触发：M3-1a brief §1.1（2026-10-19 星云 21:02 拍）
基础：0007_questions（题库基础）+ 0008_assignments + 0009 + 0010 + 0011

字段（brief §1.1 严格两列，不夹带批次/学生/条码）：
- points: Numeric(5,1) NOT NULL server_default='2.0'
  题型默认 2.0 分；Teacher 改档时手动覆盖（M3+ 决策）
- answer_text: Text NULL（仅主观题 / 填空题存；选择题答案仍走 Choice.is_correct）

边界（per brief §2）：
- 不夹带 batch_id / student_id / barcode 字段（属 0013 推迟）
- 不动 0011 之前的迁移
- 不加额外索引（model 同款字段也不加 index=True；后续切片再补）

回滚：
- downgrade() = drop 两列（可逆；data loss 可接受 — 题库 1a 阶段）
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_questions_points_and_answer"
down_revision: str | None = "0011_question_images"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. points: Numeric(5,1) NOT NULL server_default='2.0'
    op.add_column(
        "questions",
        sa.Column(
            "points",
            sa.Numeric(5, 1),
            nullable=False,
            server_default=sa.text("2.0"),
        ),
    )
    # 2. answer_text: Text NULL（仅主观题 / 填空题；选择题答案仍走 Choice.is_correct）
    op.add_column(
        "questions",
        sa.Column(
            "answer_text",
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # 倒序拆：answer_text → points
    op.drop_column("questions", "answer_text")
    op.drop_column("questions", "points")
