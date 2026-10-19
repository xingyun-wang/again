"""M3-D2-W5: PDF 嵌图测试（per plans/M3-D2-W5-PDF-image-brief.md §4）。

4 case 必全过（per D-43-X = 对象级证据 + 防恒真门槛）：

| #  | 场景                                      | 期望                                          |
|----|-------------------------------------------|-----------------------------------------------|
| T1 | service 单测：1 题带图 PDF                | image XObject ≥ 1（pymupdf 验证）             |
| T2 | service 单测：无图题 PDF（对照）          | image XObject == 0（pymupdf 验证）            |
| T3 | service 单测：image 文件丢失 / 损坏       | PDF 仍生成 + 含 fallback "（图片加载失败）"   |
| T4 | 端到端：API POST /export 含图 PDF          | 200 + application/pdf + image XObject ≥ 1    |

设计要点（per brief §3 + §4 必报项）：
- **不装 Pillow**（用 reportlab 自带 `platypus.Image`；requirements.txt 已有）
- 嵌图位置：题目 stem 之后、choices 之前（brief §3 拍板）
- 异常处理：image 加载失败 = 渲染 fallback "（图片加载失败）" + logger.warning（**不静默**）
- 默认宽 200pt；高度由 reportlab 按宽高比自动计算
- 测试最小有效 PNG = 动态生成（stdlib zlib + struct；不依赖硬编码 hex / 不装 Pillow）
- 测试库 = 显式 -e DATABASE_URL=postgresql+psycopg://...tiered_homework_test
  （per §治理.19；不污染 dev 库）

测试基础设施（per B11）：
- 复用 test_assignment_review.py 的 mock_db_session / mock_user_system_seed / mock_textbook / mock_subject
- 复用 _s4_helpers.make_test_client（TestClient + dependency_overrides[get_db]）
- 复刻 S4 _create_assignment_approved 模式但**不走 API**：直接 ORM 建 Assignment +
  AssignmentItem，review_status=APPROVED；避免依赖 question_generator 抽题逻辑
"""

from __future__ import annotations

import io
import struct
import zlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy.orm import Session

from app.models import (
    Assignment,
    AssignmentItem,
    Chapter,
    KnowledgeReviewStatus,
    Question,
    QuestionDifficulty,
    QuestionType,
)
from app.models.academic import (
    DesensitizationStatus,
    QuestionImage,
    QuestionImageSource,
)
from app.services.assignment_export import render_assignment_pdf
from tests.api.v1._s4_helpers import make_test_client  # reuse S4 TestClient factory

if TYPE_CHECKING:
    pass


# ────────────────── minimal PNG 生成（stdlib only；不装 Pillow）────────────────


def _make_minimal_png(width: int = 4, height: int = 4) -> bytes:
    """生成最小有效 PNG（全透明 RGBA，stdlib only）。

    reportlab.platypus.Image + reportlab.lib.utils.ImageReader 接受此格式。
    用 zlib + struct + crc32（stdlib 全套），不依赖 Pillow / reportlab.graphics。

    Args:
        width: 图像宽度（px）
        height: 图像高度（px）

    Returns:
        完整 PNG 字节流（含 PNG 8 字节签名 + IHDR + IDAT + IEND）
    """
    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return length + chunk_type + data + struct.pack(">I", crc)

    sig = b"\x89PNG\r\n\x1a\n"  # PNG 8 字节签名
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    # IDAT: 每行 1 字节 filter (0) + width * 4 字节 RGBA（全 0 = 全透明）
    raw = b""
    for _ in range(height):
        raw += b"\x00" + b"\x00\x00\x00\x00" * width
    idat = _chunk(b"IDAT", zlib.compress(raw))
    iend = _chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _count_pdf_image_xobjects(pdf_bytes: bytes) -> tuple[int, int]:
    """用 pymupdf 解析 PDF，统计 image XObject 总数 + PDF 字节大小。

    Args:
        pdf_bytes: PDF 字节流

    Returns:
        (image_xobject_count, pdf_byte_size) — (D-43-X §5 必报 = 对象级证据)
    """
    import pymupdf  # lazy import: 测试库隔离 per §治理.19

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        count = 0
        for page in doc:
            # full=True → 包含 XObject 引用（包括 Form / Image）
            for _img in page.get_images(full=True):
                count += 1
    finally:
        doc.close()
    return count, len(pdf_bytes)


# ────────────────── fixture：chapter + question + QuestionImage ─────────────────


@pytest.fixture()
def chapter_with_image_question(
    mock_db_session: Session,
    mock_user_system_seed: Any,
    mock_textbook: Any,
    tmp_path: Path,
) -> tuple[Chapter, Question, QuestionImage]:
    """1 chapter + 1 question (D 档) + 1 QuestionImage（4x4 透明 PNG）。

    image 文件落到 tmp_path（pytest 自动清理）；storage_path 指 tmp_path 下的文件。
    """
    ch = Chapter(
        textbook_id=mock_textbook.id,
        owner_user_id=mock_user_system_seed.id,
        chapter_number=1,
        title="W5-image-test-chapter",
        content_summary="W5 嵌图测试章节（看图回答问题）",
        extraction_source="detected",
    )
    mock_db_session.add(ch)
    mock_db_session.flush()

    q = Question(
        owner_user_id=mock_user_system_seed.id,
        chapter_id=ch.id,
        content="看图回答下列问题（这是一道带图的 D 档题）",
        difficulty=QuestionDifficulty.D,
        type=QuestionType.CHOICE,
    )
    mock_db_session.add(q)
    mock_db_session.flush()

    # 写 4x4 透明 PNG 到 tmp_path
    png_path = tmp_path / "w5_test_image.png"
    png_path.write_bytes(_make_minimal_png(4, 4))

    img = QuestionImage(
        question_id=q.id,
        order_index=0,
        file_ext="png",
        storage_path=str(png_path),
        source=QuestionImageSource.SELF_BUILT,
        desensitization_status=DesensitizationStatus.DONE,
        uploaded_by_user_id=mock_user_system_seed.id,
    )
    mock_db_session.add(img)
    mock_db_session.commit()
    mock_db_session.refresh(ch)
    mock_db_session.refresh(q)
    mock_db_session.refresh(img)
    return ch, q, img


@pytest.fixture()
def chapter_without_image(
    mock_db_session: Session,
    mock_user_system_seed: Any,
    mock_textbook: Any,
) -> tuple[Chapter, Question]:
    """1 chapter + 1 question (D 档) **无图** — T2 对照组。"""
    ch = Chapter(
        textbook_id=mock_textbook.id,
        owner_user_id=mock_user_system_seed.id,
        chapter_number=2,
        title="W5-noimage-test-chapter",
        content_summary="W5 无图对照测试章节",
        extraction_source="detected",
    )
    mock_db_session.add(ch)
    mock_db_session.flush()

    q = Question(
        owner_user_id=mock_user_system_seed.id,
        chapter_id=ch.id,
        content="这是一道无图的 D 档题（对照组）",
        difficulty=QuestionDifficulty.D,
        type=QuestionType.CHOICE,
    )
    mock_db_session.add(q)
    mock_db_session.commit()
    mock_db_session.refresh(ch)
    mock_db_session.refresh(q)
    return ch, q


@pytest.fixture()
def chapter_with_missing_image(
    mock_db_session: Session,
    mock_user_system_seed: Any,
    mock_textbook: Any,
) -> tuple[Chapter, Question, QuestionImage]:
    """1 chapter + 1 question + 1 QuestionImage **文件不存在** — T3 fallback 验证。"""
    ch = Chapter(
        textbook_id=mock_textbook.id,
        owner_user_id=mock_user_system_seed.id,
        chapter_number=3,
        title="W5-missing-image-test-chapter",
        content_summary="W5 图片丢失 fallback 测试",
        extraction_source="detected",
    )
    mock_db_session.add(ch)
    mock_db_session.flush()

    q = Question(
        owner_user_id=mock_user_system_seed.id,
        chapter_id=ch.id,
        content="图片丢失题（应触发 fallback）",
        difficulty=QuestionDifficulty.D,
        type=QuestionType.CHOICE,
    )
    mock_db_session.add(q)
    mock_db_session.flush()

    img = QuestionImage(
        question_id=q.id,
        order_index=0,
        file_ext="png",
        storage_path="/nonexistent/path/to/missing_image.png",  # 故意不存在
        source=QuestionImageSource.SELF_BUILT,
        desensitization_status=DesensitizationStatus.DONE,
        uploaded_by_user_id=mock_user_system_seed.id,
    )
    mock_db_session.add(img)
    mock_db_session.commit()
    mock_db_session.refresh(ch)
    mock_db_session.refresh(q)
    mock_db_session.refresh(img)
    return ch, q, img


# ────────────────── helper：直接 ORM 建 APPROVED Assignment + Item ─────────────────


def _build_approved_assignment(
    mock_db_session: Session,
    chapter: Chapter,
    question: Question,
    notes: str = "W5 image test (APPROVED)",
) -> int:
    """直接 ORM 建 APPROVED Assignment + 1 AssignmentItem（不走 question_generator）。

    Args:
        mock_db_session: 测试 DB session
        chapter: 章节 ORM
        question: 题目 ORM
        notes: 审阅备注

    Returns:
        assignment.id
    """
    a = Assignment(
        owner_user_id=question.owner_user_id,
        chapter_id=chapter.id,
        tier=QuestionDifficulty.D,
        total_count=1,
        d_count=1,
        c_count=0,
        b_count=0,
        a_count=0,
        review_status=KnowledgeReviewStatus.APPROVED,
        reviewed_by=question.owner_user_id,
        review_notes=notes,
        seed=1,
    )
    mock_db_session.add(a)
    mock_db_session.flush()

    item = AssignmentItem(
        assignment_id=a.id,
        question_id=question.id,
        position=0,
        tier_origin=QuestionDifficulty.D,
    )
    mock_db_session.add(item)
    mock_db_session.commit()
    mock_db_session.refresh(a)
    return a.id


# ────────────────── T1: service 单测 — 1 题带图 PDF 含 image XObject ≥ 1 ─────────────────


def test_render_pdf_with_image_has_image_xobject(
    mock_db_session: Session,
    chapter_with_image_question: tuple[Chapter, Question, QuestionImage],
) -> None:
    """T1: 1 题带图 PDF 应含 image XObject ≥ 1（per brief §4.5 = pymupdf 验证）。

    防恒假门槛（per D-43-X §5）：
    - 预检 render_assignment_pdf 返 bytes + 头 4 字节 = %PDF
    - 预检 image XObject 数 ≥ 1（**对象级证据** = D-43-X 拒收"已支持"字样）
    - 预检 PDF 字节大小 > 1024（与 S4 test_render_assignment_pdf_unit 一致）
    """
    ch, q, _img = chapter_with_image_question
    aid = _build_approved_assignment(mock_db_session, ch, q)
    a = mock_db_session.get(Assignment, aid)
    assert a is not None, "fixture failure: assignment not persisted"

    pdf_bytes = render_assignment_pdf(a)

    # 预检 1: PDF 头
    assert pdf_bytes[:4] == b"%PDF", f"PDF 头校验失败: {pdf_bytes[:4]!r}"
    # 预检 2: PDF 长度
    assert len(pdf_bytes) > 1024, f"PDF 字节大小异常: {len(pdf_bytes)}"

    # 预检 3: pymupdf image XObject ≥ 1（**对象级证据**）
    image_count, pdf_size = _count_pdf_image_xobjects(pdf_bytes)
    assert image_count >= 1, (
        f"带图 PDF 应含 image XObject ≥ 1，实际 {image_count}（"
        f"PDF size={pdf_size} 字节）"
    )


# ────────────────── T2: service 单测 — 无图 PDF 含 image XObject == 0（对照） ─────────────────


def test_render_pdf_without_image_has_zero_xobject(
    mock_db_session: Session,
    chapter_without_image: tuple[Chapter, Question],
) -> None:
    """T2: 无图 PDF 应含 image XObject == 0（**对照** = 防 T1 假红恒真）。

    防恒真门槛（per D-28 家族）：
    - 预检 render_assignment_pdf 返 bytes + 头 4 字节 = %PDF
    - 预检 image XObject 数 == 0（**证明 T1 不是恒真**）
    - 预检 PDF 字节大小 > 1024
    """
    ch, q = chapter_without_image
    aid = _build_approved_assignment(mock_db_session, ch, q)
    a = mock_db_session.get(Assignment, aid)
    assert a is not None, "fixture failure: assignment not persisted"

    pdf_bytes = render_assignment_pdf(a)

    # 预检 1: PDF 头
    assert pdf_bytes[:4] == b"%PDF", f"PDF 头校验失败: {pdf_bytes[:4]!r}"
    # 预检 2: PDF 长度
    assert len(pdf_bytes) > 1024, f"PDF 字节大小异常: {len(pdf_bytes)}"

    # 预检 3: pymupdf image XObject == 0（**对照** = T1 防恒真）
    image_count, pdf_size = _count_pdf_image_xobjects(pdf_bytes)
    assert image_count == 0, (
        f"无图 PDF 应含 image XObject == 0，实际 {image_count}（"
        f"PDF size={pdf_size} 字节）"
    )


# ────────────────── T3: service 单测 — image 文件丢失 fallback ─────────────────


def test_render_pdf_with_missing_image_file(
    mock_db_session: Session,
    chapter_with_missing_image: tuple[Chapter, Question, QuestionImage],
) -> None:
    """T3: image 文件丢失时，PDF 仍生成 + 含 fallback "（图片加载失败）"。

    异常处理（per brief §3 "不静默" + §4 必报项）：
    - 不抛异常（service 不崩）
    - PDF 头正常 + 长度 > 1024
    - 文本含 fallback "（图片加载失败）"（用 pdfplumber 提取文本验证）
    """
    ch, q, _img = chapter_with_missing_image
    aid = _build_approved_assignment(mock_db_session, ch, q)
    a = mock_db_session.get(Assignment, aid)
    assert a is not None, "fixture failure: assignment not persisted"

    # render_assignment_pdf 不应抛 — 异常在 _render_question_image 内部处理
    pdf_bytes = render_assignment_pdf(a)

    # 预检 1: PDF 头
    assert pdf_bytes[:4] == b"%PDF", f"PDF 头校验失败: {pdf_bytes[:4]!r}"
    # 预检 2: PDF 长度
    assert len(pdf_bytes) > 1024, f"PDF 字节大小异常: {len(pdf_bytes)}"

    # 预检 3: 文本含 fallback 文字（**不静默** = 用户可见）
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "".join(p.extract_text() or "" for p in pdf.pages)
    assert "图片加载失败" in text, (
        f"图片丢失 fallback 文字应出现，实际 PDF 文本片段：{text[:200]!r}"
    )


# ────────────────── T4: 端到端 — API POST /export 含图 PDF 走通 ─────────────────


def test_export_endpoint_with_image(
    mock_db_session: Session,
    chapter_with_image_question: tuple[Chapter, Question, QuestionImage],
) -> None:
    """T4: API POST /api/v1/assignments/{id}/export 端到端含图 PDF。

    端到端验证（per brief §4 必报项 = 真值证据）：
    - 200 + content-type=application/pdf + 头 4 字节 = %PDF
    - pymupdf 验证 image XObject ≥ 1
    - PDF 字节大小 > 1024（与 S4 一致）
    """
    ch, q, _img = chapter_with_image_question
    aid = _build_approved_assignment(mock_db_session, ch, q)

    # 建 TestClient（复用 S4 _s4_helpers.make_test_client 模式）
    client = make_test_client(mock_db_session)

    r = client.post(
        f"/api/v1/assignments/{aid}/export",
        headers={"X-User-Id": "1"},
    )

    # 预检 1: 200 + content-type + PDF 头
    assert r.status_code == 200, (
        f"端到端导出应 200，实际 {r.status_code}：{r.text}"
    )
    assert r.headers["content-type"] == "application/pdf", (
        f"content-type 应 application/pdf，实际 {r.headers.get('content-type')!r}"
    )
    assert r.content[:4] == b"%PDF", f"PDF 头校验失败: {r.content[:4]!r}"
    assert len(r.content) > 1024, f"PDF 字节大小异常: {len(r.content)}"

    # 预检 2: image XObject ≥ 1（**端到端对象级证据**）
    image_count, pdf_size = _count_pdf_image_xobjects(r.content)
    assert image_count >= 1, (
        f"端到端 PDF 应含 image XObject ≥ 1，实际 {image_count}（"
        f"PDF size={pdf_size} 字节）"
    )
