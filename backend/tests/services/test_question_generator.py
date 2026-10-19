"""出题引擎 unit test（M2-A.1 · v0.5 §3.2 4 档 + §3.5 反马太"只从 C 抽" + M3-B2 §1 W1 ORDER BY 回归）。

判据真值（v0.5 line 168 verbatim）：
- 100 题 D 档作业：C 抽 ∈ [15, 25]（20% ± 5%），B 抽 = 0
- M2-A.1 落"只从 C 抽"= B 池不被反马太抽（ANTI_MATTHEW_B_PULL=0）

M3-B2 W1 ORDER BY（M3 派工 brief B2 2026-10-19 commit 03eb6ac）：
- `question_generator.py:199-204` 加 `.order_by(Question.id.asc())`（W1 抽题可复现）
- 回归覆盖：ORDER BY 列名 / 同 seed 顺序一致 / 难度分布不变 / diff 列表 = 空
"""

from __future__ import annotations

import sys

import pytest

from app.services.question_generator import (
    ANTI_MATTHEW_B_PULL,
    ANTI_MATTHEW_C_RATIO,
    ANTI_MATTHEW_C_RATIO_TOLERANCE,
    compute_distribution,
    select_questions,
    validate_pool,
)

# ────── conftest mock_db_engine create_all 前预注册 models (B2 W1 ORDER BY) ──────
#
# 问题（M3-B2 brief 中发现 / 验证）：
# - backend/tests/conftest.py mock_db_engine() 先调 Base.metadata.create_all(eng)
#   再 yield —— 此时 Base.metadata 还是空（没 import model = model 未注册）
#   ⇒ create_all 创建 0 张表
# - 紧跟的 mock_user_system_seed 调 mock_db_session.get(User, 1) ⇒
#   "relation 'users' does not exist"（M3-B2 实证：4 个新 case 第 1 个 ERROR；
#   test_question_crud.py 19 passed + 1 ERROR 同根因）
# - 现象：任何测试文件**第一个**走 DB fixture 的 test 必 ERR；第 2 个起 OK
#   （第 1 个 test 失败时 model 才被 import 进 Base.metadata，后续 create_all 才真建表）
#
# 修法（本文件 workaround / 保持 2 文件 diff = 不改 conftest）：
# - 模块级 import 触发 model 注册到 Base.metadata
# - 在 pytest collection 阶段发生（早于任何 fixture）
# - mock_db_engine 的 create_all 看到非空 metadata ⇒ 真建表
# - py3.8 try/except：Mapped[list[Class]] PEP 585 不可用，但纯函数 case 不依赖 model，
#   且 TestGenerateAssignmentOrderBy 已 skipif py3.8
try:
    from app.models import (  # noqa: F401  # populate Base.metadata
        Chapter,
        Question,
        QuestionDifficulty,
        QuestionType,
        Subject,
        Textbook,
        User,
    )
    _DB_MODELS_AVAILABLE = True
except Exception:  # py3.8 / import 失败
    _DB_MODELS_AVAILABLE = False


class _FakeQuestion:
    """测试用伪 Question（避免 SQLAlchemy session 依赖）。"""

    def __init__(self, id: int, difficulty: str) -> None:
        self.id = id
        self.difficulty = difficulty


class TestAntiMatthewConstants:
    """反马太常量 verbatim 锚定 v0.5 line 168 + 消费验证。"""

    def test_constants_exist(self) -> None:
        """常量存在性 + 字面量值（v0.5 line 168 锚定）。"""
        assert ANTI_MATTHEW_B_PULL == 0, "B 池永不被反马太抽（v0.5 line 168）"
        assert ANTI_MATTHEW_C_RATIO == 0.20, "C 池反马太 20% 拔高"
        assert ANTI_MATTHEW_C_RATIO_TOLERANCE == 0.05, "±5% 浮动"

    def test_anti_matthew_ratio_consumed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A3 pre-fix red: monkeypatch ANTI_MATTHEW_C_RATIO → c_count 随之变（证生产代码真消费）。

        Pre-fix: compute_distribution 硬编码 0.80 ⇒ c_count 总是 = total - round(0.80 * total)
        Post-fix: c_count = round(ANTI_MATTHEW_C_RATIO * total) ⇒ monkeypatch 0.30 → c=30。
        """
        monkeypatch.setattr(
            "app.services.question_generator.ANTI_MATTHEW_C_RATIO", 0.30
        )
        d = compute_distribution("D", 100)
        assert d.C == 30, f"Expected 30 (0.30 * 100), got {d.C} (constant not consumed)"

    def test_anti_matthew_b_pull_consumed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A3 配套: monkeypatch ANTI_MATTHEW_B_PULL → B 仍 = 0（设计内 = B 池永不被反马太抽）。"""
        monkeypatch.setattr(
            "app.services.question_generator.ANTI_MATTHEW_B_PULL", 99
        )
        d = compute_distribution("D", 100)
        assert d.B == 0, f"B 池永不被反马太抽, got {d.B}"


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


# ──────────────────── W1 ORDER BY 回归测试（M3-B2 brief §1）────────────────────
#
# 4 case（每 case 必报项）：
#  1. test_order_by_question_id_asc_in_sql — SQL 包含 ORDER BY questions.id ASC
#     （brief §4 #2 "ORDER BY 列 + 升降"；4 法核源 #1 + #2）
#  2. test_same_seed_yields_same_question_id_sequence — 同 seed 跑 2 次 → item
#     顺序完全一致（brief §4 #3 "基线对比：同 seed 跑 2 次 = 顺序一致"）
#  3. test_difficulty_distribution_unchanged_after_order_by — 100 题 D 档作业
#     → d_count=80, c_count=20, b_count=0, a_count=0（brief §4 #3 "diff 难度不变"）
#  4. test_reproducible_100_questions_diff_list_is_empty — 同 seed 2 次
#     → diff 列表 = []（brief §5 "同 seed 跑 2 次顺序一致证据"）
#
# py3.8 跳过：DB 路径走 app.models（含 Mapped[list[Class]] PEP 585）。
# 纯函数 case（TestAntiMatthewConstants / TestComputeDistribution / TestValidatePool /
# TestSelectQuestions）= 用 _FakeQuestion 避开 SQLAlchemy，py3.8 可跑。
_skip_on_py38_orderby = pytest.mark.skipif(
    sys.version_info < (3, 9) or not _DB_MODELS_AVAILABLE,
    reason="W1 ORDER BY DB tests require py3.9+ (Mapped[list[Class]] PEP 585) + model imports OK",
)


@_skip_on_py38_orderby
class TestGenerateAssignmentOrderBy:
    """W1 抽题可复现 回归测试（M3-B2 brief §1 / §4 必报项）。

    覆盖：
    - ORDER BY 列 = Question.id ASC（不是 created_at / difficulty）
    - 同 seed 跑 2 次 → AssignmentItem.question_id 序列完全一致（diff 列表 = 空）
    - 难度分布不变（ORDER BY 不影响 d/c/b/a count）
    - 跨池桶序稳定（SQL 按 id ASC 排 → 桶内序稳定）
    """

    def test_order_by_question_id_asc_in_sql(
        self,
        mock_db_engine,  # type: ignore[no-untyped-def]
        mock_db_session,  # type: ignore[no-untyped-def]
        mock_chapter,  # type: ignore[no-untyped-def]
        mock_user_system_seed,  # type: ignore[no-untyped-def]
    ) -> None:
        """W1 抽题可复现 §1: SQL 包含 ORDER BY questions.id ASC。

        通过 SQLAlchemy ``before_cursor_execute`` event 捕获 SELECT，
        验证包含 ``ORDER BY questions.id``。**不写"我以为"**（D-43-X）：
        用物理捕获的 SQL 字面量做断言。

        排除 ORDER BY = created_at / difficulty：
        - B2 brief §2 拍板用 id；非 id 即 FAIL。
        """
        import re

        from sqlalchemy import event

        from app.models import Question, QuestionDifficulty, QuestionType
        from app.services.question_generator import generate_assignment_for_chapter

        # 准备 3 道 D 档题（足够触发 D 池 ≥ need）
        for i in range(3):
            q = Question(
                owner_user_id=mock_user_system_seed.id,
                chapter_id=mock_chapter.id,
                content=f"q{i + 1}",
                difficulty=QuestionDifficulty.D,
                type=QuestionType.CHOICE,
            )
            mock_db_session.add(q)
        mock_db_session.commit()

        # 捕获 SQL
        captured: list[str] = []

        def _capture(conn, cursor, statement, params, context, executemany):  # noqa: ANN001
            captured.append(statement)

        event.listen(mock_db_engine, "before_cursor_execute", _capture)
        try:
            generate_assignment_for_chapter(
                mock_db_session,
                owner=mock_user_system_seed,
                chapter=mock_chapter,
                tier="D",
                total_count=2,
                seed=42,
            )
        finally:
            event.remove(mock_db_engine, "before_cursor_execute", _capture)

        # 找出针对 questions 表的 SELECT
        question_selects = [
            s
            for s in captured
            if re.search(r"\bFROM\s+questions\b", s, re.IGNORECASE)
            and s.strip().upper().startswith("SELECT")
        ]
        assert question_selects, (
            f"未捕获到 SELECT FROM questions; 所有 SQL = {captured}"
        )

        # 核心断言：ORDER BY questions.id（PG / SQLite 都会渲染成 questions.id）
        has_id_orderby = any(
            re.search(r"ORDER BY\s+questions\.id", s, re.IGNORECASE)
            for s in question_selects
        )
        assert has_id_orderby, (
            f"期望 ORDER BY questions.id，实际 = {question_selects}"
        )

        # 反向断言：不应 ORDER BY 其他列（created_at / difficulty）
        for s in question_selects:
            assert not re.search(
                r"ORDER BY\s+questions\.created_at", s, re.IGNORECASE
            ), f"不应 ORDER BY created_at（B2 brief §2 排除）; 实际 = {s}"
            assert not re.search(
                r"ORDER BY\s+questions\.difficulty", s, re.IGNORECASE
            ), f"不应 ORDER BY difficulty（B2 brief §2 排除）; 实际 = {s}"

    def test_same_seed_yields_same_question_id_sequence(
        self,
        mock_db_session,  # type: ignore[no-untyped-def]
        mock_chapter,  # type: ignore[no-untyped-def]
        mock_user_system_seed,  # type: ignore[no-untyped-def]
    ) -> None:
        """W1 抽题可复现 §1: 同 seed 跑 2 次 → AssignmentItem.question_id 序列完全一致。

        5 题混合 D/C/D/C/D（足够触发 D/C 池都抽）+ tier=D total=3：
        D_count = round(0.20*3) = 1; C_count = 2。两次跑同 seed → 序列必一致。
        """
        from app.models import Question, QuestionDifficulty, QuestionType
        from app.services.question_generator import generate_assignment_for_chapter

        difficulties = [
            QuestionDifficulty.D,
            QuestionDifficulty.C,
            QuestionDifficulty.D,
            QuestionDifficulty.C,
            QuestionDifficulty.D,
        ]
        for i, diff in enumerate(difficulties):
            q = Question(
                owner_user_id=mock_user_system_seed.id,
                chapter_id=mock_chapter.id,
                content=f"q{i + 1}",
                difficulty=diff,
                type=QuestionType.CHOICE,
            )
            mock_db_session.add(q)
        mock_db_session.commit()

        a1 = generate_assignment_for_chapter(
            mock_db_session,
            owner=mock_user_system_seed,
            chapter=mock_chapter,
            tier="D",
            total_count=3,
            seed=42,
        )
        a2 = generate_assignment_for_chapter(
            mock_db_session,
            owner=mock_user_system_seed,
            chapter=mock_chapter,
            tier="D",
            total_count=3,
            seed=42,
        )

        ids1 = [item.question_id for item in a1.items]
        ids2 = [item.question_id for item in a2.items]
        assert ids1 == ids2, (
            f"同 seed 跑 2 次结果不一致: a1={ids1}, a2={ids2}, "
            f"diffs={list(zip(ids1, ids2, strict=False))}"
        )

    def test_difficulty_distribution_unchanged_after_order_by(
        self,
        mock_db_session,  # type: ignore[no-untyped-def]
        mock_chapter,  # type: ignore[no-untyped-def]
        mock_user_system_seed,  # type: ignore[no-untyped-def]
    ) -> None:
        """ORDER BY 不影响 d/c/b/a count 分布（v0.5 §3.5 反马太判据不变）。

        100 D + 100 C 题池 + tier=D total=100：
        d_count=80, c_count=20, b_count=0, a_count=0。
        items 中 D 池抽题 = 80, C 池抽题 = 20, 无 B / A。
        """
        from app.models import Question, QuestionDifficulty, QuestionType
        from app.services.question_generator import generate_assignment_for_chapter

        # 100 D + 100 C（足够覆盖反马太判据 + 验证 pool 顺序不影响分布）
        for i in range(100):
            mock_db_session.add(
                Question(
                    owner_user_id=mock_user_system_seed.id,
                    chapter_id=mock_chapter.id,
                    content=f"d{i}",
                    difficulty=QuestionDifficulty.D,
                    type=QuestionType.CHOICE,
                )
            )
        for i in range(100):
            mock_db_session.add(
                Question(
                    owner_user_id=mock_user_system_seed.id,
                    chapter_id=mock_chapter.id,
                    content=f"c{i}",
                    difficulty=QuestionDifficulty.C,
                    type=QuestionType.CHOICE,
                )
            )
        mock_db_session.commit()

        a = generate_assignment_for_chapter(
            mock_db_session,
            owner=mock_user_system_seed,
            chapter=mock_chapter,
            tier="D",
            total_count=100,
            seed=42,
        )

        # 反马太判据（v0.5 §3.5 line 168 verbatim）
        assert a.d_count == 80
        assert a.c_count == 20
        assert a.b_count == 0
        assert a.a_count == 0
        assert len(a.items) == 100

        # 实际 items 难度分布也匹配
        d_picked = sum(
            1 for item in a.items if item.tier_origin == QuestionDifficulty.D
        )
        c_picked = sum(
            1 for item in a.items if item.tier_origin == QuestionDifficulty.C
        )
        assert d_picked == 80, f"D 抽 {d_picked} ≠ 80（v0.5 §3.5 反马太）"
        assert c_picked == 20, f"C 抽 {c_picked} ≠ 20（v0.5 §3.5 反马太）"
        # 0 B / 0 A
        assert not any(
            item.tier_origin == QuestionDifficulty.B for item in a.items
        ), "B 池永不被反马太抽（v0.5 §3.5）"
        assert not any(
            item.tier_origin == QuestionDifficulty.A for item in a.items
        ), "A 池永不被反马太抽（v0.5 §3.5）"

    def test_reproducible_100_questions_diff_list_is_empty(
        self,
        mock_db_session,  # type: ignore[no-untyped-def]
        mock_chapter,  # type: ignore[no-untyped-def]
        mock_user_system_seed,  # type: ignore[no-untyped-def]
    ) -> None:
        """B2 brief §4 #3 / §5 必报项: 同 seed 跑 2 次顺序一致证据 = diff 列表 = []。

        100 D + 100 C 题池 + tier=D total=100 + seed=42。
        跑 2 次: diff (position 维度) = 空 list = 同 seed = 同结果 = W1 抽题可复现。
        """
        from app.models import Question, QuestionDifficulty, QuestionType
        from app.services.question_generator import generate_assignment_for_chapter

        # 100 D + 100 C 题池
        for i in range(100):
            mock_db_session.add(
                Question(
                    owner_user_id=mock_user_system_seed.id,
                    chapter_id=mock_chapter.id,
                    content=f"d{i}",
                    difficulty=QuestionDifficulty.D,
                    type=QuestionType.CHOICE,
                )
            )
        for i in range(100):
            mock_db_session.add(
                Question(
                    owner_user_id=mock_user_system_seed.id,
                    chapter_id=mock_chapter.id,
                    content=f"c{i}",
                    difficulty=QuestionDifficulty.C,
                    type=QuestionType.CHOICE,
                )
            )
        mock_db_session.commit()

        # 同 seed 跑 2 次
        sequences: list[list[int]] = []
        for _ in range(2):
            a = generate_assignment_for_chapter(
                mock_db_session,
                owner=mock_user_system_seed,
                chapter=mock_chapter,
                tier="D",
                total_count=100,
                seed=42,
            )
            sequences.append([item.question_id for item in a.items])

        # diff 列表 = 空（B2 brief §4 #3 必报项）
        diffs = [
            (i, sequences[0][i], sequences[1][i])
            for i in range(len(sequences[0]))
            if sequences[0][i] != sequences[1][i]
        ]
        assert diffs == [], (
            f"同 seed 跑 2 次顺序不一致（B2 brief §4 #3 FAIL）: "
            f"前 10 个 diff = {diffs[:10]}, 总不一致 = {len(diffs)}"
        )
        # 序列长度一致（防御性断言）
        assert len(sequences[0]) == 100
        assert len(sequences[1]) == 100
        assert len(sequences[0]) == len(sequences[1])
