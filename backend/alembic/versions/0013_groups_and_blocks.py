"""alembic 迁移：题组模型（question_groups + content_blocks + 图片表改造）。

触发：M3-1a-2 brief（`3c0c13e`）+ 审阅件 5 条必改 + 补遗与定稿（2026-10-23）
基础：0012_questions_points_and_answer

本轮最大的一次迁移（星轨 08:31 §六）。严格只做 5 件事，不夹带：

🔴 **revision id 长度上限 = 32 字符**（PG ``alembic_version.version_num`` 是
``varchar(32)``，alembic 建表时写死的）。超长会在 **UPDATE alembic_version**
那一步报 ``StringDataRightTruncation``，且容器 entrypoint 每次启动都跑
``upgrade head`` ⇒ **后端进入崩溃重启循环**。

前车之鉴：本笔初版取名 ``0013_question_groups_and_content_blocks``（38 字符）
在 dev 库炸掉；上一笔 ``0012_questions_points_and_answer`` 恰好 32 卡满。
故本笔取 ``0013_groups_and_blocks``（22）。**下一个迁移编号前先数字符。**

好消息：PG 的 DDL 是事务性的，alembic 整笔包在一个事务里 ⇒ 版本号写失败时
**全部 DDL 一并回滚**，库不会停在半步状态（那次实测已验证：3 表未建、2 列未加、
``question_images`` 仍是 ``question_id|NO``）。恢复只需改名重跑，
**不需要手工 DROP / stamp**。

1. 新表 question_groups —— 材料 + 全部小题的容器
   - D2(a) 难度挂整组，小题继承
   - 明确不建 title / type / points / content 四列（理由见 brief §1）
2. 新表 group_knowledge_points —— 照抄 question_knowledge_points 结构
3. 新表 content_blocks —— 材料块序列（无 FK 的多态表，级联靠应用层）
4. questions 加 group_id + group_order（含 UNIQUE(group_id, group_order)）
5. question_images：question_id NOT NULL → NULL + 加 group_id + 防孤儿图 CHECK

定稿口径（补遗 2026-10-23，冲突以补遗为准）：
- 丙-1：owner_type / block_type 用 String(16)，**不用 PG native enum**
  （《材料结构方案》§二立论 = "以后加公式块/音频块不改表"；PG 加值要 ALTER TYPE，
  且 0002 的 CREATE TYPE 非幂等就是现成的坑）
  → 相应地**不加 CHECK (block_type IN (...))**：DB 允许脏值、应用层拒绝，
  这是有意的取舍。取值白名单放 Pydantic Literal + models 模块常量。
- 乙-3：content_blocks 加 meta 列（图片宽度 50/75/100 存这里）
  为什么现在加：brief 只把宽度推给 1c-2 的 UI、没给存储位 ⇒ 1c-2 必然再改
  content_blocks，违背块模型"加东西不改表"的初衷。
- 乙-2：content_blocks 无 FK ⇒ DELETE 题组必须显式删块（应用层保证）。
  text / table 块没有任何 FK 能带走它们，只有 image 块能被 image_id CASCADE 带走
  —— 不显式删就是"3 块删 1 块留 2 块"的假级联。
- 丙-3：questions 加 UNIQUE(group_id, group_order)。
  PG 唯一约束对 NULL 不做唯一判定（多行 group_id IS NULL 互不冲突），
  单题不受影响。同一题序可重复是 brief 原文的漏洞。
- 丙-4：downgrade 必须显式拒绝，不许抛栈。

回滚：
- downgrade() = 拆 5 件事（倒序）。但**存在材料图时必定失败** —— question_id
  加回 NOT NULL 时只要有 group_id 有值 / question_id IS NULL 的行就会炸。
  因此 downgrade 第一行显式拦截并给出中文原因（DoD 1「能完整回退」只在
  空库 / 无材料图下成立，写进判据，别让 DoD 撒谎）。

禁止：
- 改 0012 或更早任何迁移（派工单 §6-1）
- 手工 DROP TABLE / stamp 糊迁移失败（派工单 §6-4）
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013_groups_and_blocks"
down_revision: str | None = "0012_questions_points_and_answer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ── CHECK 约束名（downgrade 要按名 drop，名字必须与 upgrade 写死的一致）──
CK_IMAGE_OWNER = "ck_question_images_owner_not_null"
UQ_QUESTION_GROUP_ORDER = "uq_questions_group_order"


def _json_type() -> sa.types.TypeEngine:
    """JSON 变体：PG 走 JSONB，SQLite 走 JSON。

    直接写 JSONB 会让 SQLite 建表崩（本地红 / CI 绿）—— 块模型的 JSON 坑，
    brief §0.7。全仓 0 先例，本笔首次引入（判据 15 要专门验）。

    🔴 none_as_null=True（**必加**，2026-10-23 B 笔实测踩到）：
    SQLAlchemy 的 JSON 列默认 none_as_null=False ⇒ Python 的 None 被序列化成
    JSON 字面量 `null`，**不是 SQL NULL** ⇒ 本迁移建的 CHECK 判据
    `table_json IS NULL` / `image_id IS NULL` 之类的 IS NULL 判据对 JSON 列恒为
    false ⇒ text / table 块写入被误拒（建表能过、写入全炸）。
    加 none_as_null=True ⇒ None 落成真正的 SQL NULL，CHECK 判据成立。
    """
    return sa.JSON(none_as_null=True).with_variant(
        postgresql.JSONB(none_as_null=True), "postgresql"
    )


def upgrade() -> None:
    # ── 1. question_groups ────────────────────────────────────────────────
    # difficulty 复用 question_difficulty_enum（0007 已建，create_type=False
    # 不让 SQLAlchemy 再 CREATE TYPE —— 0011 的 DuplicateObject 教训）
    op.create_table(
        "question_groups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "chapter_id",
            sa.Integer(),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "difficulty",
            sa.Enum(
                "D",
                "C",
                "B",
                "A",
                name="question_difficulty_enum",
                create_type=False,
            ),
            nullable=False,
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
    op.create_index(
        "ix_question_groups_owner_user_id",
        "question_groups",
        ["owner_user_id"],
    )
    op.create_index(
        "ix_question_groups_chapter_id",
        "question_groups",
        ["chapter_id"],
    )

    # ── 2. group_knowledge_points（照抄 question_knowledge_points，brief §0.5）──
    op.create_table(
        "group_knowledge_points",
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("question_groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "knowledge_point_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # ── 4a. questions 加 group_id / group_order（先于 images，因为 images 的
    #        CHECK 要引用 group_id 语义，但物理上无依赖，先加 questions 更直观）──
    op.add_column(
        "questions",
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("question_groups.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_questions_group_id", "questions", ["group_id"])
    op.add_column(
        "questions",
        sa.Column("group_order", sa.Integer(), nullable=True),
    )
    # 丙-3：题序唯一。PG 对 NULL 不做唯一判定 ⇒ 单题（group_id IS NULL）不受影响
    op.create_unique_constraint(
        UQ_QUESTION_GROUP_ORDER,
        "questions",
        ["group_id", "group_order"],
    )

    # ── 5. question_images 改造 ─────────────────────────────────────────
    # question_id NOT NULL → NULL（D4(a)：材料图挂组，question_id 为 NULL）
    op.alter_column(
        "question_images",
        "question_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.add_column(
        "question_images",
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("question_groups.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_question_images_group_id", "question_images", ["group_id"])
    # D4(a) 要的是**互斥**：一张图要么挂小题、要么挂题组，不能都挂、不能都不挂。
    # (question_id IS NULL) <> (group_id IS NULL)
    # - 两者都 NULL = 孤儿图，渲染时无处可挂 ⇒ 拒绝
    # - 两者都有值 = 同一张图既算小题图又算材料图 ⇒ 渲染两次 + 删题连带删材料图
    #   ⇒ 拒绝
    # 旧写法 "(question_id IS NOT NULL OR group_id IS NOT NULL)" 只挡住前者，
    # 后者能进库 —— 星轨 2026-10-23 审阅 P2 提出，本笔改正。
    # （迁移只动约束、不改数据 —— 现有行都有 question_id、group_id 为 NULL，天然满足）
    op.create_check_constraint(
        CK_IMAGE_OWNER,
        "question_images",
        "(question_id IS NULL) <> (group_id IS NULL)",
    )

    # ── 3. content_blocks ────────────────────────────────────────────────
    # owner_type / block_type 用 String(16)（丙-1），不用 native enum
    op.create_table(
        "content_blocks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        # 多态裸列：MVP 只用 'group'，'question' 预留（题干将来也能图文混排，
        # 现在不做 UI，但表结构不用再改）
        sa.Column("owner_type", sa.String(length=16), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column(
            "order_index",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("block_type", sa.String(length=16), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=True),
        # image 块只引用不存文件（图本体在 question_images）
        sa.Column(
            "image_id",
            sa.Integer(),
            sa.ForeignKey("question_images.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("table_json", _json_type(), nullable=True),
        # 乙-3：图片宽度 50/75/100 + 预留 table 的 col_widths。
        # 本笔只保证列存在，不写业务校验、不做 CHECK（宽度取值属 1c-2 编辑器负责；
        # JSON 上的 CHECK 在 SQLite 侧难验）
        sa.Column("meta", _json_type(), nullable=True),
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
        # 块在 (owner, order_index) 上唯一 —— 题目这边同理不能没有（丙-3）
        sa.UniqueConstraint(
            "owner_type",
            "owner_id",
            "order_index",
            name="uq_content_blocks_owner_order",
        ),
        # 字段自洽 CHECK（按 block_type 验字段）。注意这**不是**取值白名单 ——
        # 取值白名单刻意不加（丙-1 换扩展性），只保证"text 块必须有正文"这类
        # 结构不变量。
        sa.CheckConstraint(
            "block_type != 'text' OR (text_content IS NOT NULL "
            "AND image_id IS NULL AND table_json IS NULL)",
            name="ck_content_blocks_text_shape",
        ),
        sa.CheckConstraint(
            "block_type != 'image' OR (image_id IS NOT NULL "
            "AND text_content IS NULL AND table_json IS NULL)",
            name="ck_content_blocks_image_shape",
        ),
        sa.CheckConstraint(
            "block_type != 'table' OR (table_json IS NOT NULL "
            "AND text_content IS NULL AND image_id IS NULL)",
            name="ck_content_blocks_table_shape",
        ),
    )
    op.create_index(
        "ix_content_blocks_owner",
        "content_blocks",
        ["owner_type", "owner_id"],
    )


def downgrade() -> None:
    # 丙-4：显式拒绝，不许抛栈。
    # question_id 加回 NOT NULL 时，只要存在材料图（question_id IS NULL）就必定失败
    # —— 让 migration 自己说清楚原因，别让人以为是迁移写坏。
    conn = op.get_bind()
    n = (
        conn.execute(
            sa.text(
                "SELECT count(*) FROM question_images WHERE question_id IS NULL"
            )
        ).scalar()
        or 0
    )
    if n:
        raise RuntimeError(
            f"存在 {n} 张材料图（question_id IS NULL），0013 不可回退；"
            "如需回退请先清理题组数据或整库重建"
        )

    # 倒序拆 5 件事
    op.drop_table("content_blocks")

    op.drop_constraint(CK_IMAGE_OWNER, "question_images", type_="check")
    op.drop_index("ix_question_images_group_id", table_name="question_images")
    op.drop_column("question_images", "group_id")
    op.alter_column(
        "question_images",
        "question_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.drop_constraint(
        UQ_QUESTION_GROUP_ORDER, "questions", type_="unique"
    )
    op.drop_index("ix_questions_group_id", table_name="questions")
    op.drop_column("questions", "group_order")
    op.drop_column("questions", "group_id")

    op.drop_table("group_knowledge_points")

    op.drop_index("ix_question_groups_chapter_id", table_name="question_groups")
    op.drop_index("ix_question_groups_owner_user_id", table_name="question_groups")
    op.drop_table("question_groups")