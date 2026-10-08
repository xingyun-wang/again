"""TWAIN HTTP 桥 mock router（M2 S0-4：D-M2-4 拍板 + 3 补丁 A/B/C）。

职责：
- 实现 ``POST /scan/omr`` 抽象层（v0.5 §6.4.1 三层架构的容器侧入口）
- Linux 容器侧 = 只走本 HTTP 桥（不调 TWAIN DSM；v0.5 §6.4.1 强约束）
- mock 阶段 = 返回 deterministic 答案（不连真扫描仪）
- M3 替换本 router 为"转发到 Windows 宿主机 TWAIN DSM 服务"的真 HTTP 桥实现时，
  接口契约（路径 / 请求 / 响应 schema）零返工

设计要点：
- 路径与文件操作走 ``UPLOAD_ROOT`` 环境变量（默认 ``/app/data/uploads``）——
  既有配置 ``backend/app/services/textbook_upload.py:58``（``DEFAULT_UPLOADS_DIR``）
- 不写 ``backend/uploads/images/...``（D-43-X 失实，已修）
- 桥的职责 = 「图像 → 填涂位」；不包含出题侧概念（档位 / 题目索引等）
- 响应只回 scan_id（不暴露内部目录结构 file_path）
- deterministic：seed = chapter_id → 同样输入 = 同样输出
- mock 阶段不做真 OMR 解析（M3 范围）；只做 magic bytes peek + size cap + 流式落盘

接口契约（稳定 = M3 替换零返工）：
- 路径：``POST /api/v1/twain/scan/omr``
- 请求：multipart/form-data
    - ``file``: UploadFile（PDF / 图片）
    - ``chapter_id``: str（form，必填，1-128 字符）
    - ``question_count``: int（form，必填，5-200）
- 响应：``ScanOMRResponse``（JSON）
    - ``answers``: list[str | None]，长度 = question_count；前 5 个位置为 A/B/C/D 之一
    - ``metadata``: dict（含 bridge_layer / chapter_id / question_count /
      detected_count / scan_id / file_size / content_type / magic_kind / timestamp）

错误码：
- 400：文件为空 / 流读取失败
- 413：文件超 size cap（默认 50MB）
- 422：Form 字段校验失败（缺字段 / 类型错 / chapter_id 越界 / question_count 越界）
"""

from __future__ import annotations

import contextlib
import logging
import os
import random
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.api.v1.schemas.twain import (
    ANSWER_CHOICES,
    BRIDGE_LAYER_MOCK,
    MAX_QUESTION_COUNT,
    MIN_QUESTION_COUNT,
    MOCK_DETECTED_POSITIONS,
    ScanOMRResponse,
)
from app.services.textbook_upload import DEFAULT_UPLOADS_DIR

logger = logging.getLogger(__name__)

router = APIRouter()

# 落盘根目录：环境变量 UPLOAD_ROOT 覆盖，默认 /app/data/uploads。
# 与 academic.py:103 / textbook_upload.py:58 既有约定一致。
UPLOAD_ROOT: Path = Path(os.environ.get("UPLOAD_ROOT", DEFAULT_UPLOADS_DIR))

# mock 阶段 OMR 扫描文件 size cap（50MB；单张答题卡扫描件合理上限）
DEFAULT_SCAN_MAX_BYTES: int = 50 * 1024 * 1024
MAX_SCAN_BYTES: int = int(os.environ.get("TWAIN_SCAN_MAX_BYTES", str(DEFAULT_SCAN_MAX_BYTES)))

# 流式落盘 chunk size（8KB；与 textbook_upload 一致）
SCAN_CHUNK_SIZE: int = 8 * 1024

# 扫描件保存子目录（UPLOAD_ROOT/scans/）
SCANS_SUBDIR = "scans"

# 允许的 content type（MIME 大类；具体后缀由 filename 决定）
ALLOWED_CONTENT_TYPE_PREFIXES: tuple[str, ...] = (
    "application/pdf",
    "image/",
)

# PDF magic bytes（与 textbook_upload.py 一致）
PDF_MAGIC_PREFIX = b"%PDF-"


# ──────────────────────────── Mock 答案生成 ────────────────────────────


def _generate_mock_answers(
    chapter_id: str,
    question_count: int,
) -> list[str | None]:
    """根据 chapter_id deterministic 生成 mock 答案列表。

    契约（决策书 §7.3 补丁 A + 任务 brief）：
    - 长度 = question_count
    - 前 5 个位置（``MOCK_DETECTED_POSITIONS`` = (0,1,2,3,4)）填涂；其余 None
    - 答案字母 A/B/C/D（与 OMR 答题卡 4 选项对齐）
    - 同 chapter_id → 同输出（pytest 跑稳定）

    Args:
        chapter_id: 章节 ID（form 字段；非空即可）
        question_count: 总题数（>= 5）

    Returns:
        长度 = question_count 的答案列表；前 5 个位置为 'A'/'B'/'C'/'D'，其余 None
    """
    # seed：chapter_id → 同输入同输出
    rng = random.Random(chapter_id)

    answers: list[str | None] = [None] * question_count
    for pos in MOCK_DETECTED_POSITIONS:
        if pos < question_count:
            answers[pos] = rng.choice(ANSWER_CHOICES)
    return answers


# ──────────────────────────── 文件落盘 ────────────────────────────


def _resolve_extension(file: UploadFile) -> str:
    """从 filename / content_type 推断保存扩展名；空则回退 .bin。"""
    if file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext and len(ext) <= 8 and all(c.isalnum() or c == "." for c in ext):
            return ext
    ct = (file.content_type or "").lower()
    if ct == "application/pdf":
        return ".pdf"
    if ct.startswith("image/jpeg") or ct.startswith("image/jpg"):
        return ".jpg"
    if ct.startswith("image/png"):
        return ".png"
    if ct.startswith("image/"):
        return ".img"
    return ".bin"


def _save_scan_file(file: UploadFile, upload_root: Path) -> tuple[Path, int, str, str]:
    """流式保存扫描件到 ``{upload_root}/scans/{file_id}{ext}``。

    流程：
    1. peek magic bytes（PDF 校验；非 PDF 图片直接放行）
    2. 流式写盘 + size cap（超限清理临时文件 + 抛 413）
    3. 关 UploadFile 释放 spooled temp

    Args:
        file: FastAPI UploadFile
        upload_root: 落盘根目录（UPLOAD_ROOT）

    Returns:
        (saved_path, bytes_written, magic_kind, file_id)
        magic_kind: "pdf" / "image" / "unknown"
        file_id: 32 字符 hex（uuid4）；scan_id = file_id（响应不暴露 saved_path）

    Raises:
        HTTPException 400: 文件为空 / 流读取失败
        HTTPException 413: 超过 size cap
    """
    scans_dir = upload_root / SCANS_SUBDIR
    scans_dir.mkdir(parents=True, exist_ok=True)

    ext = _resolve_extension(file)
    file_id = uuid.uuid4().hex
    dst = scans_dir / f"{file_id}{ext}"

    bytes_written = 0
    magic_kind = "unknown"
    try:
        with open(dst, "wb") as f:
            # peek 前 5 字节判 magic（仅用于标注 metadata；非 PDF 放行）
            head = file.file.read(len(PDF_MAGIC_PREFIX))
            if head.startswith(PDF_MAGIC_PREFIX):
                magic_kind = "pdf"
                f.write(head)
                bytes_written += len(head)
            elif head:
                magic_kind = "image" if ext != ".bin" else "unknown"
                # 非 PDF：head 也要写回（图片文件头是有效内容）
                f.write(head)
                bytes_written += len(head)
            else:
                raise HTTPException(status_code=400, detail="扫描文件为空")

            # 流式续写
            while True:
                chunk = file.file.read(SCAN_CHUNK_SIZE)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > MAX_SCAN_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"扫描文件超出 {MAX_SCAN_BYTES // (1024 * 1024)} MB 上限"
                        ),
                    )
                f.write(chunk)
    except HTTPException:
        # 清理已落盘文件（413 / 400）
        with contextlib.suppress(OSError):
            dst.unlink(missing_ok=True)
        raise
    except Exception as e:  # noqa: BLE001
        # 兜底：任何 IO 异常都清理 + 抛 400
        logger.exception("扫描文件落盘失败: filename=%s", file.filename)
        with contextlib.suppress(OSError):
            dst.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"扫描文件读取失败：{e}") from e
    finally:
        # 关 UploadFile（释放 spooled temp / 真实文件 fd）
        with contextlib.suppress(OSError):
            file.file.close()

    logger.info(
        "扫描件流式落盘：path=%s bytes=%d cap=%d magic=%s",
        dst,
        bytes_written,
        MAX_SCAN_BYTES,
        magic_kind,
    )
    return dst, bytes_written, magic_kind, file_id


# ──────────────────────────── 端点 ────────────────────────────


@router.post(
    "/scan/omr",
    response_model=ScanOMRResponse,
    status_code=status.HTTP_200_OK,
    summary=(
        "OMR 答题卡扫描（M2 S0-4 mock；v0.5 §6.4.1 HTTP 桥抽象层；"
        "M3 替换为真 Windows 宿主机 TWAIN DSM 桥接时接口契约零返工）"
    ),
    tags=["twain"],
)
def scan_omr(
    file: Annotated[
        UploadFile,
        File(description="答题卡扫描件（PDF 或图片；multipart/form-data）"),
    ],
    chapter_id: Annotated[
        str,
        Form(min_length=1, max_length=128, description="章节 ID（1-128 字符）"),
    ],
    question_count: Annotated[
        int,
        Form(ge=MIN_QUESTION_COUNT, le=MAX_QUESTION_COUNT, description="题数（5-200）"),
    ],
) -> ScanOMRResponse:
    """HTTP 桥抽象层入口（mock 阶段）。

    流程：
    1. 校验 Form 字段（FastAPI 自动：chapter_id 长度 / question_count 范围）
    2. 流式落盘扫描件到 ``{UPLOAD_ROOT}/scans/{file_id}{ext}``（带 size cap）
    3. deterministic 生成 mock 答案（按 chapter_id seed；前 5 位置填涂）
    4. 构造响应（answers + metadata 含 bridge_layer + scan_id）

    M3 替换计划：
    - 替换本函数体为"转发 multipart 到 Windows 宿主机 TWAIN DSM HTTP 桥"即可
    - 接口契约（路径 / Form 字段 / 响应 schema）零返工
    - bridge_layer metadata 字段从 "http_bridge_mock" 改为 "http_bridge_windows_host"
    - scan_id 由 TWAIN DSM 服务返回（mock 阶段 = 本地生成 uuid）
    """
    # 1. 落盘（带 magic peek + size cap）
    saved_path, bytes_written, magic_kind, file_id = _save_scan_file(file, UPLOAD_ROOT)

    # 2. deterministic mock 答案
    answers = _generate_mock_answers(chapter_id, question_count)
    detected_count = sum(1 for a in answers if a is not None)

    # 3. 响应 metadata（不暴露 file_path；只回 scan_id）
    metadata: dict[str, object] = {
        "bridge_layer": BRIDGE_LAYER_MOCK,
        "chapter_id": chapter_id,
        "question_count": question_count,
        "detected_count": detected_count,
        "scan_id": file_id,
        "file_size": bytes_written,
        "content_type": file.content_type or "application/octet-stream",
        "magic_kind": magic_kind,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    logger.info(
        "OMR mock 扫描完成：chapter_id=%s question_count=%d "
        "detected_count=%d scan_id=%s bridge=%s",
        chapter_id,
        question_count,
        detected_count,
        file_id,
        BRIDGE_LAYER_MOCK,
    )

    return ScanOMRResponse(answers=answers, metadata=metadata)
