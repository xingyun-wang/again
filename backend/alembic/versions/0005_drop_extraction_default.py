"""chapters.extraction_source 拆 server_default（M1-B retro G2：fail-open → fail-closed）。

Revision ID: 0005_drop_extraction_default
Revises: 0004_chapter_extraction_source
Create Date: 2026-09-20
M1-B retro Step 1（2026-09-21）：本迁移原 revision ID 占位为高位四位数
（数值等于 G2 序号）以避开 alembic_version.version_num 列 VARCHAR(32) 上限
（高位全名 33 字符超限），并为后续 owner_user_id 迁移让出 0005 号位。
当前 revision ID 即本文件 basename：0005_drop_extraction_default。

动机（D-37 决策 — G2）：
- 0004 加 server_default='detected' 让历史 fixture 不缺字段落库
- 但被利用为 fail-open：stub extractor 走 server_default 兜底所有写入
  （不显式传 extraction_source，ORM INSERT 走 server_default 落 'detected'）
- verify_end_to_end_5_chapters.py 「全部 extraction_source == 'detected'」
  门槛仍被满足 → fail-open 实现伪装为「端到端成功」
- 这是 D-32 第 4 类 P0「门槛 fail-open」

G2 反向（D-37 决策室账本）：
1. 拆 chapters.extraction_source server_default（**仅本迁移做**）
2. service 显式传 extraction_source 路径不变（textbook_upload.py
   `for cs, summary, src in zip(...): ch = Chapter(..., extraction_source=src)`）
3. service 加 None 兜底：如果 src 走到 ORM Python default，raise TextbookUploadError
4. verify 加段 B 门槛（至少 1 个非 'detected' 路径，堵 fail-open）

本迁移只动 server_default：不变 nullable / 长度 / 索引 / 列本身。
**新行 INSERT 必须显式 set extraction_source；不允许走 server_default 兜底**。
如不显式 → NOT NULL violation（postgres 拒绝写入）。

不回填旧数据：旧章已写入的 extraction_source 不动（D-37 G2 只对增量写入收紧）。
"""

from __future__ import annotations

from typing import Sequence

from alembic import op

revision: str = "0005_drop_extraction_default"
down_revision: str | None = "0004_chapter_extraction_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # D-37 G2：拆 server_default 'detected'，让 fail-open 实现暴露。
    # service 必须显式传 extraction_source；如走 server_default 兜底，新行
    # INSERT 在 PG 会 NOT NULL violation（旧 fixture / 历史 row 不受影响）。
    op.execute(
        "ALTER TABLE chapters ALTER COLUMN extraction_source DROP DEFAULT"
    )


def downgrade() -> None:
    # 恢复 server_default='detected'（与 0004 对称；仅用于回滚兼容）
    op.execute(
        "ALTER TABLE chapters "
        "ALTER COLUMN extraction_source SET DEFAULT 'detected'"
    )