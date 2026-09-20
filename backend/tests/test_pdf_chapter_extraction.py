"""章节结构识别测试（M1-A 阶段 2 + M2 工单 A：P0-3 修复）。

覆盖：
1. 真实 PDF（选择性必修 1）能识别 5 章
2. chapter_number 严格递增 1-5
3. title 包含高中地理选择性必修 1 关键词
4. page_range 不重叠 + 边界正确（第一章 start==1，最后一章 end==总页数）
5. ChapterStructure dataclass 结构（sections 空 list）
6. PyMuPDF fallback：主路径 < 3 章时启用 pdfplumber fallback（用合成 PDF 模拟）
7. 异常：文件不存在 / 路径是目录

M2 工单 A（D-28 硬规则）：删除「空白 PDF → 5 章」恒真测试
（旧 test_fallback_when_pymupdf_returns_few_chapters 断言空 PDF 返 5 章，
等于承认 "等分造假" 是正常输出 — 是 P0-3 漏洞）。新行为：空 PDF 等分造
章节后，service 层 Chapter.extraction_source 必须 == 'equal_split_placeholder'
（链路上传后的 ChapterSummary 也必须返回此值）。
本测试文件在 extractor 层验证 source 标记；service / router 层负面前提
在 test_textbook_upload_real_pdf.py。

测试用真 PDF：materials/textbooks/选择性必修1.pdf
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import fitz
import pytest

from app.pdf.extractor import ChapterStructure, PDFExtractor

# 项目根：tests/ 的父目录的父目录
BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
TEXTBOOK_PDF = PROJECT_ROOT / "materials" / "textbooks" / "选择性必修1.pdf"


@pytest.fixture()
def real_textbook_pdf() -> Path:
    """提供真 PDF 路径（缺失则 skip 并 flag）。"""
    if not TEXTBOOK_PDF.exists():
        pytest.skip(
            f"真 PDF 不存在: {TEXTBOOK_PDF}（请决策室补 PDF 后再跑）"
        )
    return TEXTBOOK_PDF


@pytest.fixture()
def empty_pdf(tmp_path: Path) -> Path:
    """造一个 3 页全空 PDF（触发 fallback equal_split_placeholder）。"""
    pdf_path = tmp_path / "empty.pdf"
    doc = fitz.open()
    for _ in range(3):
        doc.new_page(width=400, height=600)
    doc.save(pdf_path)
    doc.close()
    return pdf_path


# ============================================================================
# 真 PDF 测试（材料到位才跑）
# ============================================================================


def test_real_pdf_identifies_five_chapters(real_textbook_pdf: Path) -> None:
    """选择性必修 1 真 PDF 识别出 5 章。"""
    extractor = PDFExtractor()
    chapters = extractor.extract_chapter_structure(str(real_textbook_pdf))
    assert len(chapters) == 5, (
        f"预期 5 章，实际 {len(chapters)}："
        f"{[(c.chapter_number, c.title) for c in chapters]}"
    )
    # 章号严格 1-5
    assert [c.chapter_number for c in chapters] == [1, 2, 3, 4, 5]


def test_chapter_numbers_strictly_increasing(real_textbook_pdf: Path) -> None:
    """chapter_number 严格递增。"""
    extractor = PDFExtractor()
    chapters = extractor.extract_chapter_structure(str(real_textbook_pdf))
    nums = [c.chapter_number for c in chapters]
    for i in range(1, len(nums)):
        assert nums[i] > nums[i - 1], (
            f"chapter_number 非严格递增: {nums}"
        )
    # 期望严格相邻（每章 +1）
    assert nums == list(range(1, len(nums) + 1)), (
        f"chapter_number 应连续 1..N，实际 {nums}"
    )


def test_chapter_titles_contain_keyword(real_textbook_pdf: Path) -> None:
    """title 至少有一章包含高中地理选择性必修 1 关键词。"""
    extractor = PDFExtractor()
    chapters = extractor.extract_chapter_structure(str(real_textbook_pdf))
    keywords = ("地球", "宇宙", "太阳", "大气", "水", "地表", "环境", "整体性")
    matched_any = False
    for ch in chapters:
        if any(kw in ch.title for kw in keywords):
            matched_any = True
            break
    assert matched_any, (
        f"无任何一章 title 包含关键词 {keywords}："
        f"{[c.title for c in chapters]}"
    )


def test_page_ranges_no_overlap_and_valid(real_textbook_pdf: Path) -> None:
    """page_range 不重叠 + 边界正确。"""
    extractor = PDFExtractor()
    chapters = extractor.extract_chapter_structure(str(real_textbook_pdf))
    # 至少有 2 章才能验证不重叠
    assert len(chapters) >= 2
    # 每章至少 1 页
    for ch in chapters:
        start, end = ch.page_range
        assert start <= end, f"chapter {ch.chapter_number} start > end: {ch.page_range}"
        assert start >= 1, f"chapter {ch.chapter_number} start < 1: {ch.page_range}"

    # 不重叠：ch[i].end < ch[i+1].start
    for i in range(len(chapters) - 1):
        end_i = chapters[i].page_range[1]
        start_next = chapters[i + 1].page_range[0]
        assert end_i < start_next, (
            f"chapter {chapters[i].chapter_number}.end={end_i} 不小于 "
            f"chapter {chapters[i + 1].chapter_number}.start={start_next}"
        )


def test_first_and_last_chapter_page_bounds(real_textbook_pdf: Path) -> None:
    """第一章 page_range start 应在文档前部；最后一章 end == 总页数。"""
    extractor = PDFExtractor()
    chapters = extractor.extract_chapter_structure(str(real_textbook_pdf))
    # 第一章 start >= 1（不严格 == 1，因为教材前面可能有目录/前言）
    assert chapters[0].page_range[0] >= 1
    # 最后一章 end 应 == 总页数
    doc = extractor.extract(str(real_textbook_pdf))
    total_pages = len(doc.pages)
    assert chapters[-1].page_range[1] == total_pages, (
        f"最后一章 end={chapters[-1].page_range[1]} != 总页数 {total_pages}"
    )


def test_chapter_structure_dataclass_fields(real_textbook_pdf: Path) -> None:
    """ChapterStructure 字段类型 + sections 默认空 list。"""
    extractor = PDFExtractor()
    chapters = extractor.extract_chapter_structure(str(real_textbook_pdf))
    ch = chapters[0]
    assert isinstance(ch, ChapterStructure)
    assert isinstance(ch.chapter_number, int)
    assert isinstance(ch.title, str)
    assert isinstance(ch.page_range, tuple)
    assert len(ch.page_range) == 2
    assert all(isinstance(p, int) for p in ch.page_range)
    assert ch.sections == []  # M1 不实现子节


# ============================================================================
# 合成 PDF + fallback 测试（不依赖真材料）
# ============================================================================


def test_empty_pdf_returns_equal_split_placeholder_source(empty_pdf: Path) -> None:
    """M2 工单 A（P0-3 修复）：空 PDF 等分造章节后，extraction_source 必须标
    'equal_split_placeholder'（**真实造假，必须标记**）。

    本测试验证 extractor 层：旧版 test_fallback_when_pymupdf_returns_few_chapters
    「空 PDF → 返 5 章」是恒真断言（D-28 反例）；新版改为：等分行为仍可走
    （保留 last-resort 防"返回 0 章"崩溃），但 extraction_source 必须如实标记。
    """
    extractor = PDFExtractor()
    result = extractor.extract_chapter_structure_with_source(str(empty_pdf))
    # 等分有 5 章，但 source 标记 = placeholder（与上一阶段判断不同）
    assert len(result.chapters) == 5
    assert result.extraction_source == "equal_split_placeholder", (
        f"等分走 fallback 后必须标 equal_split_placeholder，"
        f"实际 {result.extraction_source!r}"
    )
    # 拼接上同一入参的 legacy API 也仍返 5 章（保持代码使用点不变）
    legacy = extractor.extract_chapter_structure(str(empty_pdf))
    assert len(legacy) == 5


def test_real_pdf_returns_detected_source(real_textbook_pdf: Path) -> None:
    """M2 工单 A：真 PDF 走主路径时 extraction_source == 'detected'。"""
    extractor = PDFExtractor()
    result = extractor.extract_chapter_structure_with_source(str(real_textbook_pdf))
    assert result.extraction_source == "detected", (
        f"主路径识别 ≥3 章应返 detected，实际 {result.extraction_source!r}"
    )
    assert len(result.chapters) >= 3


def test_pymupdf_failure_triggers_pdfplumber_fallback(tmp_path: Path) -> None:
    """PyMuPDF 主路径抛异常时，应自动尝试 pdfplumber fallback。"""
    # 造一个能打开的 PDF
    pdf_path = tmp_path / "real.pdf"
    doc = fitz.open()
    for i in range(2):
        page = doc.new_page(width=400, height=600)
        page.insert_text((50, 50), f"第一章 内容 page {i + 1}")
    doc.save(pdf_path)
    doc.close()

    extractor = PDFExtractor()
    # mock PyMuPDF scan 让它识别不到（返回空 dict），触发 pdfplumber fallback
    # pdfplumber 应该能识别「第一章 内容 page ...」行——但我们用更强的 mock：
    # 让 PyMuPDF scan 直接 raise RuntimeError，验证 fallback 仍然能跑通
    with patch.object(
        PDFExtractor,
        "_scan_chapters_pymupdf",
        side_effect=RuntimeError("PyMuPDF 模拟失败"),
    ):
        result = extractor.extract_chapter_structure_with_source(str(pdf_path))
    # PyMuPDF raise 后 fallback 应该接管：这里走 pdfplumber_fallback 或
    # equal_split_placeholder（取决于 pdfplumber 是否能识别出章节）
    assert result.extraction_source in {"pdfplumber_fallback", "equal_split_placeholder"}, (
        f"PyMuPDF 抛 RuntimeError 后应走 fallback，实际 {result.extraction_source!r}"
    )
    # 至少走 fallback 路径（last-resort 等分 5 章或 pdfplumber 识别）
    assert len(result.chapters) >= 1


def test_extract_chapter_structure_nonexistent_file() -> None:
    """文件不存在抛 FileNotFoundError。"""
    extractor = PDFExtractor()
    with pytest.raises(FileNotFoundError):
        extractor.extract_chapter_structure("/tmp/does-not-exist-chapter-test.pdf")


def test_extract_chapter_structure_directory(tmp_path: Path) -> None:
    """路径是目录时抛 ValueError。"""
    extractor = PDFExtractor()
    with pytest.raises(ValueError, match="不是文件"):
        extractor.extract_chapter_structure(str(tmp_path))


def test_chapter_structure_dataclass_direct_construction() -> None:
    """ChapterStructure 可独立构造（dataclass 默认值 + 可变结构）。"""
    ch = ChapterStructure(
        chapter_number=1,
        title="测试章",
        page_range=(1, 10),
    )
    assert ch.chapter_number == 1
    assert ch.title == "测试章"
    assert ch.page_range == (1, 10)
    assert ch.sections == []
    # sections 可扩展（M1 留口子）
    ch.sections.append({"name": "第一节"})
    assert len(ch.sections) == 1
