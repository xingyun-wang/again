"""tier_to_difficulty mapping test（M2-S2 brief §八.1）。

测试覆盖：
- identity：每个 Tier 值都能映射
- value space isomorphic：顺序 + 元素 + 唯一
"""

from __future__ import annotations

from app.models.academic import QuestionDifficulty, Tier, tier_to_difficulty


def test_tier_to_difficulty_identity():
    """每个 Tier 值都能映射到对应 QuestionDifficulty（D→D / C→C / B→B / A→A）。"""
    for t in Tier:
        result = tier_to_difficulty(t)
        assert result == QuestionDifficulty(t.value)


def test_tier_difficulty_value_space_isomorphic():
    """Tier 与 QuestionDifficulty 值空间必须同构（顺序 + 元素 + 唯一）。"""
    tier_values = [e.value for e in Tier]
    qd_values = [e.value for e in QuestionDifficulty]

    # 顺序相同
    assert tier_values == qd_values
    # 元素齐全
    assert set(tier_values) == {"D", "C", "B", "A"}
    # 唯一性
    assert len(set(tier_values)) == len(tier_values)
    # 都是 4 个
    assert len(tier_values) == 4


def test_tier_to_difficulty_explicit_values():
    """显式值映射（不依赖 enum 顺序，验值）。"""
    assert tier_to_difficulty(Tier.D) == QuestionDifficulty.D
    assert tier_to_difficulty(Tier.C) == QuestionDifficulty.C
    assert tier_to_difficulty(Tier.B) == QuestionDifficulty.B
    assert tier_to_difficulty(Tier.A) == QuestionDifficulty.A
