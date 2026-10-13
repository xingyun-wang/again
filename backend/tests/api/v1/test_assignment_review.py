"""M2-S3 作业单审阅 + PDF 闸门测试（§7.5 流程硬约束）。

端点（routers/assignments.py）：
- PATCH /api/v1/assignments/{id}/review  → 老师审阅（status: reviewed/modified + notes）
- POST  /api/v1/assignments/{id}/export  → PDF 闸门（review_status=APPROVED 才放行）

用例设计（6 用例 = 5 反向 R1-R5 + 1 正向 F1；防 D-28 家族恒真 / 恒假门槛）：

| # | 场景 | 期望 | 闸门 |
|---|---|---|---|
| R1 | 新建 pending → POST /export | 403 | §7.5 核心反向：未审不得导出 |
| R2 | pending → PATCH /review status=pending | 422 | §7.5 Literal 扌 pending |
| R3 | APPROVED → PATCH /review status=pending | 422 | 不允许降级（Literal 扌） |
| R4 | user1 作业 → user2 PATCH /review | 404 | D-29 跨用户隔离 |
| R5 | user1 作业 → user2 POST /export | 404 | D-29 跨用户隔离 |
| F1 | pending → PATCH /review reviewed + notes → POST /export | 200 + 200 | 金玉良言完整闭环 |

验证要求：
- 容器 PG pytest：DATABASE_URL=postgresql... 跑出 6 passed
- 本地 SQLite 路径不验证（10-10 §三 实证会假红/假绿）
- 走 FastAPI TestClient + dependency_overrides[get_db]（hermetic）
- headers X-User-Id
- DB 直查：review_status / reviewed_by / review_notes
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

# A2 修法补充: module level import 所有 model,让 conftest 的 Base.metadata.create_all
# 看到它们(否则 fixture setup 阶段就崩: "no such table: users")
from app.models import (  # noqa: F401
    Assignment,
    AssignmentItem,
    Chapter,
    KnowledgeReviewStatus,
    Question,
    QuestionDifficulty,
    QuestionType,
    User,
)

if TYPE_CHECKING:
    pass


# ────────────────────────────── fixtures ──────────────────────────────


@pytest.fixture()
def client(mock_db_session: Any) -> TestClient:
    """FastAPI TestClient（hermetic：API 与 fixture 用同一 session）。

    A2 fix v3 极简 app：只挂 assignments_router + dependency_overrides[get_db]。
    """
    from fastapi import FastAPI

    from app.api.v1.routers.assignments import router as assignments_router
    from app.db.session import get_db

    app = FastAPI()

    def _override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.include_router(assignments_router, prefix="/api/v1")
    return TestClient(app)


@pytest.fixture()
def chapter_with_questions(
    mock_db_session: Any, mock_user_system_seed: Any, mock_textbook: Any
) -> Any:
    """章节 + 100 C + 100 D 池（同 test_assignments.py：chapter_with_questions）。"""
    ch = Chapter(
        textbook_id=mock_textbook.id,
        owner_user_id=mock_user_system_seed.id,
        chapter_number=1,
        title="S3-test-chapter",
        content_summary="S3 §7.5 测试用 chapter",
        extraction_source="detected",
    )
    mock_db_session.add(ch)
    mock_db_session.commit()

    # 100 D 池 + 100 C 池（足够 D 档 50 题作业）
    for i in range(100):
        q = Question(
            owner_user_id=mock_user_system_seed.id,
            chapter_id=ch.id,
            content=f"Q-D-{i}",
            difficulty=QuestionDifficulty.D,
            type=QuestionType.CHOICE,
        )
        mock_db_session.add(q)
    for i in range(100):
        q = Question(
            owner_user_id=mock_user_system_seed.id,
            chapter_id=ch.id,
            content=f"Q-C-{i}",
            difficulty=QuestionDifficulty.C,
            type=QuestionType.CHOICE,
        )
        mock_db_session.add(q)
    mock_db_session.commit()
    return ch


@pytest.fixture()
def user2(mock_db_session: Any) -> Any:
    """user2（id=2）— 跨用户隔离测试用。

    user1 = system-seed (id=1, is_system_owned=True)。
    user2 = 普通用户（is_system_owned=False），用于 R4/R5 跨用户越权。
    """
    user = User(id=2, name="user-2-cross", is_system_owned=False)
    mock_db_session.add(user)
    mock_db_session.commit()
    mock_db_session.refresh(user)
    return user


def _create_assignment_pending(
    client: TestClient, chapter_id: int, user_id: int = 1
) -> int:
    """走 API 创建作业单（默认 review_status=PENDING），返 id。"""
    resp = client.post(
        "/api/v1/assignments",
        json={"chapter_id": chapter_id, "tier": "D", "total_count": 50, "seed": 1},
        headers={"X-User-Id": str(user_id)},
    )
    assert resp.status_code == 201, (
        f"create assignment failed: {resp.status_code} {resp.text}"
    )
    return int(resp.json()["id"])


def _create_assignment_approved(
    client: TestClient,
    mock_db_session: Any,
    chapter_id: int,
    user_id: int = 1,
) -> int:
    """建 PENDING 后调 API PATCH /review reviewed 把它升 APPROVED，返 id。

    用于 R3（APPROVED 状态降级 422）。
    """
    aid = _create_assignment_pending(client, chapter_id, user_id)
    resp = client.patch(
        f"/api/v1/assignments/{aid}/review",
        json={"status": "reviewed", "notes": "initial review"},
        headers={"X-User-Id": str(user_id)},
    )
    assert resp.status_code == 200, (
        f"setup PATCH /review reviewed failed: {resp.status_code} {resp.text}"
    )
    return aid


# ─────────────────────── R1：pending → POST /export → 403 ─────────────────────


def test_R1_export_pending_403(
    client: TestClient,
    chapter_with_questions: Any,
) -> None:
    """§7.5 核心反向：未审不得导出。

    新建作业单（review_status=PENDING 默认）→ POST /export → 403。
    """
    aid = _create_assignment_pending(client, chapter_with_questions.id)

    resp = client.post(
        f"/api/v1/assignments/{aid}/export",
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 403, (
        f"pending assignment 导出应 403，实际 {resp.status_code}：{resp.text}"
    )
    # 错误 detail 应提及未审 / review_status
    detail = resp.json().get("detail", "")
    assert "未通过" in detail or "review" in detail.lower(), (
        f"403 detail 应说明未审原因，实际：{detail}"
    )


# ─────────────── R2：pending → PATCH /review status=pending → 422 ─────────────


def test_R2_review_status_pending_422(
    client: TestClient,
    chapter_with_questions: Any,
) -> None:
    """§7.5 Literal 扌 pending：PATCH /review 显式 status=pending → 422。

    Pydantic Literal["reviewed", "modified"] 扌 status=pending，FastAPI
    自动返 422。
    """
    aid = _create_assignment_pending(client, chapter_with_questions.id)

    resp = client.patch(
        f"/api/v1/assignments/{aid}/review",
        json={"status": "pending", "notes": "试图降级"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 422, (
        f"status=pending 应被 Literal 扌返 422，实际 {resp.status_code}：{resp.text}"
    )


# ─────────────── R3：APPROVED → PATCH /review status=pending → 422 ────────────


def test_R3_review_downgrade_to_pending_422(
    client: TestClient,
    chapter_with_questions: Any,
    mock_db_session: Any,
) -> None:
    """§7.5：不允许降级 APPROVED → pending。

    已经是 APPROVED 的作业单，PATCH /review status=pending 仍被 Literal 扌 → 422。
    """
    aid = _create_assignment_approved(
        client, mock_db_session, chapter_with_questions.id
    )

    resp = client.patch(
        f"/api/v1/assignments/{aid}/review",
        json={"status": "pending", "notes": "试图降级"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 422, (
        f"APPROVED 降级 pending 应返 422，实际 {resp.status_code}：{resp.text}"
    )


# ─────────────── R4：user1 作业 → user2 PATCH /review → 404 ─────────────────


def test_R4_review_cross_user_404(
    client: TestClient,
    chapter_with_questions: Any,
    user2: Any,
) -> None:
    """D-29 跨用户隔离：user2 越权 PATCH /review → 404（不暴露存在性）。"""
    aid = _create_assignment_pending(client, chapter_with_questions.id)

    resp = client.patch(
        f"/api/v1/assignments/{aid}/review",
        json={"status": "reviewed", "notes": "越权审阅"},
        headers={"X-User-Id": "2"},
    )
    assert resp.status_code == 404, (
        f"跨用户 PATCH /review 应 404，实际 {resp.status_code}：{resp.text}"
    )


# ─────────────── R5：user1 作业 → user2 POST /export → 404 ──────────────────


def test_R5_export_cross_user_404(
    client: TestClient,
    chapter_with_questions: Any,
    user2: Any,
) -> None:
    """D-29 跨用户隔离：user2 越权 POST /export → 404（不暴露存在性）。

    不审 owner check 顺序：404 应在 403 之前返（否则会泄漏“未审”状态）。
    """
    aid = _create_assignment_pending(client, chapter_with_questions.id)

    resp = client.post(
        f"/api/v1/assignments/{aid}/export",
        headers={"X-User-Id": "2"},
    )
    assert resp.status_code == 404, (
        f"跨用户 POST /export 应 404，实际 {resp.status_code}：{resp.text}"
    )


# ─────────────── F1：完整闭环：pending → reviewed → export（200 + 200） ─────


def test_F1_full_review_export_flow_200(
    client: TestClient,
    chapter_with_questions: Any,
    mock_db_session: Any,
) -> None:
    """金玉良言完整闭环：审阅后放行导出，DB 直查 review_status / reviewed_by / review_notes。

    防恒假门槛：
    - 预检 PATCH 返 200 + review.review_status == "reviewed"
    - 预检 POST 返 200 + export_id 形如 stub-{id}
    - DB 直查 review_status.value == "approved"（ORM 内部枚举）
    - DB 直查 reviewed_by == 1
    - DB 直查 review_notes == "..."
    """
    aid = _create_assignment_pending(client, chapter_with_questions.id)
    notes_value = "F1 闭环：内容审阅通过，可以导出"

    # 1. PATCH /review reviewed + notes
    review_resp = client.patch(
        f"/api/v1/assignments/{aid}/review",
        json={"status": "reviewed", "notes": notes_value},
        headers={"X-User-Id": "1"},
    )
    assert review_resp.status_code == 200, (
        f"PATCH /review 应 200，实际 {review_resp.status_code}：{review_resp.text}"
    )
    review_data = review_resp.json()
    assert review_data["id"] == aid
    assert review_data["review"]["review_status"] == "reviewed", (
        f"API review_status 应为 'reviewed'（词汇不一致债），实际 {review_data['review']['review_status']}"
    )
    assert review_data["review"]["reviewed_by"] == 1
    assert review_data["review"]["review_notes"] == notes_value

    # 2. POST /export
    export_resp = client.post(
        f"/api/v1/assignments/{aid}/export",
        headers={"X-User-Id": "1"},
    )
    assert export_resp.status_code == 200, (
        f"APPROVED 后 POST /export 应 200，实际 {export_resp.status_code}：{export_resp.text}"
    )
    export_data = export_resp.json()
    assert export_data["assignment_id"] == aid
    assert export_data["export_id"] == f"stub-{aid}"
    assert export_data["status"] == "queued"
    assert "S4" in export_data["note"]  # stub note 应提及 S4

    # 3. DB 直查：review_status / reviewed_by / review_notes
    row = mock_db_session.get(Assignment, aid)
    assert row is not None
    assert row.review_status == KnowledgeReviewStatus.APPROVED, (
        f"DB review_status 应为 APPROVED，实际 {row.review_status}"
    )
    assert row.reviewed_by == 1
    assert row.review_notes == notes_value
    assert row.reviewed_at is not None


# ────────── R6：modified → POST /export 闸门 = 403（D-43-X §5 收口补） ──────────


def test_R6_modified_export_403(
    client: TestClient,
    chapter_with_questions: Any,
) -> None:
    """§7.5 闸门反向用例：review_status=modified 时 POST /export 必须 403。

    补于 D-43-X §5 修正规则 #1 收口审核（A1 反馈，2026-10-13 09:14）：
    brief §192 声明 403 判据「含 pending + modified」，6 用例只覆盖
    pending；补 1 个 modified 用例收口闸门覆盖。
    """
    aid = _create_assignment_pending(client, chapter_with_questions.id)

    # 1. PATCH /review status=modified → 200（先转到 modified 状态）
    patch_resp = client.patch(
        f"/api/v1/assignments/{aid}/review",
        json={"status": "modified", "notes": "R6 验证 modified 状态不能导出"},
        headers={"X-User-Id": "1"},
    )
    assert patch_resp.status_code == 200, (
        f"owner PATCH modified 应 200，实际 {patch_resp.status_code}：{patch_resp.text}"
    )
    assert patch_resp.json()["review"]["review_status"] == "modified", (
        f"review_status 应 'modified'，实际 {patch_resp.json()['review']['review_status']}"
    )

    # 2. POST /export → 403（闸门：review_status=MODIFIED != APPROVED）
    export_resp = client.post(
        f"/api/v1/assignments/{aid}/export",
        headers={"X-User-Id": "1"},
    )
    assert export_resp.status_code == 403, (
        f"modified assignment 导出应 403，实际 {export_resp.status_code}：{export_resp.text}"
    )
    detail = export_resp.json().get("detail", "")
    assert "未通过" in detail or "review" in detail.lower(), (
        f"403 detail 应说明未审原因，实际：{detail}"
    )
