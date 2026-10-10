"""出题引擎 unit test（M2-A.1 · v0.5 §3.2 4 档 + §3.5 反马太"只从 C 抽"）。

判据真值（v0.5 line 168 verbatim）：
- 100 题 D 档作业：C 抽 ∈ [15, 25]（20% ± 5%），B 抽 = 0
- M2-A.1 落"只从 C 抽"= B 池不被反马太抽（ANTI_MATTHEW_B_PULL=0）
"""

from __future__ import annotations

import pytest

from app.services.question_generator import (
    ANTI_MATTHEW_B_PULL,
    ANTI_MATTHEW_C_RATIO,
    ANTI_MATTHEW_C_RATIO_TOLERANCE,
    compute_distribution,
    select_questions,
    validate_pool,
)


class _FakeQuestion:
    """测试用伪 Question（避免 SQLAlchemy session 依赖）。"""

    def __init__(self, id: int, difficulty: str) -> None:
        self.id = id
        self.difficulty = difficulty


class TestAntiMatthewConstants:
    """反马太常量 verbatim 锚定 v0.5 line 168。"""

    def test_constants(self) -> None:
        assert ANTI_MATTHEW_B_PULL == 0, "B 池永不被反马太抽（v0.5 line 168）"
        assert ANTI_MATTHEW_C_RATIO == 0.20, "C 池反马太 20% 拔高"
        assert ANTI_MATTHEW_C_RATIO_TOLERANCE == 0.05, "±5% 浮动"


class TestComputeDistribution:
    """compute_distribution 单测（纯函数）。"""

    def test_D_100_questions(self) -> None:
        """D 档 100 题：D 80 + C 20 + B 0 + A 0（v0.5 §3.5 反马太只从 C 抽）。"""
        d = compute_distribution("D", 100)
        assert d.D == 80
        assert d.C == 20
        assert d.B == 0
        assert d.A == 0
        assert d.total == 100

    def test_D_50_questions(self) -> None:
        """D 档 50 题：D 40 + C 10（20% 拔高）。"""
        d = compute_distribution("D", 50)
        assert d.D == 40
        assert d.C == 10
        assert d.B == 0
        assert d.A == 0
        assert d.total == 50

    def test_D_25_questions(self) -> None:
        """D 档 25 题：D 20 + C 5（20% 拔高）。"""
        d = compute_distribution("D", 25)
        assert d.D == 20
        assert d.C == 5
        assert d.B == 0
        assert d.A == 0
        assert d.total == 25

    def test_C_100_percent_C_pool(self) -> None:
        """C 档作业：100% C 池。"""
        d = compute_distribution("C", 50)
        assert d == (0, 50, 0, 0) or (
            d.D == 0 and d.C == 50 and d.B == 0 and d.A == 0
        )

    def test_B_100_percent_B_pool(self) -> None:
        d = compute_distribution("B", 30)
        assert d.D == 0 and d.C == 0 and d.B == 30 and d.A == 0

    def test_A_100_percent_A_pool(self) -> None:
        d = compute_distribution("A", 25)
        assert d.D == 0 and d.C == 0 and d.B == 0 and d.A == 25

    def test_invalid_tier_raises(self) -> None:
        with pytest.raises(ValueError, match="tier 必须是"):
            compute_distribution("X", 100)

    def test_zero_count_raises(self) -> None:
        with pytest.raises(ValueError, match="total_count 必须 > 0"):
            compute_distribution("D", 0)

    def test_negative_count_raises(self) -> None:
        with pytest.raises(ValueError, match="total_count 必须 > 0"):
            compute_distribution("D", -1)


class TestValidatePool:
    """validate_pool 单测。"""

    def _pool(self, d: int = 100, c: int = 100, b: int = 100, a: int = 100):
        return {
            "D": [_FakeQuestion(i, "D") for i in range(d)],
            "C": [_FakeQuestion(i, "C") for i in range(c)],
            "B": [_FakeQuestion(i, "B") for i in range(b)],
            "A": [_FakeQuestion(i, "A") for i in range(a)],
        }

    def test_sufficient_pool_passes(self) -> None:
        d = compute_distribution("D", 100)
        validate_pool(d, self._pool())  # 不 raise

    def test_insufficient_C_pool_raises(self) -> None:
        d = compute_distribution("D", 100)
        with pytest.raises(ValueError, match=r"C 池"):
            validate_pool(d, self._pool(c=10))

    def test_insufficient_D_pool_raises(self) -> None:
        d = compute_distribution("D", 100)
        with pytest.raises(ValueError, match=r"D 池"):
            validate_pool(d, self._pool(d=50))


class TestSelectQuestions:
    """select_questions 单测 + 100 题 D 档作业反马太判据（v0.5 line 168 verbatim）。"""

    def _pool(self, d: int = 100, c: int = 100, b: int = 100, a: int = 100):
        return {
            "D": [_FakeQuestion(i, "D") for i in range(d)],
            "C": [_FakeQuestion(i, "C") for i in range(c)],
            "B": [_FakeQuestion(i, "B") for i in range(b)],
            "A": [_FakeQuestion(i, "A") for i in range(a)],
        }

    def test_100_question_D_assignment_anti_matthew_judgment(self) -> None:
        """v0.5 line 168 verbatim：100 题 D 档作业 C 抽 ∈ [15, 25], B 抽 = 0。

        compute_distribution 给出 fixed C=20；20 ∈ [15, 25] ✓。
        多次随机抽样（不同 seed）= C 抽恒 20，B 抽恒 0。
        """
        d = compute_distribution("D", 100)
        # distribution 真值
        assert 15 <= d.C <= 25, f"C 抽 {d.C} 不在 [15, 25] 区间"
        assert d.B == 0, f"B 抽 {d.B} 不为 0"

        pool = self._pool()
        for seed in range(20):
            selected = select_questions("D", pool, 100, seed=seed)
            c_picked = sum(1 for q in selected if q.difficulty == "C")
            b_picked = sum(1 for q in selected if q.difficulty == "B")
            d_picked = sum(1 for q in selected if q.difficulty == "D")
            a_picked = sum(1 for q in selected if q.difficulty == "A")
            assert c_picked == 20, f"seed={seed}: C 抽 {c_picked} ≠ 20"
            assert b_picked == 0, f"seed={seed}: B 抽 {b_picked} ≠ 0"
            assert a_picked == 0, f"seed={seed}: A 抽 {a_picked} ≠ 0"
            assert d_picked == 80, f"seed={seed}: D 抽 {d_picked} ≠ 80"
            assert len(selected) == 100

    def test_50_question_D_assignment(self) -> None:
        """50 题 D 档作业：C 抽 10（20% × 50），B 抽 0。"""
        pool = self._pool()
        selected = select_questions("D", pool, 50, seed=42)
        c_picked = sum(1 for q in selected if q.difficulty == "C")
        assert c_picked == 10
        assert all(q.difficulty != "B" for q in selected)
        assert all(q.difficulty != "A" for q in selected)

    def test_reproducible_with_same_seed(self) -> None:
        """同 seed 必同结果（可复现）。"""
        pool = self._pool()
        s1 = select_questions("D", pool, 100, seed=123)
        s2 = select_questions("D", pool, 100, seed=123)
        assert [q.id for q in s1] == [q.id for q in s2]

    def test_C_tier_100_percent_C(self) -> None:
        pool = self._pool()
        selected = select_questions("C", pool, 50, seed=1)
        assert all(q.difficulty == "C" for q in selected)
        assert len(selected) == 50

    def test_B_tier_100_percent_B(self) -> None:
        pool = self._pool()
        selected = select_questions("B", pool, 30, seed=1)
        assert all(q.difficulty == "B" for q in selected)

    def test_A_tier_100_percent_A(self) -> None:
        pool = self._pool()
        selected = select_questions("A", pool, 25, seed=1)
        assert all(q.difficulty == "A" for q in selected)

    def test_insufficient_pool_raises(self) -> None:
        compute_distribution("D", 100)
        with pytest.raises(ValueError):
            select_questions("D", self._pool(d=10), 100, seed=1)
