"""教材上传真 PDF 测试（M1-B B.3.1：v0.5 §9.1 PDF 抽取 + §10 M1 端到端）。

覆盖：
1. 上传真 PDF（fixture = `materials/textbooks/选择性必修1.pdf`）→ 解析出 ≥ 3 章节 + 持久化
2. 上传非 PDF → 400 + 友好错误
3. 上传空文件 → 400
4. 上传后 DB 中 Textbook + Chapter 行可见

实现要点：
- 真 PDF 路径 fixture（指向 materials/textbooks/选择性必修1.pdf），
  跳过 if 文件不存在（CI 环境可能没 materials 目录）
- 同步测试用 SQLite in-memory（mock_db_session fixture from conftest）
- 真 PDF 测试中 PyMuPDF 扫描耗时 < 5s（35M PDF + PyMuPDF 主路径）
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.main import create_app as build_app

# 项目根 = backend/ 的上一级（含 materials/ 目录）
BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
REAL_PDF_PATH = PROJECT_ROOT / "materials" / "textbooks" / "选择性必修1.pdf"


def _build_test_client(
    db_session: Any,
    llm_provider: Any,
) -> TestClient:
    """构造带 DB + LLM 依赖 override 的 TestClient。"""
    from app.api.v1.routers.academic import get_llm_dep
    from app.db.session import get_db

    app = build_app()

    def _override_get_db():  # generator function（def + yield）
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_llm_dep] = lambda: llm_provider
    return TestClient(app)


# ─────────────────────── 1. 真 PDF 上传 + 章节抽取 ───────────────────────


def test_upload_real_pdf_extracts_chapters(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """上传真 PDF（人教版地理选择性必修1）→ 抽取 ≥ 3 章节 + 持久化 Textbook。

    跳过条件：materials/textbooks/选择性必修1.pdf 不存在（CI 简化环境）。
    验证：
    - 响应 201
    - 至少 3 个 chapter（PDF 章节识别走 PyMuPDF 主路径 + pdfplumber fallback + 等分 last-resort；
      真 PDF 教材按 v0.5 §5.3.2 应有 5 章；至少 3 章是 §7.6 验收门槛）
    - 每章节含 page_range（start + end 都是 1-based 正整数）
    - M2 工单 A：每章节 extraction_source == 'detected'（真 PDF 走主路径）
    - content_summary 非空（从该章节页范围抽出）
    """
    if not REAL_PDF_PATH.exists():
        import pytest

        pytest.skip(f"真 PDF 不存在：{REAL_PDF_PATH}（CI 环境跳过）")

    client = _build_test_client(mock_db_session, mock_llm_provider)
    pdf_bytes = REAL_PDF_PATH.read_bytes()
    assert pdf_bytes.startswith(b"%PDF-"), "fixture 必须是 PDF"

    resp = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("选择性必修1.pdf", pdf_bytes, "application/pdf")},
        data={
            "name": "人教版地理选择性必修1",
            "grade_level": "senior_high",
        },
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()

    # textbook 元数据
    assert data["textbook_id"] >= 1
    assert data["name"] == "人教版地理选择性必修1"
    assert data["grade_level"] == "senior_high"

    # 章节结构
    chapters = data["chapters"]
    assert len(chapters) >= 3, f"应识别 ≥ 3 章，实际 {len(chapters)} 章：{[c['title'] for c in chapters]}"

    # 每章节 page_range 合法
    for ch in chapters:
        assert ch["chapter_number"] >= 1
        assert ch["page_range_start"] is not None and ch["page_range_start"] >= 1
        assert ch["page_range_end"] is not None and ch["page_range_end"] >= ch["page_range_start"]
        assert ch["has_extracted"] is False  # 新建章节未抽取
        # M2 工单 A：真 PDF 主路径应返 detected
        assert ch["extraction_source"] == "detected", (
            f"真 PDF 主路径应返 detected，实际 {ch['extraction_source']!r}"
            f"（chapter {ch['chapter_number']} {ch['title']!r}）"
        )

    # chapter_number 单调（升序）
    nums = [ch["chapter_number"] for ch in chapters]
    assert nums == sorted(nums), f"chapter_number 应升序：{nums}"

    # M2 工单 A：DB 中 Chapter.content_summary 非空（链接真实性 P0-1 修复证据）
    from app.models import Chapter

    db_chapters = (
        mock_db_session.query(Chapter)
        .filter(Chapter.textbook_id == data["textbook_id"])
        .all()
    )
    for ch in db_chapters:
        assert ch.content_summary is not None and len(ch.content_summary) > 0, (
            f"chapter {ch.chapter_number} content_summary 为空（应从 PDF 抽出）"
        )
        assert ch.extraction_source == "detected"


def test_upload_real_pdf_persists_to_db(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """上传真 PDF 后，DB 中可见 Textbook + Chapter 行（验证持久化）。

    M2 工单 A：
    - Chapter.extraction_source = 'detected'
    - Chapter.content_summary 非空
    - Textbook.file_path = 'uploads/{textbook_id}/test.pdf'（不是 uploaded:{name}.pdf）
    """
    if not REAL_PDF_PATH.exists():
        import pytest

        pytest.skip(f"真 PDF 不存在：{REAL_PDF_PATH}")

    from app.models import Chapter, Textbook

    client = _build_test_client(mock_db_session, mock_llm_provider)
    pdf_bytes = REAL_PDF_PATH.read_bytes()

    resp = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        data={"name": "持久化测试教材"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201
    data = resp.json()
    textbook_id = data["textbook_id"]
    n_chapters = len(data["chapters"])

    # DB 直查
    tb = mock_db_session.get(Textbook, textbook_id)
    assert tb is not None, "Textbook 行未持久化"
    assert tb.name == "持久化测试教材"
    assert tb.grade_level is None  # 没传 grade_level

    # M2 工单 A：file_path 改为真实相对路径（不是 uploaded:{name}.pdf）
    assert tb.file_path.startswith(f"uploads/{textbook_id}/"), (
        f"file_path 应为 uploads/{textbook_id}/{{filename}}.pdf，"
        f"实际 {tb.file_path!r}"
    )
    assert not tb.file_path.startswith("uploaded:"), (
        f"file_path 不应是 uploaded:...（M2 P0-2 修复证据），实际 {tb.file_path!r}"
    )

    db_chapters = (
        mock_db_session.query(Chapter)
        .filter(Chapter.textbook_id == textbook_id)
        .all()
    )
    assert len(db_chapters) == n_chapters, "Chapter 行数与响应不一致"
    for ch in db_chapters:
        assert ch.extraction_source == "detected", (
            f"chapter {ch.id} extraction_source 应为 detected，实际 {ch.extraction_source!r}"
        )
        assert ch.content_summary is not None, (
            f"chapter {ch.id} content_summary 不应为 None（M2 P0-1 修复证据）"
        )


# ─────────────────────── 2. 非 PDF 上传 → 400 ───────────────────────


def test_upload_non_pdf_returns_400(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """上传纯文本（非 PDF）→ 400 + magic bytes 错误信息。

    注：errors.py 自定义 handler 把 HTTPException 包成 ErrorResponse{message, ...}，
    没有 detail 键；要查错误信息用 message。
    """
    client = _build_test_client(mock_db_session, mock_llm_provider)
    non_pdf_bytes = b"this is just plain text, not a PDF"
    resp = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("fake.pdf", non_pdf_bytes, "application/pdf")},
        data={"name": "假 PDF"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    message = body.get("message", body.get("detail", ""))
    assert "PDF" in message or "magic" in message.lower(), f"错误信息应提及 PDF/magic：{body}"


def test_upload_pdf_with_wrong_magic_returns_400(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """上传 %PDF 开头但实际不是 PDF（垃圾内容）→ 400（PyMuPDF 打不开 / 解析无章节）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    # magic bytes 通过但后续内容不是合法 PDF → extractor 会拒绝
    fake = b"%PDF-1.4\n" + b"GARBAGE NO PDF STRUCTURE " * 100
    resp = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("corrupt.pdf", fake, "application/pdf")},
        data={"name": "损坏 PDF"},
        headers={"X-User-Id": "1"},
    )
    # PyMuPDF 解析失败 → 400（"PDF 解析失败" 或 "未识别到任何章节"）
    assert resp.status_code == 400, resp.text


# ─────────────────────── 3. 空文件 → 400 ───────────────────────


def test_upload_empty_file_returns_400(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """上传 0 字节文件 → 400。

    注：errors.py 自定义 handler 把 HTTPException 包成 ErrorResponse{message, ...}。
    M2 工单 A：service 报错改为「文件过小（N bytes）」，原断言「空」不再适用
    （保持测试语义不变：仍是「拒绝空文件」）。
    """
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        data={"name": "空文件"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    message = body.get("message", body.get("detail", ""))
    assert "过小" in message or "PDF" in message, (
        f"错误信息应提及文件过小 / PDF：{body}"
    )


# ─────────────────────── 4. Form 字段校验 ───────────────────────


def test_upload_missing_name_returns_422(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """name Form 字段缺失 → 422（FastAPI Form 校验）。"""
    from io import BytesIO

    import fitz  # PyMuPDF

    # 构造最小 PDF（保证 magic bytes 通过 + 至少 1 章）
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "第一章 测试章节", fontsize=12)
    pdf_io = BytesIO()
    doc.save(pdf_io)
    doc.close()
    pdf_bytes = pdf_io.getvalue()

    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        # 故意不传 name
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 422


def test_upload_invalid_grade_level_returns_400(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """grade_level 非法值（如 "primary_school"）→ 400 / 422。"""
    from io import BytesIO

    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "第一章 测试", fontsize=12)
    pdf_io = BytesIO()
    doc.save(pdf_io)
    doc.close()
    pdf_bytes = pdf_io.getvalue()

    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        data={"name": "test", "grade_level": "primary_school"},  # 非法
        headers={"X-User-Id": "1"},
    )
    # FastAPI Form 校验（422）或 service 业务校验（400）皆可；只要不是 201
    assert resp.status_code in (400, 422), resp.text


# ============================ M2 工单 A 负面测试 ==============================
# Done 定义 #1：故意无法解析的 PDF 上传 → 400 + DB 不写入 Chapter 行。
# Done 定义 #4：至少一条「坏输入被拒绝」断言。
# 本节是 P0-2 + P0-3 修复后的负面前提：D-28 「验收门槛必须可被最坏实现证伪」。
# ============================ M2 工单 A 负面测试 ==============================


def test_upload_corrupt_bytes_no_chapter_persisted(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """M2 工单 A 负面前提 #1（Done #1 + #4）：
    上传 `%PDF-1.4\\n` 开头的损坏 bytes → 400 + DB 不写入 Chapter 行。

    背景：旧 verify 门槛 `章节数 ≥ 3` 可被损坏 PDF + 等分 fallback 恒真满足
    （P0-3）。现在损坏 PDF 上传必须被拒，且 DB 不留半成品 Chapter 行。
    """
    from app.models import Chapter, Textbook

    client = _build_test_client(mock_db_session, mock_llm_provider)
    # magic bytes 合法但后面是垃圾 → PyMuPDF 打开后会识别不出章节 → 400
    corrupt_pdf_bytes = b"%PDF-1.4\n" + b"GARBAGE_NO_PDF_STRUCTURE " * 200

    resp = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("corrupt.pdf", corrupt_pdf_bytes, "application/pdf")},
        data={"name": "损坏 PDF"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 400, (
        f"损坏 PDF 应被拒（400），实际 {resp.status_code} {resp.text}"
    )
    # DB 不应写入 Textbook + Chapter（Done #1 负面前提）
    assert mock_db_session.query(Textbook).count() == 0, (
        "损坏 PDF 不应留 Textbook 行"
    )
    assert mock_db_session.query(Chapter).count() == 0, (
        "损坏 PDF 不应留 Chapter 行"
    )


def test_upload_random_non_pdf_bytes_returns_400(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """M2 工单 A 负面前提 #2（Done #4）：
    上传随机 non-PDF bytes → 400 + magic bytes 错误信息。

    不需依赖损坏 PDF；这里用任意文本验证 magic bytes 校验入口。
    """
    client = _build_test_client(mock_db_session, mock_llm_provider)
    non_pdf_bytes = b"random_text_not_pdf_at_all_just_garbage"
    resp = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("random.pdf", non_pdf_bytes, "application/pdf")},
        data={"name": "随机 bytes"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 400
    body = resp.json()
    message = body.get("message", body.get("detail", ""))
    assert "magic" in message.lower() or "PDF" in message, (
        f"错误信息应提及 magic/PDF：{body}"
    )


def test_upload_empty_pdf_marks_scanned_pdf_empty(
    mock_db_session: Any, mock_llm_provider: Any, tmp_path
) -> None:
    """M2 工单 A 负面前提 #3（Done #4 + 链路完备性）：
    上传扫描型 PDF（页文本全空）→ 201 + extraction_source='scanned_pdf_empty'
    + content_summary=None。

    背景：扫描型 PDF 是不可读文本的合法场景；旧代码默认填 "" 或 None 但无
    source 标记，M2 加 'scanned_pdf_empty' 后下游能识别为「待 OCR」状态。
    """
    import fitz  # PyMuPDF

    # 造一个 3 页全空 PDF（无任何文字、图片；PyMuPDF 能打开 + 返回 3 页）
    scanned_pdf_path = tmp_path / "scanned.pdf"
    doc = fitz.open()
    for _ in range(3):
        doc.new_page(width=400, height=600)
    doc.save(scanned_pdf_path)
    doc.close()
    pdf_bytes = scanned_pdf_path.read_bytes()

    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("scanned.pdf", pdf_bytes, "application/pdf")},
        data={"name": "扫描型 PDF"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    chapters = data["chapters"]
    # 扫描型 PDF 走等分 5 章；每章 extraction_source = scanned_pdf_empty
    assert len(chapters) == 5, f"扫描型 PDF 应返 5 章等分，实际 {len(chapters)}"
    for ch in chapters:
        assert ch["extraction_source"] == "scanned_pdf_empty", (
            f"扫描型 PDF 每章应标 scanned_pdf_empty，实际 {ch['extraction_source']!r}"
        )