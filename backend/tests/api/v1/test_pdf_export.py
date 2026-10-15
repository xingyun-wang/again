"""S4 PDF 导出端到端测试（M2-S4 必跑；5 case 必全过）。

模式：复用 test_assignment_review.py:62-70（TestClient + generator-based dependency_overrides + X-User-Id）。
复用既有 _create_assignment_pending / _create_assignment_approved（不手搓 DB）。
所有 helper / client factory 抽到 tests/api/v1/_s4_helpers.py（per B11 = 避免 tests/api/__init__.py 缺失 ⇒ 双导入）。
"""
# ruff: noqa: F811
# F811 报 'chapter_with_questions' redefinition: 因 _s4_helpers.py re-export 既有 fixture
# (per B11 单一真值源) + pytest fixture 注入同名参数; 非真重定义, 是 pytest fixture 机制.

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Assignment
from app.services.assignment_export import render_assignment_pdf
from tests.api.v1._s4_helpers import (  # noqa: F401, F811
    _create_assignment_approved,
    _create_assignment_pending,
    chapter_with_questions,
    make_test_client,
)


@pytest.fixture()
def client(mock_db_session: Session) -> TestClient:
    """TestClient + dependency_overrides get_db（per test_assignment_review.py:62-70 既有模式；per A8 strict 修法）。"""
    return make_test_client(mock_db_session)


def test_pdf_export_403_when_not_approved(
    client, mock_db_session, chapter_with_questions
):
    """§7.5 闸门：review_status != APPROVED → 403。"""
    aid = _create_assignment_pending(client, chapter_with_questions.id)  # per A6: 删 mock_db_session
    r = client.post(
        f"/api/v1/assignments/{aid}/export",
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 403
    assert "未通过教师审阅" in r.json()["detail"]


def test_pdf_export_404_when_cross_user(
    client, mock_db_session, chapter_with_questions
):
    """D-29 B 项：跨用户 404 而非 403。"""
    aid = _create_assignment_approved(client, mock_db_session, chapter_with_questions.id)
    r = client.post(
        f"/api/v1/assignments/{aid}/export",
        headers={"X-User-Id": "999"},  # 不是 owner
    )
    assert r.status_code == 404
    assert "不存在" in r.json()["detail"]
    # per B12: 加强判别力 (防 "user 999 不存在" 同过伪绿)
    assert f"assignment {aid}" in r.json()["detail"]


def test_pdf_export_200_returns_valid_pdf(
    client, mock_db_session, chapter_with_questions
):
    """D-S4-3 ① 流式直返：200 + application/pdf + 头 4 字节 = %PDF。"""
    aid = _create_assignment_approved(client, mock_db_session, chapter_with_questions.id)
    r = client.post(
        f"/api/v1/assignments/{aid}/export",
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    assert "attachment" in r.headers.get("content-disposition", "")


def test_pdf_export_contains_chinese_marker(
    client, mock_db_session, chapter_with_questions, tmp_path
):
    """D-A1 (a) 字体嵌入 + 中文检出器。

    注 1（per B5）：整串中文标题做 in 断言易撞 PDF 断行假红；改用结构标记（短串 + 标点）。
    注 2（per A11 path 2）：A10 R2 覆盖度判据**撤除**（per 复核员 v4 评：硬红让 DoD 恒假 + CI 永久红 + 红与真红不可分）。
    字体扩集（3500 码点）= **S4.5 后续工单**（见 §十三 S4.5 范围）；本工单 (S4) 不做 tripwire。
    """
    aid = _create_assignment_approved(client, mock_db_session, chapter_with_questions.id)
    r = client.post(
        f"/api/v1/assignments/{aid}/export",
        headers={"X-User-Id": "1"},
    )
    pdf_path = tmp_path / "export.pdf"  # per B4 改用 tmp_path
    pdf_path.write_bytes(r.content)

    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        text = "".join(p.extract_text() or "" for p in pdf.pages)
        page_count = len(pdf.pages)

    # 结构标记断言（brief 字符集内）
    assert "作业单" in text, "结构标记 '作业单' 缺失"
    assert "§0 档位分布" in text, "结构标记 '§0 档位分布' 缺失"
    assert "D 基础" in text, "结构标记 'D 基础' 缺失"
    assert "[D]" in text, "结构标记 '[D]' 缺失"
    assert "§3 审阅状态" in text, "结构标记 '§3 审阅状态' 缺失"
    assert page_count >= 1, "至少 1 页"


def test_render_assignment_pdf_unit(client, mock_db_session, chapter_with_questions):
    """service 层单测：返 bytes + 头 4 字节 = %PDF + 长度 ≥ 1KB。"""
    # per A7: 用既有 client fixture (不用裸 FastAPI() = 无 include_router + 无 dependency_overrides ⇒ 必崩)
    aid = _create_assignment_approved(client, mock_db_session, chapter_with_questions.id)
    a = mock_db_session.get(Assignment, aid)
    pdf_bytes = render_assignment_pdf(a)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 1024
