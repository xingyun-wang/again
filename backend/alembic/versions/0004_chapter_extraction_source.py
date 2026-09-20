"""chapters.extraction_source 字段（M2 工单 A：P0-1 + P0-3 合并修复）

Revision ID: 0004_chapter_extraction_source
Revises: 0003_lesson_plans
Create Date: 2026-09-20

动机（D-28 决策）：
- B.3.1 阶段 Chapter.content_summary 全仓唯一写入 = None（"只入章节骨架"）；
  LLM 抽取时 prompt 落 `（无）`（P0-1）。
- PDFExtractor._fallback_equal_split 凭空造 5 章等分；落库无 extraction_source
  标记（P0-3）；verify_end_to_end_5_chapters.py 门槛 `章节数 ≥ 3` 可被恒真满足。

本迁移目标：
1. 给 chapters 表加 extraction_source 列（String(32), NOT NULL, indexed）。
2. 用启发式回填 B.3 verify 创建的 5 章行：
   - title 形如 `^第\\d+章$`（纯阿拉伯数字）→ equal_split_placeholder
   - 其他 → detected
   （保守：宁可标 placeholder，不要错标 detected。）
3. 加 ix_chapters_extraction_source 索引。

不动 owner_user_id（D-29 B 项，工单 B 负责）。
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_chapter_extraction_source"
down_revision: str | None = "0003_lesson_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. 加列 nullable=True，回填后再 NOT NULL
    op.add_column(
        "chapters",
        sa.Column(
            "extraction_source",
            sa.String(length=32),
            nullable=True,
        ),
    )

    # 2. 启发式回填：
    #    - ^第\\d+章$   → equal_split_placeholder
    #    - 其他          → detected
    # PG 用 ~ 正则；SQLite 测试 in-memory 也支持 ~（SQLAlchemy 转译）
    op.execute(
        "UPDATE chapters SET extraction_source = 'equal_split_placeholder' "
        "WHERE extraction_source IS NULL AND title ~ '^第[0-9]+章$'"
    )
    op.execute(
        "UPDATE chapters SET extraction_source = 'detected' "
        "WHERE extraction_source IS NULL"
    )

    # 3. NOT NULL 收紧
    op.alter_column("chapters", "extraction_source", nullable=False)

    # 4. server_default 兜底（新建 chapter 时若未传值）
    op.execute(
        "ALTER TABLE chapters "
        "ALTER COLUMN extraction_source SET DEFAULT 'detected'"
    )

    # 5. 索引
    op.create_index(
        "ix_chapters_extraction_source",
        "chapters",
        ["extraction_source"],
    )


def downgrade() -> None:
    op.drop_index("ix_chapters_extraction_source", table_name="chapters")
    op.drop_column("chapters", "extraction_source")