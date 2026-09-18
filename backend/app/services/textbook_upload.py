"""教材上传 service（M1-B B.3：v0.5 §9.1 PDF 抽取 → 持久化）。

职责：
- 接收 PDF bytes + metadata（name, subject_id, grade_level）
- 校验 magic bytes（%PDF-）
- 写 temp file → 调 ``PDFExtractor.extract_chapter_structure`` → ``ChapterStructure`` 列表
- 持久化 Textbook + N 个 Chapter 行
- 清理 temp file
- 返回 (Textbook 实例, Chapter 列表)；调用方负责 response 构造

Judgment call（B.3 spec §关键技术点 + §Judgment calls）：
- 适配层放 service 层（便于复用 + 不动 extractor 内部逻辑）
- batch 上传不支持（spec 没明；保持 MVP 极简）
- 失败 fail-fast（任一持久化失败抛异常，事务回滚）
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Literal

from sqlalchemy.orm import Session

from app.models import Chapter, GradeLevel, Textbook
from app.pdf.extractor import ChapterStructure, PDFExtractor

logger = logging.getLogger(__name__)

# PDF 文件 magic bytes：文件头 5 字节为 "%PDF-"
PDF_MAGIC_PREFIX = b"%PDF-"


class TextbookUploadError(Exception):
    """教材上传失败（业务层异常；router 转 HTTPException）。

    调用方根据 message 决定 HTTP status（400 / 422 / 500）。
    """


def upload_textbook_with_extraction(
    db: Session,
    *,
    pdf_bytes: bytes,
    name: str,
    subject_id: int | None,
    grade_level: Literal["junior_high", "senior_high"] | None,
) -> tuple[Textbook, list[Chapter]]:
    """上传教材 PDF：extractor 解析章节 + 持久化 Textbook + Chapter。

    Args:
        db: SQLAlchemy Session（调用方控制事务；本函数内 commit）
        pdf_bytes: PDF 文件 bytes
        name: 教材名称
        subject_id: 学科 ID（可空）
        grade_level: 学段（"junior_high" / "senior_high"，可空）

    Returns:
        (Textbook 实例, Chapter 列表) — 都已 refresh，含 id / created_at

    Raises:
        TextbookUploadError: 校验失败 / 抽取失败 / DB 写入失败
    """
    # 1. magic bytes 校验（空文件 / 非 PDF 直接抛）
    if not pdf_bytes:
        raise TextbookUploadError("PDF 文件为空")
    if len(pdf_bytes) < len(PDF_MAGIC_PREFIX):
        raise TextbookUploadError(
            f"文件过小（{len(pdf_bytes)} bytes），不是有效 PDF"
        )
    if not pdf_bytes.startswith(PDF_MAGIC_PREFIX):
        raise TextbookUploadError(
            f"文件不是 PDF（magic bytes 校验失败：开头 {pdf_bytes[:8]!r}，期望以 {PDF_MAGIC_PREFIX!r} 开头）"
        )

    # 2. 写 temp file（PyMuPDF + pdfplumber 都从 file path 读，不接 bytes）
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp_path = Path(f.name)

        # 3. 调 extractor（PyMuPDF 主路径 + pdfplumber fallback + 等分 last-resort）
        extractor = PDFExtractor()
        try:
            chapters_struct: list[ChapterStructure] = extractor.extract_chapter_structure(
                str(tmp_path)
            )
        except (FileNotFoundError, ValueError, RuntimeError) as e:
            raise TextbookUploadError(f"PDF 解析失败：{e}") from e

        if not chapters_struct:
            raise TextbookUploadError("PDF 解析未识别到任何章节（文档可能损坏或为空）")

        # 4. 解析 grade_level
        gl_value: GradeLevel | None = None
        if grade_level is not None:
            try:
                gl_value = GradeLevel(grade_level)
            except ValueError as e:
                raise TextbookUploadError(f"非法 grade_level: {grade_level}") from e

        # 5. 持久化 Textbook + Chapter（commit 失败 → rollback → 抛异常）
        try:
            textbook = Textbook(
                name=name,
                file_path=f"uploaded:{name}.pdf",  # metadata placeholder；B.3 阶段不跟踪物理路径
                subject_id=subject_id,
                grade_level=gl_value,
            )
            db.add(textbook)
            db.flush()  # 取到 textbook.id

            chapters: list[Chapter] = []
            for cs in chapters_struct:
                ch = Chapter(
                    textbook_id=textbook.id,
                    chapter_number=cs.chapter_number,
                    title=cs.title,
                    content_summary=None,  # B.3.1 只入章节骨架；summary 由 /extract 填
                    page_range_start=cs.page_range[0],
                    page_range_end=cs.page_range[1],
                )
                db.add(ch)
                chapters.append(ch)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.exception("textbook upload DB write failed: name=%s", name)
            raise TextbookUploadError(f"DB 写入失败：{e}") from e

        # 6. refresh 拿到 created_at + id
        db.refresh(textbook)
        for ch in chapters:
            db.refresh(ch)

        logger.info(
            "教材上传成功：textbook_id=%s name=%s chapters=%d",
            textbook.id,
            name,
            len(chapters),
        )
        return textbook, chapters
    finally:
        # 7. 清理 temp file（永远执行）
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError as e:  # noqa: BLE001
                logger.warning("temp PDF 清理失败 %s: %s", tmp_path, e)