"""D-28 extraction_source gate 单元测试（D-37 G2 段 B 已删除）。

D-28 段 A 门槛（D-32 M2 工单 A）：
  - 章节数 >= 3
  - 全部 extraction_source == 'detected'

D-37 G2 fail-open 保护迁移历史（2026-10-07 修）：
  原 verify 段 B（强制 ≥1 个非默认路径）与 D-28 段 A 互补互斥，
  导致 verify 恒 FAIL。段 B 已删除；fail-open 防护由独立负向测试
  承担（见 test_fallback_paths_in_extractor.py 静态检查 + follow-up
  detector-direct fixture 测试）。

本测试覆盖 D-28 段 A 真值表：
  - 全 detected + >=3 章 → PASS（端到端成功）
  - 含 fallback → FAIL（段 A 第二项 add_error，不 return 阻断 extract）
  - <3 章 → FAIL（段 A 第一项 add_error 且 return False 阻断 extract）

测试不依赖真实 PDF / DB / HTTP，仅调 _check_extraction_source_gate 核心函数。
"""

from __future__ import annotations


def test_d28_gate_all_detected_passes() -> None:
    """D-28 段 A 全通过：count >= 3 + 全 detected → verify PASS（端到端成功）。

    D-37 段 B 已删除后，全 detected 输入不再被 fail-open 保护在生产 gate 里。
    这是 D-28 原意（"全部 detected = 端到端成功"）的回归测试。
    fail-open 防护由独立测试承担（见 test_fallback_paths_in_extractor.py）。
    """
    from scripts.verify_end_to_end_5_chapters import (
        VerifyReport,
        _check_extraction_source_gate,
    )

    report = VerifyReport()
    chapter_ids: list[int] = [1, 2, 3, 4, 5]
    chapter_sources: list[str] = ["detected"] * len(chapter_ids)

    gate_passed = _check_extraction_source_gate(report, chapter_ids, chapter_sources)

    assert gate_passed, (
        f"全 detected + >=3 章 应 PASS（D-28 端到端成功），"
        f"但 gate_passed={gate_passed}, errors={report.errors}"
    )
    assert report.errors == [], (
        f"全 detected + >=3 章 不应 add_error，但 report.errors={report.errors}"
    )


def test_d28_gate_with_fallback_records_error_but_continues() -> None:
    """D-28 段 A 第二项：≥1 fallback → record error 不 return，继续 extract/lesson-plan。

    与段 A 第一项（<3 章）的"硬阻断"不同 — verify 主流程见到 errors 即可
    退出非零，但 extract/lesson-plan 仍继续让报告齐。
    """
    from scripts.verify_end_to_end_5_chapters import (
        VerifyReport,
        _check_extraction_source_gate,
    )

    report = VerifyReport()
    chapter_ids: list[int] = [1, 2, 3, 4, 5]
    # 真实 extractor 路径：5 章中 4 章 detected + 1 章 fallback（PyMuPDF 主路径
    # 识别不足 → pdfplumber fallback 接管）。
    chapter_sources: list[str] = [
        "detected",
        "detected",
        "detected",
        "detected",
        "pdfplumber_fallback",
    ]

    gate_passed = _check_extraction_source_gate(report, chapter_ids, chapter_sources)

    assert not gate_passed, (
        f"含 fallback 应触发段 A 第二项 FAIL，但 gate_passed={gate_passed}"
    )
    assert any("门槛 A 不齐" in e for e in report.errors), (
        f"段 A 第二项错误消息缺失，errors={report.errors}"
    )


def test_d28_gate_count_below_three_fails_and_returns() -> None:
    """D-28 段 A 第一项：count < 3 → 整体 FAIL 且 return False 阻断后续 extract。"""
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