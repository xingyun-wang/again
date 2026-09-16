"""PDF Extractor 单元测试。

构造一个最小 PDF（含一段文本）验证：
- extract() 返回 PDFDocument + 至少一页
- extract_pages() 范围生效
- extract_tables() 即使没有表格也返回空 list

构造 PDF 用 PyMuPDF 自己写（不依赖外部文件）。
"""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from app.pdf.extractor import PDFExtractor


@pytest.fixture()
def sample_pdf(tmp_path: Path) -> Path:
    """造一个 3 页的简单 PDF：每页一段文本 + 第 2 页加个矩形当"伪表格区域"。"""
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=400, height=600)
        page.insert_text((50, 50), f"Page {i + 1} content")
        if i == 1:
            # 画一个表格占位框（pdfplumber 不一定能识别为表，但至少不报错）
            rect = fitz.Rect(50, 100, 350, 200)
            page.draw_rect(rect)
    doc.save(pdf_path)
    doc.close()
    return pdf_path


def test_extract_returns_document(sample_pdf: Path) -> None:
    """extract() 返回 PDFDocument 含正确页数。"""
    extractor = PDFExtractor()
    doc = extractor.extract(str(sample_pdf))
    assert len(doc.pages) == 3
    assert doc.metadata["page_count"] == 3
    assert doc.metadata["source_path"].endswith("sample.pdf")


def test_extract_pages_have_text(sample_pdf: Path) -> None:
    """每页 text 字段包含插入的文本。"""
    extractor = PDFExtractor()
    doc = extractor.extract(str(sample_pdf))
    assert "Page 1 content" in doc.pages[0].text
    assert "Page 2 content" in doc.pages[1].text
    assert "Page 3 content" in doc.pages[2].text


def test_extract_page_numbers_are_one_based(sample_pdf: Path) -> None:
    """page_no 从 1 开始。"""
    extractor = PDFExtractor()
    doc = extractor.extract(str(sample_pdf))
    assert [p.page_no for p in doc.pages] == [1, 2, 3]


def test_extract_pages_range(sample_pdf: Path) -> None:
    """extract_pages() 范围提取生效。"""
    extractor = PDFExtractor()
    pages = extractor.extract_pages(str(sample_pdf), (2, 2))
    assert len(pages) == 1
    assert pages[0].page_no == 2


def test_extract_pages_range_clipped(sample_pdf: Path) -> None:
    """超出范围自动截断。"""
    extractor = PDFExtractor()
    pages = extractor.extract_pages(str(sample_pdf), (2, 99))
    assert len(pages) == 2
    assert [p.page_no for p in pages] == [2, 3]


def test_extract_pages_range_start_beyond_total(sample_pdf: Path) -> None:
    """start 大于总页数时返回空 list（不抛错）。"""
    extractor = PDFExtractor()
    pages = extractor.extract_pages(str(sample_pdf), (99, 100))
    assert pages == []


def test_extract_pages_invalid_range(sample_pdf: Path) -> None:
    """非法范围抛 ValueError。"""
    extractor = PDFExtractor()
    with pytest.raises(ValueError, match="page_range 不合法"):
        extractor.extract_pages(str(sample_pdf), (0, 2))
    with pytest.raises(ValueError, match="page_range 不合法"):
        extractor.extract_pages(str(sample_pdf), (3, 1))


def test_extract_tables_returns_list(sample_pdf: Path) -> None:
    """extract_tables() 至少返回 list（不一定识别出表，但接口稳定）。"""
    extractor = PDFExtractor()
    tables = extractor.extract_tables(str(sample_pdf))
    assert isinstance(tables, list)


def test_extract_nonexistent_file() -> None:
    """文件不存在抛 FileNotFoundError。"""
    extractor = PDFExtractor()
    with pytest.raises(FileNotFoundError):
        extractor.extract("/tmp/does-not-exist-m0-test.pdf")


def test_extract_path_is_directory(tmp_path: Path) -> None:
    """路径是目录时抛 RuntimeError。"""
    extractor = PDFExtractor()
    with pytest.raises(RuntimeError, match="不是文件"):
        extractor.extract(str(tmp_path))
