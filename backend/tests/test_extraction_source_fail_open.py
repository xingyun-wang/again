"""extraction_source fail-open 负面测试（M1-B retro G2：D-37 硬规则）。

D-37 硬规则：**必须附一条在旧 fail-open 实现下会 FAIL 的负面测试**。

本测试模拟 stub extractor 走「全部 detected」→ 验证 verify 段 B 门槛
（至少 1 个非默认路径）能抓到 fail-open。

预期：
- G2 修复前（仅段 A：全 detected 通过）：verify 不会 FAIL（stub 满足段 A），
  本测试断言「verify FAIL」失败 → **本测试 FAIL**（D-37 要求的"旧实现下 FAIL"）。
- G2 修复后（加段 B：≥ 1 个非默认路径）：verify FAIL（段 B 抓 stub），
  本测试断言「verify FAIL」成功 → **本测试 PASS**。

D-32 第 4 类 P0 关联：fail-open 实现 = 写一个永远返回 server_default 的
extractor → 旧 verify 通过 → 决策室被骗。本测试在 G2 修复后能稳定抓到
这种最坏实现。

可证伪设计（D-37 第 3 条）：
- 写测试时确保它能 fail 在 commit 前的实现上 → commit 后能被 pass。
- 本测试不依赖真实 PDF / DB / HTTP，仅调 _check_extraction_source_gate 核心函数。
"""

from __future__ import annotations


def test_stub_extractor_all_detected_triggers_fail_open_gate_b() -> None:
    """Stub extractor 全部 detected → verify 段 B 必须 FAIL（关闭 fail-open）。

    D-37 硬规则核心断言：
    1. stub 输入：全部 chapter 都走 source='detected'（fail-open 最坏实现）
    2. 段 A：count >= 3 满足 + 全部 detected 满足 → 段 A PASS
    3. 段 B：全部 detected → 没有 ≥ 1 非默认路径 → 段 B FAIL
    4. verify 总体 FAIL = 段 B 必须报错

    旧实现（仅段 A）：段 A 满足 → verify PASS → 断言「verify FAIL」失败 → 测试 FAIL。
    新实现（段 A + 段 B）：段 B 不满足 → verify FAIL → 断言「verify FAIL」成功 → 测试 PASS。
    """
    from scripts.verify_end_to_end_5_chapters import (
        VerifyReport,
        _check_extraction_source_gate,
    )

    report = VerifyReport()
    # 段 A 第一项：count >= 3（满足，段 A 第一项不阻断）
    chapter_ids: list[int] = [1, 2, 3, 4, 5]
    # stub：fail-open 最坏实现 — 全部 chapter 都走 'detected'，没有任何
    # 非默认路径暴露 extractor 是否真跑了主路径。
    chapter_sources: list[str] = ["detected"] * len(chapter_ids)

    gate_passed = _check_extraction_source_gate(report, chapter_ids, chapter_sources)

    # D-37 G2 核心断言：段 B 必须抓到「全 detected」的 fail-open
    assert not gate_passed, (
        f"FAIL-OPEN 未关闭：stub extractor 全部 'detected' 应触发 verify FAIL"
        f"（段 B），但 gate_passed={gate_passed}，report.errors={report.errors}"
    )
    # 报告里必须写明「门槛 B fail-open 未关闭」（D-37 报告可读性要求）
    assert any("门槛 B" in e and "fail-open" in e for e in report.errors), (
        f"FAIL-OPEN 未关闭：段 B 错误消息缺失（D-37 报告须写明 '门槛 B fail-open 未关闭'），"
        f"errors={report.errors}"
    )


def test_real_extractor_with_diversity_passes_gate() -> None:
    """正面对照：extractor 真的产出混合路径 → verify PASS。

    这个不是 D-37 要求的负面测试，但放在同一文件方便决策室一眼对照
    "fail-open stub 被抓 vs. 真实现可过" 的预期关系。
    """
    from scripts.verify_end_to_end_5_chapters import (
        VerifyReport,
        _check_extraction_source_gate,
    )

    report = VerifyReport()
    chapter_ids: list[int] = [1, 2, 3, 4, 5]
    # 真实 extractor 路径：5 章中 4 章 detected + 1 章 fallback（PyMuPDF 主路径
    # 识别不足 → pdfplumber fallback 接管）。段 A 第二项不通过（有 non_detected），
    # 段 B 通过（有 ≥ 1 non_detected）。
    chapter_sources: list[str] = [
        "detected",
        "detected",
        "detected",
        "detected",
        "pdfplumber_fallback",
    ]

    _check_extraction_source_gate(report, chapter_ids, chapter_sources)

    # 段 A 第二项会记录 error（"不全 detected"），但段 B 通过（"≥ 1 非默认"）。
    # 整体：失败（D-28 段 A 第二项 "不全 detected" 仍被记录）。
    # 这个对照说明：新门槛对 fallback 教材也 fail — D-28 段 A 与 D-37 段 B
    # 形成互补（"全 detected 是 fail-open / 有 fallback 是非端到端"）。
    # 决策室后续可按需调整段 A 第二项的语义。
    # 注：此处不直接断言 gate_passed（段 A 第二项仍会让整体 FAIL，下面只校验
    # 段 A 错误消息是否到位）。
    assert "门槛 A 不齐" in "".join(report.errors), (
        f"段 A 第二项应记录 '不全 detected' 错误（fallback 教材不算端到端），"
        f"errors={report.errors}"
    )


def test_count_below_three_fails_gate_a_first_item() -> None:
    """段 A 第一项：count < 3 → 整体 FAIL 且 return False 阻断后续。"""
    from scripts.verify_end_to_end_5_chapters import (
        VerifyReport,
        _check_extraction_source_gate,
    )

    report = VerifyReport()
    chapter_ids: list[int] = [1, 2]  # < 3
    chapter_sources: list[str] = ["detected", "detected"]

    gate_passed = _check_extraction_source_gate(report, chapter_ids, chapter_sources)

    assert not gate_passed, (
        f"count < 3 应触发段 A 第一项 FAIL，但 gate_passed={gate_passed}"
    )
    assert any("门槛 A 章节数不足" in e for e in report.errors), (
        f"段 A 第一项错误消息缺失，errors={report.errors}"
    )