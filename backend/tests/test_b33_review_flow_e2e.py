"""B.3.3 §7.5 流程端到端 + OpenAPI B.3 验证测试（M1-B B.3 收官）。

覆盖（B.3 spec）：
1. lesson-plan pending → reviewed 端到端 + review_notes 写入 DB
2. lesson-plan pending → modified 端到端 + content 覆写 + review_notes 写入 DB
3. chapter extract → PATCH /chapters/{id}/review 全流程 + notes 持久化
4. OpenAPI schema：B.3.1 升级的 upload 端点（multipart/form-data）在 OpenAPI 暴露
5. OpenAPI schema：AIAnnotation 5 字段 + TeacherReviewStatus 4 字段在 components.schemas 可见
   + 所有 lesson-plan / chapter-extract 响应 schema 引用 AIAnnotation

实现要点：
- SQLite in-memory（mock_db_session fixture）
- 走 FastAPI TestClient + dependency override（get_db + get_llm_dep）
- mock_llm_provider 给真 LLM 真值（JSON 响应 + 文本响应）
- DB 直查验证 review_notes / review_status / content 写入
"""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from app.main import create_app as build_app


def _build_test_client(
    db_session: Any,
    llm_provider: Any,
) -> TestClient:
    from app.api.v1.routers.academic import get_llm_dep
    from app.db.session import get_db

    app = build_app()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_llm_dep] = lambda: llm_provider
    return TestClient(app)


# ─────────────────────── §7.5 流程端到端（B.3.3 核心） ───────────────────────


def test_b33_lesson_plan_review_notes_persisted_to_db(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_chapter: Any,
) -> None:
    """B.3.3：lesson-plan pending → reviewed 端到端 + review_notes 实际写入 DB。

    关键验证：notes 不仅在响应里出现，DB 的 lesson_plans.review_notes 字段也要有值
    （B.3 spec: §7.5 review_status 流转（含 review_notes））。
    """
    from app.models import LessonPlan

    mock_llm_provider.set_chat_response("AI 生成的授课建议正文")
    client = _build_test_client(mock_db_session, mock_llm_provider)

    # 1. 创建 lesson-plan（pending）
    create = client.post(
        "/api/v1/academic/lesson-plans/generate",
        json={"chapter_id": mock_chapter.id, "duration_minutes": 45},
        headers={"X-User-Id": "1"},
    )
    assert create.status_code == 201
    lp_id = create.json()["id"]

    # 2. PATCH /review → reviewed + notes
    notes_value = "B.3.3 端到端验证：内容覆盖全面，通过"
    resp = client.patch(
        f"/api/v1/academic/lesson-plans/{lp_id}/review",
        json={"status": "reviewed", "notes": notes_value},
        headers={"X-User-Id": "5"},
    )
    # D-29/D-37：user_5 评审 user_1 资源 → 404（不豁免）
    assert resp.status_code == 404, (
        f"D-29 不可豁免：user_5 评审 user_1 资源应返 404，实际 {resp.status_code}：{resp.text}"
    )
    assert resp.json()["review"]["review_status"] == "reviewed"
    assert resp.json()["review"]["review_notes"] == notes_value

    # 3. DB 直查：review_notes 真的写入了
    lp_row = mock_db_session.get(LessonPlan, lp_id)
    assert lp_row is not None
    assert lp_row.review_notes == notes_value, "DB 中 review_notes 未持久化"
    assert lp_row.review_status.value == "approved"  # ORM 内部 = approved；API = reviewed
    assert lp_row.reviewed_by == 5
    assert lp_row.reviewed_at is not None


def test_b33_lesson_plan_modified_with_content_and_notes(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_chapter: Any,
) -> None:
    """B.3.3：lesson-plan pending → modified：content 可改 + notes 持久化（双重 B.3.3 验收）。"""
    from app.models import LessonPlan

    ai_content = "AI 原内容"
    modified_content = "教师覆写后的授课建议"
    notes_value = "B.3.3 modified：调整了导入环节"

    mock_llm_provider.set_chat_response(ai_content)
    client = _build_test_client(mock_db_session, mock_llm_provider)

    # create + review
    create = client.post(
        "/api/v1/academic/lesson-plans/generate",
        json={"chapter_id": mock_chapter.id, "duration_minutes": 45},
        headers={"X-User-Id": "1"},
    )
    lp_id = create.json()["id"]

    resp = client.patch(
        f"/api/v1/academic/lesson-plans/{lp_id}/review",
        json={
            "status": "modified",
            "notes": notes_value,
            "content": modified_content,
        },
        headers={"X-User-Id": "3"},
    )
    # D-29/D-37：user_3 评审 user_1 资源 → 404（不豁免）
    assert resp.status_code == 404, (
        f"D-29 不可豁免：user_3 评审 user_1 资源应返 404，实际 {resp.status_code}：{resp.text}"
    )
    assert resp.json()["review"]["review_status"] == "modified"

    # DB 直查
    lp_row = mock_db_session.get(LessonPlan, lp_id)
    assert lp_row is not None
    assert lp_row.content == modified_content
    assert lp_row.review_notes == notes_value
    assert lp_row.review_status.value == "modified"


def test_b33_chapter_review_pending_to_reviewed_with_notes(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_chapter: Any,
) -> None:
    """B.3.3：chapter extract → PATCH /chapters/{id}/review 全流程 + notes 持久化。"""
    from app.models import KnowledgeReview

    mock_llm_provider.set_chat_response(
        json.dumps(
            {
                "key_points": ["A", "B", "C"],
                "difficulties": ["D", "E"],
                "teaching_suggestions": ["F", "G"],
            },
            ensure_ascii=False,
        )
    )
    client = _build_test_client(mock_db_session, mock_llm_provider)

    # extract
    extract = client.post(
        f"/api/v1/academic/chapters/{mock_chapter.id}/extract",
        json={},
        headers={"X-User-Id": "1"},
    )
    assert extract.status_code == 201
    review_id = extract.json()["review_id"]

    # review
    notes_value = "B.3.3 chapter review：抽取结果 OK"
    resp = client.patch(
        f"/api/v1/academic/chapters/{mock_chapter.id}/review",
        json={"status": "reviewed", "notes": notes_value},
        headers={"X-User-Id": "9"},
    )
    # D-29/D-37：user_9 评审 user_1 资源 → 404（不豁免）
    assert resp.status_code == 404, (
        f"D-29 不可豁免：user_9 评审 user_1 资源应返 404，实际 {resp.status_code}：{resp.text}"
    )
    assert resp.json()["review"]["review_status"] == "reviewed"
    assert resp.json()["review"]["review_notes"] == notes_value

    # DB 直查
    review_row = mock_db_session.get(KnowledgeReview, review_id)
    assert review_row is not None
    assert review_row.notes == notes_value
    assert review_row.status.value == "approved"
    assert review_row.reviewed_by == f"user:{9}"


# ─────────────────────── OpenAPI B.3.1 + B.3.3 schema 验证 ───────────────────────


def test_b33_openapi_upload_endpoint_multipart_form(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """B.3.3：POST /textbooks/upload 在 OpenAPI 暴露为 multipart/form-data（B.3.1 升级证据）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()

    path = "/api/v1/academic/textbooks/upload"
    assert path in schema["paths"], f"OpenAPI 缺 {path}"
    upload_op = schema["paths"][path]["post"]

    # requestBody 必含 multipart/form-data
    request_body = upload_op.get("requestBody", {})
    content = request_body.get("content", {})
    assert "multipart/form-data" in content, (
        f"upload 端点应为 multipart/form-data，实际：{list(content.keys())}"
    )

    # schema 引用 components.schemas.TextbookUploadResponse
    resp_ref = upload_op["responses"]["201"]["content"]["application/json"]["schema"]
    assert "$ref" in resp_ref, "201 响应 schema 应引用 components.schemas"


def test_b33_openapi_ai_annotation_and_review_status_schemas(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """B.3.3：AIAnnotation + TeacherReviewStatus 在 components.schemas 可见 + 字段完整。

    §7.4 必带字段：ai_generated, model, generated_at, requires_teacher_review, annotation
    §7.5 必带字段：review_status, reviewed_by, reviewed_at, review_notes
    """
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get("/openapi.json")
    schemas = resp.json().get("components", {}).get("schemas", {})

    # AIAnnotation
    ai_schemas = {n: s for n, s in schemas.items() if n == "AIAnnotation"}
    assert ai_schemas, f"OpenAPI 缺 AIAnnotation schema：{list(schemas.keys())}"
    ai_props = next(iter(ai_schemas.values()))["properties"]
    for f in ("ai_generated", "model", "generated_at", "requires_teacher_review", "annotation"):
        assert f in ai_props, f"§7.4 缺字段 {f}：{list(ai_props.keys())}"

    # TeacherReviewStatus
    rs_schemas = {n: s for n, s in schemas.items() if n == "TeacherReviewStatus"}
    assert rs_schemas, f"OpenAPI 缺 TeacherReviewStatus schema：{list(schemas.keys())}"
    rs_props = next(iter(rs_schemas.values()))["properties"]
    for f in ("review_status", "reviewed_by", "reviewed_at", "review_notes"):
        assert f in rs_props, f"§7.5 缺字段 {f}：{list(rs_props.keys())}"

    # review_status enum 三态
    enum_values = rs_props["review_status"].get("enum", [])
    for s in ("pending", "reviewed", "modified"):
        assert s in enum_values, f"review_status enum 缺 {s}：{enum_values}"


def test_b33_openapi_lesson_plan_responses_reference_ai_annotation(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """B.3.3：lesson-plan + chapter-extract 响应 schema 引用 AIAnnotation（§7.4 硬约束）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get("/openapi.json")
    schema = resp.json()
    schemas = schema["components"]["schemas"]

    # lesson-plan generate 响应 schema
    lp_op = schema["paths"]["/api/v1/academic/lesson-plans/generate"]["post"]
    lp_resp = lp_op["responses"]["201"]["content"]["application/json"]["schema"]["$ref"]
    # ref 形如 "#/components/schemas/LessonPlanResponse"
    lp_resp_schema_name = lp_resp.split("/")[-1]
    lp_resp_schema = schemas[lp_resp_schema_name]
    # LessonPlanResponse 必有 ai 字段（type=AIAnnotation）
    assert "ai" in lp_resp_schema["properties"]
    ai_ref = lp_resp_schema["properties"]["ai"]
    assert "$ref" in ai_ref
    assert ai_ref["$ref"].endswith("/AIAnnotation"), f"lesson-plan.ai 应引用 AIAnnotation：{ai_ref}"

    # chapter extract 响应 schema
    extract_op = schema["paths"]["/api/v1/academic/chapters/{chapter_id}/extract"]["post"]
    extract_resp = extract_op["responses"]["201"]["content"]["application/json"]["schema"]["$ref"]
    extract_resp_schema_name = extract_resp.split("/")[-1]
    extract_resp_schema = schemas[extract_resp_schema_name]
    assert "ai" in extract_resp_schema["properties"]
    assert extract_resp_schema["properties"]["ai"]["$ref"].endswith("/AIAnnotation")


def test_b33_openapi_eight_academic_paths_visible(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """B.3.3：8 个 academic 端点路径在 OpenAPI 暴露（与 B.2 spec 一致）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get("/openapi.json")
    paths = resp.json().get("paths", {})

    expected = {
        "/api/v1/academic/textbooks/upload",
        "/api/v1/academic/textbooks/{textbook_id}/chapters",
        "/api/v1/academic/chapters/{chapter_id}/extract",
        "/api/v1/academic/chapters/{chapter_id}",
        "/api/v1/academic/chapters/{chapter_id}/review",
        "/api/v1/academic/lesson-plans/generate",
        "/api/v1/academic/lesson-plans/{lesson_plan_id}",
        "/api/v1/academic/lesson-plans/{lesson_plan_id}/review",
    }
    actual = {p for p in paths if "/api/v1/academic/" in p}
    assert expected.issubset(actual), f"OpenAPI 缺 academic 路径：{expected - actual}"