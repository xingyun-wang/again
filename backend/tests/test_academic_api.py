"""Academic 业务 API smoke tests（M1-B B.2.1：API 骨架 + 数据模型）。

覆盖 8 个端点 + §7.4 AI 声明字段在 response 中可见 + X-User-Id 缺失 401。

策略：
- SQLite in-memory（mock_db_session fixture from conftest.py）
- FastAPI dependency override：get_db → mock session；get_llm_dep → mock LLM
- 每个测试前建表 + drop，状态隔离
- 走 TestClient（httpx + FastAPI 同步模式）

注：B.2 spec 列了 7 个端点，B.2.3 §7.5 流程测试需要第 8 个
PATCH /lesson-plans/{id}/review（judgment call）。
"""

from __future__ import annotations

import json
from io import BytesIO
from typing import Any

from fastapi.testclient import TestClient

from app.main import create_app as build_app


def _build_test_client(
    db_session: Any,
    llm_provider: Any,
) -> TestClient:
    """构造带 DB + LLM 依赖 override 的 TestClient。

    注意：override 必须是 generator 函数（def + yield），不是 lambda 返回 generator。
    FastAPI 0.141 对 override 返回 generator 的处理路径与 generator function 不一致
    （后者通过 inspect.isgenerator 检查迭代；前者直接作为 dependency 使用，导致 route
    拿到 generator 对象本身）。直接写 generator function 最稳。
    """
    from app.api.v1.routers.academic import get_llm_dep
    from app.db.session import get_db

    app = build_app()

    def _override_get_db():  # generator function（def + yield）
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_llm_dep] = lambda: llm_provider
    return TestClient(app)


# ─────────────────────────── 1. 教材上传（B.3 升级 multipart/form-data） ────────────
# B.3：B.2 mock（JSON body）已升级为 multipart/form-data + 真 PDF 抽取。
# 旧的"chapters 列表为空 → 422"测试不再适用（multipart 不接空 chapters）；
# 该场景在 test_textbook_upload_real_pdf.py::test_upload_real_pdf_extracts_chapters
# 覆盖（真 PDF 解析出 ≥ 1 章节）。B.2 spec "chapters 必填"语义被 PDF 文件本身替代。


def _build_minimal_pdf_bytes(title_line: str = "测试教材") -> bytes:
    """构造一个最小可解析的 PDF（PyMuPDF 能打开 + 识别 chapter title）。

    用 PyMuPDF 生成：1 页 + 1 行文本"第一章 测试章节"。PyMuPDF 章节正则识别
    「第X章 title」格式。
    """
    import fitz  # PyMuPDF

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), f"{title_line} 测试章节内容", fontsize=12)
    pdf_bytes_io = BytesIO()
    doc.save(pdf_bytes_io)
    doc.close()
    return pdf_bytes_io.getvalue()


def test_textbook_upload_creates_textbook_and_chapters(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """POST /textbooks/upload（B.3 multipart/form-data）创建 Textbook + Chapter。

    M2 工单 A：响应里必须有 extraction_source 字段（链路真源标记）。
    """
    client = _build_test_client(mock_db_session, mock_llm_provider)
    pdf_bytes = _build_minimal_pdf_bytes("第一章")
    resp = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        data={"name": "人教版数学七上"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["textbook_id"] >= 1
    assert data["name"] == "人教版数学七上"
    assert len(data["chapters"]) >= 1
    assert data["chapters"][0]["has_extracted"] is False
    # M2 工单 A：每章节都有 extraction_source 字段（取值在 Literal 4 选一之内）
    for ch in data["chapters"]:
        assert ch["extraction_source"] in {
            "detected",
            "pdfplumber_fallback",
            "equal_split_placeholder",
            "scanned_pdf_empty",
        }, f"extraction_source 非法：{ch['extraction_source']!r}"


def test_textbook_upload_404_subject_not_found(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """subject_id 不存在 → 404。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    pdf_bytes = _build_minimal_pdf_bytes()
    resp = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        data={"name": "test", "subject_id": "9999"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 404


# ────────────────────── 2. 教材下章节列表 ──────────────────────


def test_list_textbook_chapters_returns_chapter_summary(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_textbook: Any,
    mock_chapter: Any,
) -> None:
    """GET /textbooks/{id}/chapters 返回章节摘要列表。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get(
        f"/api/v1/academic/textbooks/{mock_textbook.id}/chapters",
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["textbook_id"] == mock_textbook.id
    assert len(data["chapters"]) == 1
    assert data["chapters"][0]["title"] == mock_chapter.title


def test_list_textbook_chapters_404(mock_db_session: Any, mock_llm_provider: Any) -> None:
    """textbook 不存在 → 404。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get(
        "/api/v1/academic/textbooks/9999/chapters",
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 404


# ────────────────────── 3. 章节 extract（mock LLM） ──────────────────────


def test_chapter_extract_calls_llm_and_creates_rows(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_chapter: Any,
) -> None:
    """POST /chapters/{id}/extract 调用 LLM → 创建 KeyPoint/Difficulty/TeachingSuggestion + KnowledgeReview(pending)。

    §7.4: ai 字段（ai_generated=true, model, generated_at, requires_teacher_review=true, annotation）可见。
    §7.5: review 字段 review_status=pending。
    """
    # 设置 mock LLM 返回：固定结构（测试不依赖真 LLM）
    mock_llm_provider.set_chat_response(
        json.dumps(
            {
                "key_points": ["重点 A", "重点 B"],
                "difficulties": ["难点 A"],
                "teaching_suggestions": ["建议 A"],
            },
            ensure_ascii=False,
        )
    )

    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        f"/api/v1/academic/chapters/{mock_chapter.id}/extract",
        json={},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()

    # §7.4: ai 字段全部必带
    assert data["ai"]["ai_generated"] is True
    assert data["ai"]["requires_teacher_review"] is True
    assert "model" in data["ai"]
    assert "generated_at" in data["ai"]
    assert "annotation" in data["ai"]
    assert "AI" in data["ai"]["annotation"]  # UI 标签值含"AI"

    # §7.5: review 字段 = pending
    assert data["review"]["review_status"] == "pending"
    assert data["review"]["reviewed_by"] is None
    assert data["review"]["reviewed_at"] is None

    # 抽取内容正确
    assert data["key_points"] == ["重点 A", "重点 B"]
    assert data["difficulties"] == ["难点 A"]
    assert data["teaching_suggestions"] == ["建议 A"]

    # LLM 被调用过
    assert len(mock_llm_provider.chat_calls) == 1


def test_chapter_extract_404(mock_db_session: Any, mock_llm_provider: Any) -> None:
    """chapter 不存在 → 404。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/chapters/9999/extract",
        json={},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 404


def test_chapter_extract_handles_markdown_fences(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_chapter: Any,
) -> None:
    """LLM 返回 ```json ... ``` 包裹的响应也能解析。"""
    mock_llm_provider.set_chat_response(
        "```json\n"
        + json.dumps(
            {
                "key_points": ["X"],
                "difficulties": ["Y"],
                "teaching_suggestions": ["Z"],
            },
            ensure_ascii=False,
        )
        + "\n```"
    )
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        f"/api/v1/academic/chapters/{mock_chapter.id}/extract",
        json={},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201
    assert resp.json()["key_points"] == ["X"]


def test_chapter_extract_422_on_bad_json(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_chapter: Any,
) -> None:
    """LLM 返回非 JSON → 422（业务错误）。"""
    mock_llm_provider.set_chat_response("not json at all")
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        f"/api/v1/academic/chapters/{mock_chapter.id}/extract",
        json={},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 422


# ────────────────────── 4. 章节详情 ──────────────────────


def test_chapter_detail_includes_ai_summary(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_chapter: Any,
) -> None:
    """GET /chapters/{id} 返回 ai_summary（§7.4）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get(
        f"/api/v1/academic/chapters/{mock_chapter.id}",
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == mock_chapter.id
    assert "ai_summary" in data
    # 未抽取时 ai_summary 的 ai/review 应为 null
    assert data["ai_summary"]["has_extracted"] is False
    assert data["ai_summary"]["ai"] is None


def test_chapter_detail_404(mock_db_session: Any, mock_llm_provider: Any) -> None:
    """chapter 不存在 → 404。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get(
        "/api/v1/academic/chapters/9999",
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 404


# ────────────────────── 5. 章节 review PATCH ──────────────────────


def test_chapter_review_marks_reviewed(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_chapter: Any,
) -> None:
    """先 extract 创建 pending review；再 PATCH /review 标记 reviewed → status 流转。"""
    mock_llm_provider.set_chat_response(
        json.dumps(
            {"key_points": ["A"], "difficulties": ["B"], "teaching_suggestions": ["C"]},
            ensure_ascii=False,
        )
    )
    client = _build_test_client(mock_db_session, mock_llm_provider)
    # 先 extract
    extract_resp = client.post(
        f"/api/v1/academic/chapters/{mock_chapter.id}/extract",
        json={},
        headers={"X-User-Id": "1"},
    )
    assert extract_resp.status_code == 201
    review_id = extract_resp.json()["review_id"]

    # 再 review
    resp = client.patch(
        f"/api/v1/academic/chapters/{mock_chapter.id}/review",
        json={"status": "reviewed", "notes": "看起来 OK"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["review_id"] == review_id
    assert data["review"]["review_status"] == "reviewed"
    assert data["review"]["reviewed_by"] == 1
    assert data["review"]["reviewed_at"] is not None
    assert data["review"]["review_notes"] == "看起来 OK"


def test_chapter_review_409_without_prior_extract(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_chapter: Any,
) -> None:
    """未先 extract 就 review → 409（§7.5 必须有 review 行）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.patch(
        f"/api/v1/academic/chapters/{mock_chapter.id}/review",
        json={"status": "reviewed"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 409


# ────────────────────── 6. lesson-plan generate（mock LLM） ──────────────────────


def test_lesson_plan_generate_calls_llm_and_creates_pending(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_chapter: Any,
) -> None:
    """POST /lesson-plans/generate 调 LLM → 创建 LessonPlan(review_status=pending)。

    §7.4 + §7.5 字段都在 response 中。
    """
    mock_llm_provider.set_chat_response("这是 AI 生成的授课建议正文。教学目标：... 教学环节：...")
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/lesson-plans/generate",
        json={
            "chapter_id": mock_chapter.id,
            "duration_minutes": 45,
            "student_count": 50,
        },
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["chapter_id"] == mock_chapter.id
    assert data["chapter_title"] == mock_chapter.title
    assert "AI" in data["content"] or "建议" in data["content"]

    # §7.4
    assert data["ai"]["ai_generated"] is True
    assert data["ai"]["requires_teacher_review"] is True

    # §7.5
    assert data["review"]["review_status"] == "pending"


def test_lesson_plan_generate_404(mock_db_session: Any, mock_llm_provider: Any) -> None:
    """chapter 不存在 → 404。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/lesson-plans/generate",
        json={"chapter_id": 9999},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 404


# ────────────────────── 7. lesson-plan GET ──────────────────────


def test_lesson_plan_get_returns_full(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_chapter: Any,
) -> None:
    """GET /lesson-plans/{id} 返回完整字段（含 §7.4 + §7.5）。"""
    mock_llm_provider.set_chat_response("授课建议正文")
    client = _build_test_client(mock_db_session, mock_llm_provider)
    # 先创建
    create_resp = client.post(
        "/api/v1/academic/lesson-plans/generate",
        json={"chapter_id": mock_chapter.id, "duration_minutes": 45},
        headers={"X-User-Id": "1"},
    )
    assert create_resp.status_code == 201
    lp_id = create_resp.json()["id"]

    # 再 GET
    resp = client.get(
        f"/api/v1/academic/lesson-plans/{lp_id}",
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == lp_id
    assert data["chapter_id"] == mock_chapter.id
    assert "ai" in data and "review" in data


# ────────────── 8. lesson-plan review PATCH（judgment call） ──────────────


def test_lesson_plan_review_marks_reviewed(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_chapter: Any,
) -> None:
    """§7.5 流程硬约束：lesson-plan generate → pending → PATCH /review 标记 reviewed。"""
    mock_llm_provider.set_chat_response("授课建议正文")
    client = _build_test_client(mock_db_session, mock_llm_provider)
    create_resp = client.post(
        "/api/v1/academic/lesson-plans/generate",
        json={"chapter_id": mock_chapter.id, "duration_minutes": 45},
        headers={"X-User-Id": "1"},
    )
    assert create_resp.status_code == 201
    lp_id = create_resp.json()["id"]

    resp = client.patch(
        f"/api/v1/academic/lesson-plans/{lp_id}/review",
        json={"status": "reviewed", "notes": "OK"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["review"]["review_status"] == "reviewed"
    assert data["review"]["reviewed_by"] == 1
    assert data["review"]["review_notes"] == "OK"


# ─────────────────────────── X-User-Id 校验 ────────────────────────────


def test_endpoints_require_x_user_id_header(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """所有 academic 端点缺 X-User-Id → 401。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    # 任意挑几个端点
    assert client.get("/api/v1/academic/chapters/1").status_code == 401
    # multipart/form-data（即使空 body 也需要 X-User-Id → 401）
    assert client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("x.pdf", b"%PDF-1.4\n", "application/pdf")},
        data={"name": "x"},
    ).status_code == 401
    assert client.post(
        "/api/v1/academic/lesson-plans/generate", json={"chapter_id": 1}
    ).status_code == 401


def test_x_user_id_must_be_positive(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """X-User-Id ≤ 0 → 401。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get(
        "/api/v1/academic/chapters/1",
        headers={"X-User-Id": "0"},
    )
    assert resp.status_code == 401


# ─────────────────────────── 路由注册校验 ────────────────────────────


def test_all_eight_endpoints_registered(mock_db_session: Any, mock_llm_provider: Any) -> None:
    """router 上注册的端点数 = 8（B.2 spec 7 + judgment call 1）。"""
    from app.api.v1.routers.academic import router

    paths = {(r.path, tuple(r.methods or set())) for r in router.routes}
    expected = {
        ("/textbooks/upload", ("POST",)),
        ("/textbooks/{textbook_id}/chapters", ("GET",)),
        ("/chapters/{chapter_id}/extract", ("POST",)),
        ("/chapters/{chapter_id}", ("GET",)),
        ("/chapters/{chapter_id}/review", ("PATCH",)),
        ("/lesson-plans/generate", ("POST",)),
        ("/lesson-plans/{lesson_plan_id}", ("GET",)),
        ("/lesson-plans/{lesson_plan_id}/review", ("PATCH",)),
    }
    assert expected.issubset(paths), f"缺端点：{expected - paths}"