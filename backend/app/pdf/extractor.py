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
import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber

logger = logging.getLogger(__name__)

# 抽取「第X章 title」的捕获正则（用于解析章号 + 标题文字）
# 注意：每章标题在 PDF 中通常以页眉形式重复多次（每章约 8 次），
# 所以匹配后必须按 chapter_number 去重、取首次出现页作为 page_range.start。
_CHAPTER_PARSE_RE = re.compile(
    r"^第\s*([一二三四五六七八九十百千\d]+)\s*章\s*([\u4e00-\u9fff]+)"
)
_CHAPTER_PARSE_EN_RE = re.compile(
    r"^Chapter\s+(\d+)\s*([\u4e00-\u9fffA-Za-z]+)"
)

# D-29 第 3 条：Chapter.title 退化为「第N章」模板判定（M1-B retro P1-5）
# 命中模式：第[一-十百千0-9]章（可含任意空白；其他字符不行）
TEMPLATE_TITLE_PATTERN = re.compile(
    r"^第\s*[一二三四五六七八九十百千0-9]+\s*章\s*$"
)


def is_template_title(title: str) -> bool:
    """判定 Chapter.title 是否退化为「第N章」模板（P1-5 service 层标记用）。

    D-29 第 3 条：Chapter.title 质量门槛；extraction_source='equal_split_placeholder'
    时 title 通常是「第1章」「第N章」之类占位字符串，需触发人工审阅流程（§7.5）。

    命中模式示例（True）：
        - 「第一章」「第 3 章」「第十二章」「第N章」「第 9 章」
    命中非模式示例（False）：
        - 「地球运动」「大气受热过程」「Chapter 1: Earth」「第三章 地球运动」

    Args:
        title: 待判定字符串（None/空 → True，空字符串等同模板）

    Returns:
        True  = 模板化标题（需标 PENDING 审阅）
        False = 真实标题（保留默认 flow）
    """
    if not title:
        return True
    return bool(TEMPLATE_TITLE_PATTERN.match(title.strip()))


# 中文数字 → int（支持到「九十九」够用，M1 教材不超过二十）
_CN_NUM_MAP: dict[str, int] = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}


def _parse_chinese_number(s: str) -> int | None:
    """解析中文数字到 int；不支持返回 None。

    支持：「一」~「九」、「十」~「十九」、「二十」~「九十九」。
    """
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if len(s) == 1:
        return _CN_NUM_MAP.get(s)
    if len(s) == 2:
        if s[0] == "十":
            return 10 + _CN_NUM_MAP.get(s[1], 0)
        if s[1] == "十":
            return _CN_NUM_MAP.get(s[0], 0) * 10
    if len(s) == 3 and s[1] == "十":
        return _CN_NUM_MAP.get(s[0], 0) * 10 + _CN_NUM_MAP.get(s[2], 0)
    return None


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


@dataclass
class ChapterStructure:
    """章节结构（M1 阶段 2：仅章节级，子节留空）。

    - chapter_number: 1-based 章号（与「第N章」中的 N 一致）
    - title: 章节完整标题（如「第一章 地球的运动」）
    - page_range: (start, end)，1-based，含两端
    - sections: 子节列表（M1 不实现，留空 list）
    """

    chapter_number: int
    title: str
    page_range: tuple[int, int]  # (start, end) 1-based inclusive
    sections: list[object] = field(default_factory=list)


@dataclass
class ChapterStructureResult:
    """M2 工单 A：章节抽取结果 + 链路真源标记。

    - chapters: 抽到的 ChapterStructure 列表（按 chapter_number 升序）
    - extraction_source: 抽取路径来源（snake_case）
      - 'detected'                — PyMuPDF 主路径 ≥3 章，未走 fallback
      - 'pdfplumber_fallback'     — PyMuPDF 识别不足 / 失败，pdfplumber fallback 接管
      - 'equal_split_placeholder' — 主路径 + fallback 都识别不足，等分造章节
    - service 据此填 Chapter.extraction_source + content_summary 判空决定是否
      'scanned_pdf_empty'。
    """

    chapters: list[ChapterStructure]
    extraction_source: str


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

    def extract_chapter_structure(self, file_path: str) -> list[ChapterStructure]:
        """按章节解析教材，返回结构化章节列表。

        实现策略：
        1. PyMuPDF 主路径：用 ``page.get_text("text")`` 抽取每页文本，
           按优先级正则识别「第X章」「Chapter N」标题；按 chapter_number
           去重（PDF 页眉会重复每章标题），取每个 chapter_number 首次出现
           的页面作为 page_range.start。
        2. page_range.end 推断：第 N 章 end = 第 N+1 章 start - 1；
           最后一章 end = 文档总页数。
        3. pdfplumber fallback：当 PyMuPDF 识别失败（< 3 章 或 全部为空）
           时启用，用 ``pdfplumber.open(file_path).pages[i].extract_text()``
           重新跑同样正则。
        4. last resort：当主路径 + fallback 都识别不出章节（< 3 章），
           按总页数等分（默认 5 章）作为占位结构。

        Args:
            file_path: PDF 文件路径

        Returns:
            ChapterStructure 列表，按 chapter_number 升序排列

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 不是 PDF 文件
            RuntimeError: PDF 解析失败
        """
        return self.extract_chapter_structure_with_source(file_path).chapters

    def extract_chapter_structure_with_source(self, file_path: str) -> ChapterStructureResult:
        """M2 工单 A：同 extract_chapter_structure，但额外返回 extraction_source。

        返回 ``ChapterStructureResult``，含：
        - chapters: ChapterStructure 列表
        - extraction_source:
            - 'detected'                — PyMuPDF 主路径 ≥3 章
            - 'pdfplumber_fallback'     — PyMuPDF 识别不足 / 失败，pdfplumber 接管
            - 'equal_split_placeholder' — 主路径 + fallback 都识别不足，等分造章节

        service 据此填 Chapter.extraction_source；content_summary 抽到空文本时
        service 单独再标 'scanned_pdf_empty'（不在 extractor 层做，因为 extract_pages
        拿全文可能拿到图章等非章节文本，service 拿到 summary 后才判空更稳）。

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 不是 PDF 文件
            RuntimeError: PDF 解析失败
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {file_path}")
        if not path.is_file():
            raise ValueError(f"PDF 路径不是文件: {file_path}")

        # 主路径：PyMuPDF
        extraction_source = "detected"
        try:
            chapters, total_pages = self._scan_chapters_pymupdf(path)
        except RuntimeError as e:
            # PyMuPDF 完全失败（打不开文件、单页全报） → 降级到 pdfplumber
            logger.warning("PyMuPDF 章节扫描整体失败，降级到 pdfplumber: %s", e)
            chapters, total_pages = self._scan_chapters_pdfplumber(path)
            extraction_source = "pdfplumber_fallback"
        if len(chapters) < 3:
            logger.warning(
                "PyMuPDF 章节识别不足（%d 章），启用 pdfplumber fallback",
                len(chapters),
            )
            fb_chapters, fb_total = self._scan_chapters_pdfplumber(path)
            if (fb_chapters and len(fb_chapters) > len(chapters)) or len(fb_chapters) >= 3:
                # fb_chapters 比当前更完整（>= 3 章 或单纯更多）才采纳
                chapters = fb_chapters
                total_pages = fb_total
                extraction_source = "pdfplumber_fallback"

        # last resort：等分
        if len(chapters) < 3:
            logger.warning(
                "PDF 章节识别仍不足（%d 章），启用 last-resort 等分（5 章）",
                len(chapters),
            )
            chapters = self._fallback_equal_split(total_pages, target_count=5)
            extraction_source = "equal_split_placeholder"

        # 构造 ChapterStructure（含 page_range 推断）
        result_chapters = self._build_chapter_structures(chapters, total_pages)
        if extraction_source != "detected":
            logger.warning(
                "extract_chapter_structure_with_source 走 fallback 路径：%s",
                extraction_source,
            )
        return ChapterStructureResult(
            chapters=result_chapters, extraction_source=extraction_source
        )

    # -------- extract_chapter_structure 内部辅助 --------

    @staticmethod
    def _parse_chapter_line(line: str) -> tuple[int, str] | None:
        """解析单行文本，命中章节正则则返回 (chapter_number, title)。

        Args:
            line: 原始单行（未 strip）

        Returns:
            (chapter_number, title) 或 None
        """
        s = line.strip()
        if not s:
            return None

        # 中文「第X章」
        m = _CHAPTER_PARSE_RE.match(s)
        if m:
            num_str = m.group(1)
            n = _parse_chinese_number(num_str)
            if n is not None and 0 < n <= 99:
                return n, s
            return None

        # 英文 "Chapter N"
        m = _CHAPTER_PARSE_EN_RE.match(s)
        if m:
            n = int(m.group(1))
            if 0 < n <= 99:
                return n, s
            return None

        return None

    def _scan_chapters_pymupdf(
        self, path: Path
    ) -> tuple[dict[int, tuple[str, int]], int]:
        """PyMuPDF 扫描每页，识别章节（按 chapter_number 去重，记录首次出现页）。

        Returns:
            (chapters_dict, total_pages)
            - chapters_dict: {chapter_number: (title_text, first_page_no)}
              first_page_no 1-based，是该章 title 首次出现的页（用于 page_range.start）。
            - total_pages: 文档总页数
        """
        chapters: dict[int, tuple[str, int]] = {}
        total_pages = 0
        try:
            with fitz.open(path) as pdf:
                total_pages = pdf.page_count
                for i in range(total_pages):
                    try:
                        page = pdf.load_page(i)
                        text = page.get_text("text")
                    except Exception as e:  # noqa: BLE001
                        logger.warning(
                            "PyMuPDF 章节扫描失败 page=%s: %s", i + 1, e
                        )
                        continue
                    page_no = i + 1
                    for line in text.split("\n"):
                        parsed = self._parse_chapter_line(line)
                        if parsed is None:
                            continue
                        n, title = parsed
                        # 去重：取首次出现的页 + title
                        if n not in chapters:
                            chapters[n] = (title, page_no)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"PyMuPDF 打开 PDF 失败: {e}") from e
        return chapters, total_pages

    def _scan_chapters_pdfplumber(
        self, path: Path
    ) -> tuple[dict[int, tuple[str, int]], int]:
        """pdfplumber fallback：用 extract_text() 重跑正则。

        Returns:
            (chapters_dict, total_pages)
            chapters_dict: {chapter_number: (title_text, first_page_no)}
        """
        chapters: dict[int, tuple[str, int]] = {}
        total_pages = 0
        try:
            with pdfplumber.open(path) as pdf:
                total_pages = len(pdf.pages)
                for i, plumber_page in enumerate(pdf.pages):
                    try:
                        text = plumber_page.extract_text() or ""
                    except Exception as e:  # noqa: BLE001
                        logger.warning(
                            "pdfplumber 章节扫描失败 page=%s: %s", i + 1, e
                        )
                        continue
                    page_no = i + 1
                    for line in text.split("\n"):
                        parsed = self._parse_chapter_line(line)
                        if parsed is None:
                            continue
                        n, title = parsed
                        if n not in chapters:
                            chapters[n] = (title, page_no)
        except Exception as e:  # noqa: BLE001
            logger.warning("pdfplumber 打开 PDF 失败: %s", e)
            return chapters, total_pages
        return chapters, total_pages

    @staticmethod
    def _fallback_equal_split(
        total_pages: int, target_count: int = 5
    ) -> dict[int, tuple[str, int]]:
        """last resort：按总页数等分 target_count 章。

        返回 {chapter_number: (placeholder_title, start_page)}。
        start_page 用等距分配（idx * per + 1），不依赖真实章节位置。
        """
        if total_pages <= 0 or target_count <= 0:
            return {}
        per = max(1, total_pages // target_count)
        result: dict[int, tuple[str, int]] = {}
        for n in range(1, target_count + 1):
            start = (n - 1) * per + 1
            result[n] = (f"第{n}章", start)
        return result

    @staticmethod
    def _build_chapter_structures(
        chapters: dict[int, tuple[str, int]], total_pages: int
    ) -> list[ChapterStructure]:
        """从 {chapter_number: (title, start_page)} + 总页数 构造 ChapterStructure。

        page_range 推断：
        - 按 chapter_number 升序排列
        - 第 N 章 start = 该章首次出现页（来自 scan 阶段）
        - 第 N 章 end = 第 N+1 章 start - 1；最后一章 end = 总页数

        边界保护：
        - start 截断到 [1, total_pages]
        - end 截断到 [start, total_pages]
        - 若章节数 > 总页数（如空 PDF + fallback 5 章 vs 3 页），start 会被
          截到 total_pages；末章 end 仍 = total_pages。page_range 在这种
          退化情况下允许部分重叠——但保证 start >= 1 且 end <= total_pages。
        """
        if not chapters or total_pages <= 0:
            return []

        sorted_nums = sorted(chapters.keys())
        starts_raw = [chapters[n][1] for n in sorted_nums]
        # 截断 start 到 [1, total_pages]
        starts = [max(1, min(s, total_pages)) for s in starts_raw]

        result: list[ChapterStructure] = []
        for idx, n in enumerate(sorted_nums):
            title = chapters[n][0]
            start = starts[idx]
            if idx == len(sorted_nums) - 1:
                end = total_pages
            else:
                next_start = starts[idx + 1]
                end = max(start, next_start - 1)
            end = min(end, total_pages)
            if end < start:
                end = start
            result.append(
                ChapterStructure(
                    chapter_number=n,
                    title=title,
                    page_range=(start, end),
                    sections=[],
                )
            )
        return result

