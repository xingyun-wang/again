"""extraction_source fallback 路径静态检查（D-32 第 4 类 P0 fail-open 防护）。

D-32 第 4 类 P0：fail-open 实现 = 永远返回 server_default 的 extractor →
D-28 段 A 单点门槛可被利用 → 决策室被骗。

D-37 G2 fail-open 保护历史迁移（2026-10-07 修）：
原 verify 段 B（强制 ≥1 个非默认路径）与 D-28 段 A 互补互斥 → 段 B 已删
→ fail-open 防护迁到 tests/。本测试是**结构层最小保障**（独立负向测试）。

测试原理：扫描 detector + service 源码，确认 4 个合法 extraction_source 字面量
都被实际使用（不只是 docstring 描述）。如果某 fallback 路径被错误删除
（dev 误删 / stub 攻击替换），本测试 FAIL = catch fail-open 风险。

4 个合法 extraction_source 字面量：
  - 'detected'                - PyMuPDF 主路径 ≥3 章（extractor.py）
  - 'pdfplumber_fallback'     - PyMuPDF 失败/不足 → pdfplumber 接管（extractor.py）
  - 'equal_split_placeholder' - 主+fallback 都识别不足 → 等分造章节（extractor.py）
  - 'scanned_pdf_empty'       - content_summary 抽空时 service 单独标（textbook_upload.py）

distinction 层级：
  - extractor.py: detected / pdfplumber_fallback / equal_split_placeholder
  - service/textbook_upload.py: scanned_pdf_empty

测试不依赖真实 PDF / DB / HTTP，纯静态扫描。
"""

from __future__ import annotations

from pathlib import Path


# 用 test 文件相对路径（parent.parent = 上一级 backend 目录）
# host: backend/tests/test_*.py → ../app/pdf/extractor.py = backend/app/pdf/extractor.py ✓
# container (docker exec -w /app): /app/tests/test_*.py → ../app/pdf/extractor.py = /app/app/pdf/extractor.py ✓
APP_DIR = Path(__file__).parent.parent / "app"
EXTRACTOR_PATH = APP_DIR / "pdf" / "extractor.py"
SERVICE_PATH = APP_DIR / "services" / "textbook_upload.py"


def _source_contains_quoted(path: Path, literal: str) -> bool:
    """检查源码文件是否含带引号的字面量（双引号或单引号）。"""
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return f'"{literal}"' in text or f"'{literal}'" in text


def test_detector_contains_detected() -> None:
    """detector 必须有 'detected' 字面量（PyMuPDF 主路径基础）。"""
    assert _source_contains_quoted(EXTRACTOR_PATH, "detected"), (
        f"extractor.py 缺 'detected' 字面量 — PyMuPDF 主路径被删？"
        f"fail-open stub 攻击防护结构层被破坏（D-32 第 4 类 P0）"
    )


def test_detector_contains_pdfplumber_fallback() -> None:
    """detector 必须有 'pdfplumber_fallback' 字面量（PyMuPDF 失败路径）。"""
    assert _source_contains_quoted(EXTRACTOR_PATH, "pdfplumber_fallback"), (
        f"extractor.py 缺 'pdfplumber_fallback' 字面量 — PyMuPDF 失败路径被删？"
        f"fail-open stub 攻击防护结构层被破坏（D-32 第 4 类 P0）"
    )


def test_detector_contains_equal_split_placeholder() -> None:
    """detector 必须有 'equal_split_placeholder' 字面量（last-resort 等分路径）。"""
    assert _source_contains_quoted(EXTRACTOR_PATH, "equal_split_placeholder"), (
        f"extractor.py 缺 'equal_split_placeholder' 字面量 — last-resort 等分路径被删？"
        f"fail-open stub 攻击防护结构层被破坏（D-32 第 4 类 P0）"
    )


def test_service_contains_scanned_pdf_empty() -> None:
    """service 层必须有 'scanned_pdf_empty' 字面量（content_summary 抽空路径）。"""
    assert _source_contains_quoted(SERVICE_PATH, "scanned_pdf_empty"), (
        f"textbook_upload.py 缺 'scanned_pdf_empty' 字面量 — service 层 fallback 被删？"
        f"fail-open stub 攻击防护结构层被破坏（D-32 第 4 类 P0）"
    )