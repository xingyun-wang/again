"""owner_user_id 归属字段 + users 表（M1-B retro 工单 B：D-29 B 项落地）。

Revision ID: 0005_owner_user_id
Revises: 0007_drop_extraction_source_default
Create Date: 2026-09-20

动机（D-29 B 项，docs/decisions.md）：
- §1.4「题库属于教师个人资产」未建模；6 个端点收下 ``_user_id`` 直接丢
  （B.2 临时简化；M1+ 才补完整 auth）
- 跨用户可见性：A 读 B → 必须 404（不是 403，避免 id 存在性泄漏）
- 落地策略：
    1. 建 users 表（id / name / is_system_owned / created_at / updated_at）
    2. Data migration：插 root seed user (id=1, name='system-seed',
       is_system_owned=True)；既有 Subject/Textbook/Chapter 的 owner_user_id
       全设 1（system-seed 代持，等用户系统接入 M3+ 后迁移到真 user_id）
    3. 三个表加 owner_user_id 列（nullable=True → 回填 → NOT NULL + FK to users.id）
    4. 三个 owner_user_id 索引

依赖：G2 (0007) 已 merge → down_revision=0007_drop_extraction_source_default。

不动：chapters.textbook_id FK 行为 / chapters.extraction_source 服务端 default
（G2 已处理）；其他表的字段；其他迁移的语义。

不引入：user 注册 / 登录 / JWT 鉴权端点（M3+ 范围；本工单只做 ownership 字段
+ 过滤）。
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_owner_user_id"
down_revision: str | None = "0007_drop_extraction_source_default"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# 系统种子用户 id：所有既有 Subject/Textbook/Chapter 的 owner 默认指向它。
# ON CONFLICT DO NOTHING：开发环境多次跑 migration 时不报错。
SYSTEM_SEED_USER_ID = 1
SYSTEM_SEED_USER_NAME = "system-seed"


def upgrade() -> None:
    # ─────────────────────────── 1. 建 users 表 ──────────────────────
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "name",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "is_system_owned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ─────────────────────────── 2. 插 root seed user ────────────────
    # id 显式写死 = 1；既有 Subject/Textbook/Chapter 回填都指向 1。
    # ON CONFLICT DO NOTHING：开发环境多次重跑不会因已存在报 unique violation。
    op.execute(
        sa.text(
            "INSERT INTO users (id, name, is_system_owned) "
            "VALUES (:id, :name, :iso) "
            "ON CONFLICT (id) DO NOTHING"
        ).bindparams(
            id=SYSTEM_SEED_USER_ID,
            name=SYSTEM_SEED_USER_NAME,
            iso=True,
        )
    )

    # ─────────────────────────── 3. subjects ─────────────────────────
    # 加列 nullable=True（先不 NOT NULL，避免影响现有行）
    op.add_column(
        "subjects",
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            nullable=True,
        ),
    )
    # 回填既有行 → system-seed
    op.execute(
        sa.text(
            "UPDATE subjects SET owner_user_id = :uid "
            "WHERE owner_user_id IS NULL"
        ).bindparams(uid=SYSTEM_SEED_USER_ID)
    )
    # NOT NULL 收紧
    op.alter_column("subjects", "owner_user_id", nullable=False)
    # FK 约束（RESTRICT：删 user 时若有关联 subjects，阻止删除）
    op.create_foreign_key(
        "fk_subjects_owner_user_id",
        "subjects",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    # 索引
    op.create_index(
        "ix_subjects_owner_user_id",
        "subjects",
        ["owner_user_id"],
    )

    # ─────────────────────────── 4. textbooks ────────────────────────
    op.add_column(
        "textbooks",
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.execute(
        sa.text(
            "UPDATE textbooks SET owner_user_id = :uid "
            "WHERE owner_user_id IS NULL"
        ).bindparams(uid=SYSTEM_SEED_USER_ID)
    )
    op.alter_column("textbooks", "owner_user_id", nullable=False)
    op.create_foreign_key(
        "fk_textbooks_owner_user_id",
        "textbooks",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_textbooks_owner_user_id",
        "textbooks",
        ["owner_user_id"],
    )

    # ─────────────────────────── 5. chapters ─────────────────────────
    op.add_column(
        "chapters",
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.execute(
        sa.text(
            "UPDATE chapters SET owner_user_id = :uid "
            "WHERE owner_user_id IS NULL"
        ).bindparams(uid=SYSTEM_SEED_USER_ID)
    )
    op.alter_column("chapters", "owner_user_id", nullable=False)
    op.create_foreign_key(
        "fk_chapters_owner_user_id",
        "chapters",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_chapters_owner_user_id",
        "chapters",
        ["owner_user_id"],
    )


def downgrade() -> None:
    # ─────────────────────────── 反向：拆 FK → 拆索引 → 拆列 → 拆 users ──
    # chapters
    op.drop_index("ix_chapters_owner_user_id", table_name="chapters")
    op.drop_constraint("fk_chapters_owner_user_id", "chapters", type_="foreignkey")
    op.drop_column("chapters", "owner_user_id")

    # textbooks
    op.drop_index("ix_textbooks_owner_user_id", table_name="textbooks")
    op.drop_constraint("fk_textbooks_owner_user_id", "textbooks", type_="foreignkey")
    op.drop_column("textbooks", "owner_user_id")

    # subjects
    op.drop_index("ix_subjects_owner_user_id", table_name="subjects")
    op.drop_constraint("fk_subjects_owner_user_id", "subjects", type_="foreignkey")
    op.drop_column("subjects", "owner_user_id")

    # users（不删 seed user 行；保留 id=1 以便回滚后再跑 upgrade 不报 duplicate）
    op.drop_table("users")