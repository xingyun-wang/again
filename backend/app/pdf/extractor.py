"""PDF 解析封装（v0.5 §9.1 已定：PyMuPDF + pdfplumber 双库）。

PyMuPDF (pymupdf) 处理：文本 + 图像 + 坐标（地理教材地图 / 示意图）
pdfplumber 处理：表格（地理教材数据表）
两者互补，覆盖教材全部类型。

设计要点：
- PDFPage / PDFDocument 用 dataclass，简洁清晰
- 提取失败时不整体崩溃，单页失败记录到 metadata
- extract_pages 支持范围提取（M1+ 分章节处理用得到）
- extract_tables 单独暴露，便于 M1+ 题库构建做表格题快速通道
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber

logger = logging.getLogger(__name__)


@dataclass
class PDFPage:
    """单页 PDF 内容。"""

    page_no: int
    text: str
    tables: list[list[list[str]]]
    images: list[bytes]
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class PDFDocument:
    """完整 PDF 文档内容。"""

    pages: list[PDFPage]
    metadata: dict[str, object] = field(default_factory=dict)


class PDFExtractor:
    """PDF 解析器：PyMuPDF + pdfplumber 组合。

    用法：
        extractor = PDFExtractor()
        doc = extractor.extract("path/to/textbook.pdf")
        for page in doc.pages:
            print(page.page_no, page.text[:100])
    """

    def extract(self, file_path: str) -> PDFDocument:
        """解析完整 PDF 文档。

        Args:
            file_path: PDF 文件路径

        Returns:
            PDFDocument（含全部页的文本/表格/图像/元数据）

        Raises:
            FileNotFoundError: 文件不存在
            RuntimeError: 解析失败
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {file_path}")
        if not path.is_file():
            raise RuntimeError(f"PDF 路径不是文件: {file_path}")

        doc_meta: dict[str, object] = {
            "source_path": str(path.resolve()),
            "errors": [],
        }
        errors: list[str] = []
        pages: list[PDFPage] = []

        # PyMuPDF 解析（文本 + 图像 + 元数据）
        try:
            with fitz.open(path) as pdf:
                doc_meta["page_count"] = pdf.page_count
                doc_meta["pdf_metadata"] = dict(pdf.metadata or {})
                for i in range(pdf.page_count):
                    page = pdf.load_page(i)
                    page_meta: dict[str, object] = {}
                    try:
                        text = page.get_text("text")
                    except Exception as e:  # noqa: BLE001
                        logger.warning("PyMuPDF 提取文本失败 page=%s: %s", i + 1, e)
                        text = ""
                        page_meta["text_error"] = str(e)

                    images: list[bytes] = []
                    try:
                        for img_info in page.get_images(full=True):
                            xref = img_info[0]
                            base = pdf.extract_image(xref)
                            if base and base.get("image"):
                                images.append(base["image"])
                    except Exception as e:  # noqa: BLE001
                        logger.warning("PyMuPDF 提取图像失败 page=%s: %s", i + 1, e)
                        page_meta["image_error"] = str(e)

                    pages.append(
                        PDFPage(
                            page_no=i + 1,
                            text=text,
                            tables=[],  # 表格由 pdfplumber 填充
                            images=images,
                            metadata=page_meta,
                        )
                    )
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"PyMuPDF 打开 PDF 失败: {e}") from e

        # pdfplumber 解析（表格）
        try:
            with pdfplumber.open(path) as pdf:
                if len(pdf.pages) != len(pages):
                    errors.append(
                        f"pdfplumber 页数 {len(pdf.pages)} 与 PyMuPDF {len(pages)} 不一致"
                    )
                for i, plumber_page in enumerate(pdf.pages):
                    if i >= len(pages):
                        break
                    try:
                        tables = plumber_page.extract_tables() or []
                        # 把所有 cell 转 str（pdfplumber 可能返回 None）
                        tables_str: list[list[list[str]]] = [
                            [[("" if c is None else str(c)) for c in row] for row in tbl]
                            for tbl in tables
                        ]
                        pages[i].tables = tables_str
                    except Exception as e:  # noqa: BLE001
                        logger.warning("pdfplumber 提取表格失败 page=%s: %s", i + 1, e)
                        pages[i].metadata["table_error"] = str(e)
        except Exception as e:  # noqa: BLE001
            # pdfplumber 失败不致命（文本已经能拿到）
            logger.warning("pdfplumber 打开 PDF 失败: %s", e)
            errors.append(f"pdfplumber_error: {e}")

        doc_meta["errors"] = errors
        return PDFDocument(pages=pages, metadata=doc_meta)

    def extract_pages(self, file_path: str, page_range: tuple[int, int]) -> list[PDFPage]:
        """解析指定页范围（含两端，1-based）。

        Args:
            file_path: PDF 文件路径
            page_range: (start, end)，1-based，含两端

        Returns:
            指定页的 PDFPage 列表

        Raises:
            ValueError: page_range 不合法
        """
        start, end = page_range
        if start < 1 or end < start:
            raise ValueError(f"page_range 不合法: {page_range}（start ≥ 1，end ≥ start）")

        doc = self.extract(file_path)
        total = len(doc.pages)
        # 截断到文档范围内
        end_clipped = min(end, total)
        if start > total:
            return []
        return [p for p in doc.pages if start <= p.page_no <= end_clipped]

    def extract_tables(self, file_path: str) -> list[list[list[str]]]:
        """提取 PDF 全部页的全部表格（扁平 list）。

        Args:
            file_path: PDF 文件路径

        Returns:
            表格列表，每个表格是 [[cell, ...], ...]
        """
        doc = self.extract(file_path)
        all_tables: list[list[list[str]]] = []
        for page in doc.pages:
            all_tables.extend(page.tables)
        return all_tables
