"""出题引擎（M2-A.1 · v0.5 §3.2 4 档 + §3.5 反马太"只从 C 抽"）。

设计：
- 纯函数为主（`compute_distribution` / `validate_pool`），不依赖 SQLAlchemy / FastAPI，
  便于独立单测 + 多次随机抽样验证。
- 唯一 DB 交互是 `generate_assignment_for_chapter`：从 DB 读 chapter 下题库 +
  调 `select_questions` + 写 Assignment + AssignmentItem 落库。
- 随机性显式注入 `seed`（`random.Random(seed)`）；同 seed 必同结果（可复现）。

判据真值（v0.5 §3.5 line 168 verbatim）：
- 100 题 D 档作业：C 抽 ∈ [15, 25]（20% ± 5%），B 抽 = 0
- v0.6 候选修正（M2-A.1 落地）= "只从 C 抽"（B 池不被反马太抽）
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import Assignment, Chapter, Question, User

TierLiteral = Literal["D", "C", "B", "A"]
ALL_TIERS: tuple[TierLiteral, ...] = ("D", "C", "B", "A")

# v0.5 §3.5 反马太判据（verbatim）：
#   "100 题作业中 C 抽 ∈ [15, 25]（20% ± 5%），B 抽 = 0"
# M2-A.1 落"只从 C 抽"= B 池不被反马太抽。
ANTI_MATTHEW_B_PULL = 0  # 永远 = 0
ANTI_MATTHEW_C_RATIO = 0.20  # 20% 拔高
ANTI_MATTHEW_C_RATIO_TOLERANCE = 0.05  # ±5%


@dataclass(frozen=True)
class Distribution:
    """4 档池各抽几题的反马太分布。

    sum = total_count。4 档 = D/C/B/A。
    """

    D: int
    C: int
    B: int
    A: int

    @property
    def total(self) -> int:
        return self.D + self.C + self.B + self.A

    def as_dict(self) -> dict[TierLiteral, int]:
        return {"D": self.D, "C": self.C, "B": self.B, "A": self.A}


def compute_distribution(tier: TierLiteral, total_count: int) -> Distribution:
    """根据目标档位 + 总题数,计算 4 档池各抽几题。

    规则（v0.5 §3.5 + M2-A.1 "只从 C 抽"）：
    - D 档作业：80% D 池 + 20% C 池（反马太拔高）;B/A 池 = 0
    - C/B/A 档作业：100% 来自自身档位池

    Args:
        tier: 目标档位 D/C/B/A
        total_count: 作业总题数（> 0）

    Returns:
        Distribution（D/C/B/A 各抽几题;sum = total_count）

    Raises:
        ValueError: tier 非法 或 total_count <= 0
    """
    if tier not in ALL_TIERS:
        raise ValueError(
            f"tier 必须是 {ALL_TIERS!r} 之一,实际 {tier!r}"
        )
    if total_count <= 0:
        raise ValueError(f"total_count 必须 > 0,实际 {total_count}")

    if tier == "D":
        # A3 fix: 反马太比例从 ANTI_MATTHEW_C_RATIO 消费（主变量 = C）。
        # 旧实现 D 数 = round(0.80 * n), C 数 = 余数（以 D 为舍入主体）。
        # 新实现 C 数 = round(ANTI_MATTHEW_C_RATIO * n), D 数 = 余数（以 C 为舍入主体）。
        # 舍入归属会变：n=100→c=20 / 50→10 / 25→5 与旧值一致；奇数 n 可能差 1（可接受）。
        c_count = round(ANTI_MATTHEW_C_RATIO * total_count)
        d_count = total_count - c_count  # D 取补集，保证 sum = total_count
        return Distribution(D=d_count, C=c_count, B=0, A=0)
    # C / B / A: 100% 来自自身档位
    return Distribution(D=0, C=total_count if tier == "C" else 0,
                        B=total_count if tier == "B" else 0,
                        A=total_count if tier == "A" else 0)


def validate_pool(
    distribution: Distribution,
    pool_by_difficulty: Mapping[TierLiteral, Sequence[object]],
) -> None:
    """校验每个档位池是否够抽（>= 需求数）。

    Args:
        distribution: 4 档抽题数
        pool_by_difficulty: 各档池题目列表(可空,但不足会 raise)

    Raises:
        ValueError: 任一档位池题目数 < 需求数
    """
    missing: list[str] = []
    for tier in ALL_TIERS:
        need = distribution.as_dict()[tier]
        if need == 0:
            continue
        have = len(pool_by_difficulty.get(tier, []))
        if have < need:
            missing.append(f"{tier} 池 {have}<{need}")
    if missing:
        raise ValueError(
            f"题库容量不足,缺: {', '.join(missing)};"
            f"v0.5 §3.5 限制 MVP 阶段 C 题池建设必须前置"
        )


def select_questions(
    tier: TierLiteral,
    pool_by_difficulty: dict[TierLiteral, Sequence[Question]],
    total_count: int,
    seed: int | None = None,
) -> list[Question]:
    """按档位 + 反马太规则抽题。

    Args:
        tier: 目标档位 D/C/B/A
        pool_by_difficulty: 各档池题目列表
        total_count: 作业总题数
        seed: 随机种子(None = 用系统时间);同 seed 必同结果

    Returns:
        选中的题目列表(按 D 池先 / C 池后 ... 的顺序;具体题 random.sample 决定)

    Raises:
        ValueError: tier 非法、total_count <= 0、池子不足
    """
    distribution = compute_distribution(tier, total_count)
    validate_pool(distribution, pool_by_difficulty)

    rng = random.Random(seed)
    selected: list[Question] = []
    # 抽题顺序 D → C → B → A(稳定顺序;position 字段后续按本序落库)
    for pool_tier in ALL_TIERS:
        need = distribution.as_dict()[pool_tier]
        if need == 0:
            continue
        pool = list(pool_by_difficulty.get(pool_tier, []))
        # random.sample 无放回抽样;同 seed → 同结果
        picked = rng.sample(pool, need)
        selected.extend(picked)
    return selected


# ──────────────────────────── DB 落库 ────────────────────────────


def generate_assignment_for_chapter(
    db: Session,
    *,
    owner: User,
    chapter: Chapter,
    tier: TierLiteral,
    total_count: int,
    seed: int | None = None,
) -> Assignment:
    """为指定 chapter 出题并落库 Assignment + AssignmentItem。

    流程:
    1. 查 chapter 下所有 questions(按 owner_user_id 过滤,防跨用户泄漏)
    2. 按 difficulty 分桶
    3. compute_distribution + select_questions
    4. 创 Assignment + 顺序创 AssignmentItem(position = 在选中列表的索引)
    5. commit + refresh

    Args:
        db: SQLAlchemy Session
        owner: 当前用户(归属元数据)
        chapter: 目标章节
        tier: 目标档位 D/C/B/A
        total_count: 作业总题数
        seed: 可选随机种子(可复现)

    Returns:
        落库后的 Assignment(含 items 关系)

    Raises:
        ValueError: tier 非法、total_count <= 0、池子不足
    """
    # 延迟 import:本模块测试可在无 SQLAlchemy 环境跑
    from app.models import Assignment, AssignmentItem, Question

    # 1. 查题库(按 owner + chapter 过滤)
    questions: list[Question] = (
        db.query(Question)
        .filter(Question.owner_user_id == owner.id, Question.chapter_id == chapter.id)
        .all()
    )

    # 2. 按 difficulty 分桶
    pool_by_difficulty: dict[TierLiteral, list[Question]] = {
        "D": [], "C": [], "B": [], "A": []
    }
    for q in questions:
        diff = q.difficulty.value if hasattr(q.difficulty, "value") else str(q.difficulty)
        if diff in pool_by_difficulty:
            pool_by_difficulty[diff].append(q)  # type: ignore[index]

    # 3. 抽题
    selected = select_questions(
        tier=tier,
        pool_by_difficulty=pool_by_difficulty,  # type: ignore[arg-type]
        total_count=total_count,
        seed=seed,
    )

    # 4. 创 Assignment
    distribution = compute_distribution(tier, total_count)
    assignment = Assignment(
        owner_user_id=owner.id,
        chapter_id=chapter.id,
        tier=tier,
        total_count=total_count,
        d_count=distribution.D,
        c_count=distribution.C,
        b_count=distribution.B,
        a_count=distribution.A,
        seed=seed,
    )
    db.add(assignment)
    db.flush()  # 拿 assignment.id

    # 5. 顺序创 AssignmentItem
    for position, q in enumerate(selected):
        item = AssignmentItem(
            assignment_id=assignment.id,
            question_id=q.id,
            position=position,
            tier_origin=q.difficulty,  # ORM enum 直接传
        )
        db.add(item)

    db.commit()
    db.refresh(assignment)
    return assignment


def pool_to_dict(
    questions: Iterable[Question],
) -> dict[TierLiteral, list[Question]]:
    """把扁平的题库列表按 difficulty 分桶(测试 fixture 加载用)。"""
    pool: dict[TierLiteral, list[Question]] = {"D": [], "C": [], "B": [], "A": []}
    for q in questions:
        diff = q.difficulty.value if hasattr(q.difficulty, "value") else str(q.difficulty)
        if diff in pool:
            pool[diff].append(q)  # type: ignore[index]
    return pool
