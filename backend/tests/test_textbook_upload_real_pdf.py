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

    # chapter_number 单调（升序）
    nums = [ch["chapter_number"] for ch in chapters]
    assert nums == sorted(nums), f"chapter_number 应升序：{nums}"


def test_upload_real_pdf_persists_to_db(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """上传真 PDF 后，DB 中可见 Textbook + Chapter 行（验证持久化）。"""
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
    textbook_id = resp.json()["textbook_id"]
    n_chapters = len(resp.json()["chapters"])

    # DB 直查
    tb = mock_db_session.get(Textbook, textbook_id)
    assert tb is not None, "Textbook 行未持久化"
    assert tb.name == "持久化测试教材"
    assert tb.grade_level is None  # 没传 grade_level

    db_chapters = (
        mock_db_session.query(Chapter)
        .filter(Chapter.textbook_id == textbook_id)
        .all()
    )
    assert len(db_chapters) == n_chapters, "Chapter 行数与响应不一致"


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
    assert "空" in message, f"错误信息应提及空文件：{body}"


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