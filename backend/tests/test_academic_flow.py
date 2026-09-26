"""§7.5 流程硬约束 + OpenAPI schema 测试（M1-B B.2.3）。

覆盖：
1. lesson-plan 生成 → review_status=pending（§7.5 硬约束起点）
2. PATCH /lesson-plans/{id}/review 标记 reviewed → status 流转
3. PATCH /lesson-plans/{id}/review 标记 modified → content 可改
4. 章节 extract → review=pending（§7.5 硬约束起点）
5. PATCH /chapters/{id}/review 标记 reviewed → status 流转
6. §7.5 不允许：未先 extract 就 review（409）
7. OpenAPI schema：§7.4 字段（ai_generated / requires_teacher_review / model / generated_at /
   annotation）在 /openapi.json 中可见
8. OpenAPI schema：§7.5 字段（review_status / reviewed_by / reviewed_at / review_notes）
   在 /openapi.json 中可见
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.main import create_app as build_app


def _build_test_client(db_session: Any, llm_provider: Any) -> TestClient:
    from app.api.v1.routers.academic import get_llm_dep
    from app.db.session import get_db

    app = build_app()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_llm_dep] = lambda: llm_provider
    return TestClient(app)


# ───────────────────── §7.5 流程硬约束 ─────────────────────


def test_lesson_plan_review_status_starts_pending(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_chapter: Any,
) -> None:
    """§7.5：lesson-plan 生成时 review_status = pending（不可跳过）。"""
    mock_llm_provider.set_chat_response("授课建议正文")
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/lesson-plans/generate",
        json={"chapter_id": mock_chapter.id, "duration_minutes": 45},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["review"]["review_status"] == "pending"
    assert data["review"]["reviewed_by"] is None
    assert data["review"]["reviewed_at"] is None


def test_lesson_plan_review_flow_pending_to_reviewed(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_chapter: Any,
) -> None:
    """§7.5：pending → reviewed 流转 + reviewed_by/reviewed_at 填充。"""
    mock_llm_provider.set_chat_response("正文")
    client = _build_test_client(mock_db_session, mock_llm_provider)
    create = client.post(
        "/api/v1/academic/lesson-plans/generate",
        json={"chapter_id": mock_chapter.id},
        headers={"X-User-Id": "1"},
    )
    lp_id = create.json()["id"]

    # pending → reviewed
    resp = client.patch(
        f"/api/v1/academic/lesson-plans/{lp_id}/review",
        json={"status": "reviewed", "notes": "OK 通过"},
        headers={"X-User-Id": "7"},
    )
    # D-29/D-37：user_7 评审 user_1 资源 → 404（不豁免）
    assert resp.status_code == 404, (
        f"D-29 不可豁免：user_7 评审 user_1 资源应返 404，实际 {resp.status_code}：{resp.text}"
    )
    assert resp.json()["review"]["review_status"] == "reviewed"
    assert resp.json()["review"]["reviewed_by"] == 7
    assert resp.json()["review"]["reviewed_at"] is not None
    assert resp.json()["review"]["review_notes"] == "OK 通过"

    # GET 后状态保持
    get_resp = client.get(
        f"/api/v1/academic/lesson-plans/{lp_id}",
        headers={"X-User-Id": "1"},
    )
    assert get_resp.json()["review"]["review_status"] == "reviewed"


def test_lesson_plan_review_modified_updates_content(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_chapter: Any,
) -> None:
    """§7.5：pending → modified 时 content 可改（教师覆写 AI 建议）。"""
    mock_llm_provider.set_chat_response("AI 原内容")
    client = _build_test_client(mock_db_session, mock_llm_provider)
    create = client.post(
        "/api/v1/academic/lesson-plans/generate",
        json={"chapter_id": mock_chapter.id},
        headers={"X-User-Id": "1"},
    )
    lp_id = create.json()["id"]

    modified_content = "教师覆写后的授课建议"
    resp = client.patch(
        f"/api/v1/academic/lesson-plans/{lp_id}/review",
        json={"status": "modified", "content": modified_content, "notes": "改了"},
        headers={"X-User-Id": "3"},
    )
    # D-29/D-37：user_3 评审 user_1 资源 → 404（不豁免）
    assert resp.status_code == 404, (
        f"D-29 不可豁免：user_3 评审 user_1 资源应返 404，实际 {resp.status_code}：{resp.text}"
    )
    assert resp.json()["review"]["review_status"] == "modified"

    # GET 后 content 已是 modified 版本
    get_resp = client.get(
        f"/api/v1/academic/lesson-plans/{lp_id}",
        headers={"X-User-Id": "1"},
    )
    assert get_resp.json()["content"] == modified_content


def test_chapter_extract_review_status_starts_pending(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_chapter: Any,
) -> None:
    """§7.5：chapter extract 时新建 KnowledgeReview(review_status=pending)。"""
    import json as _json

    mock_llm_provider.set_chat_response(
        _json.dumps(
            {"key_points": ["A"], "difficulties": ["B"], "teaching_suggestions": ["C"]},
            ensure_ascii=False,
        )
    )
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        f"/api/v1/academic/chapters/{mock_chapter.id}/extract",
        json={},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201
    assert resp.json()["review"]["review_status"] == "pending"


def test_chapter_review_flow_pending_to_reviewed(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_chapter: Any,
) -> None:
    """§7.5：chapter extract (pending) → PATCH /review (reviewed)。"""
    import json as _json

    mock_llm_provider.set_chat_response(
        _json.dumps(
            {"key_points": ["A"], "difficulties": ["B"], "teaching_suggestions": ["C"]},
            ensure_ascii=False,
        )
    )
    client = _build_test_client(mock_db_session, mock_llm_provider)
    extract = client.post(
        f"/api/v1/academic/chapters/{mock_chapter.id}/extract",
        json={},
        headers={"X-User-Id": "1"},
    )
    review_id = extract.json()["review_id"]

    resp = client.patch(
        f"/api/v1/academic/chapters/{mock_chapter.id}/review",
        json={"status": "reviewed", "notes": "ok"},
        headers={"X-User-Id": "5"},
    )
    # D-29/D-37：user_5 评审 user_1 资源 → 404（不豁免）
    assert resp.status_code == 404, (
        f"D-29 不可豁免：user_5 评审 user_1 资源应返 404，实际 {resp.status_code}：{resp.text}"
    )
    assert resp.json()["review_id"] == review_id
    assert resp.json()["review"]["review_status"] == "reviewed"
    assert resp.json()["review"]["reviewed_by"] == 5

    # GET chapter 后 ai_summary 含 reviewed status
    get_resp = client.get(
        f"/api/v1/academic/chapters/{mock_chapter.id}",
        headers={"X-User-Id": "1"},
    )
    assert get_resp.json()["ai_summary"]["latest_review_status"] == "reviewed"


def test_review_without_prior_extract_returns_409(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_chapter: Any,
) -> None:
    """§7.5：未先 extract 就 review chapter → 409（必须有 review 行）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.patch(
        f"/api/v1/academic/chapters/{mock_chapter.id}/review",
        json={"status": "reviewed"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 409


def test_lesson_plan_review_404_when_not_found(
    mock_db_session: Any,
    mock_llm_provider: Any,
) -> None:
    """§7.5：lesson-plan 不存在 → 404。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.patch(
        "/api/v1/academic/lesson-plans/9999/review",
        json={"status": "reviewed"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 404


# ───────────────────── §7.4 OpenAPI schema 可见性 ─────────────────────


def test_openapi_schema_contains_ai_annotation_fields(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """§7.4：AIAnnotation schema 在 OpenAPI 中可见，且必带字段全在。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()

    # AIAnnotation schema 应在 components.schemas 里
    schemas = schema.get("components", {}).get("schemas", {})
    # 找 AIAnnotation（可能命名为 AIAnnotation 或类似）
    ai_schemas = {name: s for name, s in schemas.items() if "AIAnnotation" in name or "AI" in name}
    assert ai_schemas, f"OpenAPI 没暴露 AIAnnotation schema；schemas 列表：{list(schemas.keys())}"
    ai_schema = next(iter(ai_schemas.values()))

    # §7.4 必带字段
    props = ai_schema.get("properties", {})
    for field in ("ai_generated", "model", "generated_at", "requires_teacher_review", "annotation"):
        assert field in props, f"§7.4 缺字段 {field}：{list(props.keys())}"


def test_openapi_schema_contains_review_status_fields(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """§7.5：TeacherReviewStatus schema 在 OpenAPI 中可见。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()

    schemas = schema.get("components", {}).get("schemas", {})
    # 找 TeacherReviewStatus
    review_schemas = {
        name: s
        for name, s in schemas.items()
        if "TeacherReviewStatus" in name or "ReviewStatus" in name
    }
    assert review_schemas, f"OpenAPI 没暴露 TeacherReviewStatus schema；schemas：{list(schemas.keys())}"
    review_schema = next(iter(review_schemas.values()))

    # §7.5 必带字段
    props = review_schema.get("properties", {})
    for field in ("review_status", "reviewed_by", "reviewed_at", "review_notes"):
        assert field in props, f"§7.5 缺字段 {field}：{list(props.keys())}"

    # review_status 必须是 enum
    rs = props["review_status"]
    enum_values = rs.get("enum") or [v for v in rs.get("anyOf", [{}])[0].get("enum", [])]
    assert "pending" in enum_values, f"review_status enum 缺 pending：{enum_values}"
    assert "reviewed" in enum_values, f"review_status enum 缺 reviewed：{enum_values}"
    assert "modified" in enum_values, f"review_status enum 缺 modified：{enum_values}"


def test_openapi_doc_endpoint_accessible(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """/docs 端点可访问（Swagger UI）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get("/docs")
    assert resp.status_code == 200
    # Swagger UI 是 HTML
    assert "text/html" in resp.headers.get("content-type", "")


def test_openapi_exposes_eight_academic_paths(
    mock_db_session: Any, mock_llm_provider: Any
) -> None:
    """OpenAPI 含 8 个 academic 端点路径（B.2 spec 7 + judgment call 1）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
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