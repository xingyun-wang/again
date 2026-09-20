"""教材上传 service（M2 工单 A：知识链路真实性 — P0-1/P0-2/P0-3 合并修复）。

职责（M2 工单 A 后）：
- 接收 ``file_path: str`` + metadata（name, subject_id, grade_level）
- 校验 magic bytes（%PDF-，A 阶段仍全量读 5 字节；C 工地可能改流式 peek，接口兼容）
- 调 ``PDFExtractor.extract_chapter_structure_with_source`` → ``ChapterStructureResult``
- 调 ``extract_pages`` 每章页范围抽正文，填 Chapter.content_summary
  （空文本 → content_summary=None + extraction_source='scanned_pdf_empty'）
- 持久化 Textbook + N 个 Chapter 行（含 extraction_source）
- 把 PDF 从临时路径落到 ``uploads/{textbook_id}/{filename}.pdf``（DB 相对路径）
- 清理失败回滚时的残留文件
- 返回 (Textbook 实例, Chapter 列表)；调用方负责 response 构造

设计要点：
- 接口约定（与工单 C 共享）：service 签名接受 ``file_path: str``，C 工地接管后
  可能从流式接收改为预写盘，但接口形态不变。
- ``finally: tmp_path.unlink()`` 已删除（M2 工单 A P0-2 修复）：落盘文件 = 真
  artifact，不再走 /tmp。
- 失败回滚：DB rollback + 删已落盘文件 + 删残留 pending 文件（best effort）。

Judgment call（M2 工单 A）：
- 文件落盘失败（如磁盘满）→ 抛 TextbookUploadError，DB rollback；pending
  路径下文件残留由 router 兜底清理。
- extracted_source 优先级：service 一律采纳 extractor 的判定；content_summary
  文本判空后单独把 extraction_source 改写为 'scanned_pdf_empty'（避免和
  'equal_split_placeholder' 混淆）。
"""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO, Literal

from sqlalchemy.orm import Session

from app.models import Chapter, GradeLevel, Textbook
from app.pdf.extractor import ChapterStructureResult, PDFExtractor

logger = logging.getLogger(__name__)

# PDF 文件 magic bytes：文件头 5 字节为 "%PDF-"
PDF_MAGIC_PREFIX = b"%PDF-"

# 落盘根目录（容器内路径）。docker-compose.yml backend 段 bind mount
# ./data/uploads:/app/data/uploads；CI / 本地测试可用环境变量覆盖。
DEFAULT_UPLOADS_DIR = "/app/data/uploads"

# extraction_source 取值（snake_case；与 alembic 0004 + schemas.Literal 对齐）
SRC_DETECTED = "detected"
SRC_PDFPLUMBER_FALLBACK = "pdfplumber_fallback"
SRC_EQUAL_SPLIT_PLACEHOLDER = "equal_split_placeholder"
SRC_SCANNED_PDF_EMPTY = "scanned_pdf_empty"

# 应用层上传 size cap（500 MB；nginx 300M < backend 500M 双重保险）
DEFAULT_MAX_UPLOAD_BYTES = 500 * 1024 * 1024

# 流式写盘 chunk size（8KB；内存平稳 + 系统调用次数可控）
DEFAULT_CHUNK_SIZE = 8 * 1024

# pending 临时子目录名（router 写盘路径；A service 完成后会 move 到 {textbook_id}/...）
PENDING_SUBDIR = "pending"


class TextbookUploadError(Exception):
    """教材上传失败（业务层异常；router 转 HTTPException）。

    调用方根据 message 决定 HTTP status（400 / 422 / 500）。
    """


class UploadValidationError(Exception):
    """上传内容校验失败（magic bytes / 文件过小 / 空文件）。

    router 转 HTTPException(400)。
    """


class UploadTooLargeError(Exception):
    """上传超 size cap（默认 500MB）。

    router 转 HTTPException(413)。
    """


def check_magic_bytes(src: BinaryIO) -> bytes:
    """流式读前 5 字节校验 magic；不全量入内存（D-28 第 4 条可证伪）。

    Args:
        src: 二进制输入流（UploadFile.file / SpooledTemporaryFile）

    Returns:
        读到的 magic bytes（调用方要 prepend 到落盘文件）

    Raises:
        UploadValidationError: 文件为空 / 过小 / 非 %PDF- 开头
    """
    chunk = src.read(len(PDF_MAGIC_PREFIX))
    if not chunk:
        raise UploadValidationError("PDF 文件为空")
    if len(chunk) < len(PDF_MAGIC_PREFIX):
        raise UploadValidationError(
            f"文件过小（{len(chunk)} bytes），不是有效 PDF"
        )
    if not chunk.startswith(PDF_MAGIC_PREFIX):
        raise UploadValidationError(
            f"文件不是 PDF（magic bytes 校验失败：开头 {chunk!r}，"
            f"期望以 {PDF_MAGIC_PREFIX!r} 开头）"
        )
    return chunk


def stream_upload_to_disk(
    src: BinaryIO,
    *,
    dst_dir: Path,
    prefix: bytes = b"",
    max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Path:
    """流式把 src 写到 ``dst_dir/pending/{uuid4}.pdf``（带 size cap + 自动清理）。

    Args:
        src: 二进制输入流（magic 已被 check_magic_bytes 消费）
        dst_dir: 落盘根目录（容器内 = /app/data/uploads）
        prefix: 已读 magic bytes（如 b"%PDF-"），写在文件头
        max_bytes: 上限字节数（默认 500MB）
        chunk_size: 每次 read 字节数（默认 8KB）

    Returns:
        落盘文件路径（dst_dir/pending/{uuid4}.pdf）

    Raises:
        UploadTooLargeError: 累计字节数 > max_bytes（关 fp + 删临时文件）
    """
    pending_dir = dst_dir / PENDING_SUBDIR
    pending_dir.mkdir(parents=True, exist_ok=True)
    dst = pending_dir / f"{uuid.uuid4().hex}.pdf"

    bytes_written = 0
    try:
        with open(dst, "wb") as f:
            if prefix:
                f.write(prefix)
                bytes_written += len(prefix)
            while True:
                chunk = src.read(chunk_size)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    raise UploadTooLargeError(
                        f"文件超出 {max_bytes // (1024 * 1024)} MB 上限"
                    )
                f.write(chunk)
    except BaseException:
        # 任何异常都清理临时文件（UploadTooLargeError / OSError / KeyboardInterrupt / ...）
        with contextlib.suppress(OSError):
            dst.unlink(missing_ok=True)
        raise

    logger.info(
        "流式上传落盘：path=%s bytes=%d cap=%d",
        dst,
        bytes_written,
        max_bytes,
    )
    return dst


def _uploads_root() -> Path:
    """读取 UPLOADS_DIR 环境变量，默认 /app/data/uploads。"""
    raw = os.environ.get("UPLOADS_DIR", DEFAULT_UPLOADS_DIR)
    return Path(raw)


def _cleanup_files(
    target_path: Path | None,
    pending_path: Path | None,
) -> None:
    """失败回滚时清理已落盘的文件 + pending 残留。

    Best effort：清失败只 warning，不抛（已在外层 except 中处理）。
    """
    if target_path is not None and target_path.exists():
        try:
            target_path.unlink()
        except OSError as e:  # noqa: BLE001
            logger.warning("清理落盘文件失败 %s: %s", target_path, e)
        else:
            # 如果目录空了，尝试删空目录（不删非空目录）
            parent = target_path.parent
            try:
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
            except OSError:  # noqa: BLE001
                pass
    if pending_path is not None and pending_path.exists() and (
        target_path is None or pending_path != target_path
    ):
        try:
            pending_path.unlink()
        except OSError as e:  # noqa: BLE001
            logger.warning("清理 pending 文件失败 %s: %s", pending_path, e)


def upload_textbook_with_extraction(
    db: Session,
    *,
    file_path: str,
    name: str,
    subject_id: int | None,
    grade_level: Literal["junior_high", "senior_high"] | None,
) -> tuple[Textbook, list[Chapter]]:
    """上传教材 PDF：从 file_path 读 PDF → 解析章节 + 摘要 → 落盘 → 持久化。

    接口约定（与工单 C 共享；A 阶段最终固定）：
    - 接收 ``file_path: str`` 而非 ``pdf_bytes: bytes``
    - router / 调用方先把 UploadFile 字节写到 ``/app/data/uploads/pending/{uuid}.pdf``
    - service 解析 + 落盘到 ``uploads/{textbook_id}/{filename}.pdf`` + DB 持久化
    - 失败回滚：删 pending + target + DB rollback

    Args:
        db: SQLAlchemy Session（调用方控制事务；本函数内 commit）
        file_path: 已落地的 PDF 文件路径（router 写到 pending/）
        name: 教材名称
        subject_id: 学科 ID（可空）
        grade_level: 学段（"junior_high" / "senior_high"，可空）

    Returns:
        (Textbook 实例, Chapter 列表) — 都已 refresh，含 id / created_at / file_path

    Raises:
        TextbookUploadError: 校验失败 / 抽取失败 / DB 写入失败 / 落盘失败
    """
    pending_path = Path(file_path)
    target_path: Path | None = None  # 落盘目标，失败时回滚
    textbook: Textbook | None = None
    chapters: list[Chapter] = []

    try:
        # ───────── 1. magic bytes 校验（全量读 5 字节；C 工地可能改流式） ─────────
        if not pending_path.exists():
            raise TextbookUploadError(f"PDF 文件不存在: {file_path}")
        if not pending_path.is_file():
            raise TextbookUploadError(f"PDF 路径不是文件: {file_path}")
        try:
            with open(pending_path, "rb") as f:
                head = f.read(len(PDF_MAGIC_PREFIX))
        except OSError as e:  # noqa: BLE001
            raise TextbookUploadError(f"PDF 文件读取失败：{e}") from e
        if len(head) < len(PDF_MAGIC_PREFIX):
            raise TextbookUploadError(
                f"文件过小（{len(head)} bytes），不是有效 PDF"
            )
        if not head.startswith(PDF_MAGIC_PREFIX):
            raise TextbookUploadError(
                f"文件不是 PDF（magic bytes 校验失败：开头 {head!r}，"
                f"期望以 {PDF_MAGIC_PREFIX!r} 开头）"
            )

        # ───────── 2. 解析章节结构（带回 extraction_source） ─────────
        extractor = PDFExtractor()
        try:
            structure: ChapterStructureResult = (
                extractor.extract_chapter_structure_with_source(str(pending_path))
            )
        except (FileNotFoundError, ValueError, RuntimeError) as e:
            raise TextbookUploadError(f"PDF 解析失败：{e}") from e
        if not structure.chapters:
            raise TextbookUploadError("PDF 解析未识别到任何章节（文档可能损坏或为空）")
        chapters_struct = structure.chapters
        chapter_extraction_source = structure.extraction_source

        # ───────── 3. 抽取每章正文 → content_summary ─────────
        # 多章节用 '\n\n---\n\n' 拼接（M1+ UI 拆分）；但目前每个 Chapter 行存
        # 一段单章的 content_summary，拼接是 router 渲染的事（v0.5 §4.2）。
        # 这里仍然单章存；判定文本为空 → content_summary=None + extraction_source='scanned_pdf_empty'
        per_chapter_summary: list[str | None] = []
        per_chapter_source: list[str] = []
        for cs in chapters_struct:
            try:
                pages = extractor.extract_pages(
                    str(pending_path), cs.page_range
                )
            except (ValueError, RuntimeError) as e:
                raise TextbookUploadError(
                    f"章节 {cs.chapter_number} 正文抽取失败：{e}"
                ) from e
            text = "\n".join(p.text for p in pages).strip()
            if not text:
                per_chapter_summary.append(None)
                per_chapter_source.append(SRC_SCANNED_PDF_EMPTY)
            else:
                per_chapter_summary.append(text)
                per_chapter_source.append(chapter_extraction_source)

        # ───────── 4. 解析 grade_level ─────────
        gl_value: GradeLevel | None = None
        if grade_level is not None:
            try:
                gl_value = GradeLevel(grade_level)
            except ValueError as e:
                raise TextbookUploadError(f"非法 grade_level: {grade_level}") from e

        # ───────── 5. 持久化 Textbook（占位 file_path）+ flush 取 ID ─────────
        textbook = Textbook(
            name=name,
            file_path=str(pending_path),  # 临时占位；flush 后会被覆盖
            subject_id=subject_id,
            grade_level=gl_value,
        )
        db.add(textbook)
        db.flush()  # 触发 INSERT 但不 commit；拿 textbook.id

        # ───────── 6. 落盘：pending → uploads/{textbook_id}/{filename}.pdf ─────────
        uploads_root = _uploads_root()
        target_dir = uploads_root / str(textbook.id)
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:  # noqa: BLE001
            raise TextbookUploadError(f"创建 uploads 目录失败 {target_dir}：{e}") from e

        original_name = pending_path.name
        target_path = target_dir / original_name
        if target_path.exists():
            # 极少见；同名加 _N 后缀
            stem = pending_path.stem
            suffix = pending_path.suffix
            i = 1
            while True:
                candidate = target_dir / f"{stem}_{i}{suffix}"
                if not candidate.exists():
                    target_path = candidate
                    break
                i += 1

        try:
            shutil.move(str(pending_path), str(target_path))
        except OSError as e:  # noqa: BLE001
            raise TextbookUploadError(f"PDF 落盘失败：{e}") from e

        # ───────── 7. 更新 file_path + 写入 Chapter 行 ─────────
        textbook.file_path = (
            f"uploads/{textbook.id}/{target_path.name}"  # 相对路径入 DB
        )

        for cs, summary, src in zip(
            chapters_struct, per_chapter_summary, per_chapter_source, strict=True
        ):
            ch = Chapter(
                textbook_id=textbook.id,
                chapter_number=cs.chapter_number,
                title=cs.title,
                content_summary=summary,
                page_range_start=cs.page_range[0],
                page_range_end=cs.page_range[1],
                extraction_source=src,
            )
            db.add(ch)
            chapters.append(ch)

        try:
            db.commit()
        except Exception as e:  # noqa: BLE001
            db.rollback()
            raise TextbookUploadError(f"DB 写入失败：{e}") from e

        # ───────── 8. refresh 拿到 created_at + id ─────────
        db.refresh(textbook)
        for ch in chapters:
            db.refresh(ch)

        logger.info(
            "教材上传成功：textbook_id=%s name=%s chapters=%d file=%s",
            textbook.id,
            name,
            len(chapters),
            textbook.file_path,
        )
        # 标记：target_path 已是真 artifact，失败回滚不应再清（path 重赋值 None，避免清理已落盘文件）
        target_path = None
        pending_path = None
        return textbook, chapters

    except TextbookUploadError:
        db.rollback()
        _cleanup_files(target_path, pending_path)
        raise
    except Exception as e:  # noqa: BLE001
        db.rollback()
        _cleanup_files(target_path, pending_path)
        logger.exception("教材上传意外失败: name=%s", name)
        raise TextbookUploadError(f"教材上传失败：{e}") from e