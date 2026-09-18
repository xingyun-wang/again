"""LLM 真值测试（M1-B B.2.2：§7.4 + §7.5 + 真值调用）。

策略：
- 默认 skip（CI / 无真 key）
- 当 DEEPSEEK_API_KEY 真值设置（环境变量非占位）时启用
- chapter extract 真值：mock chapter → 调真 chat → 验证返回结构（key_points /
  difficulties / teaching_suggestions 至少 1 条）+ §7.4 字段 + §7.5 pending
- lesson-plan generate 真值：mock chapter → 调真 chat → 验证 §7.4 + §7.5 字段

判定：
- 响应 status 200/201
- §7.4 字段（ai_generated=true, requires_teacher_review=true, model 非空, generated_at 非空）
- §7.5 字段（review_status=pending, reviewed_by=None）

运行时：
- 跑容器内：需要先注入真 DEEPSEEK_API_KEY 到 .env
- 或 host 端：export DEEPSEEK_API_KEY=sk-xxx 后 pytest tests/test_academic_llm.py -v
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app as build_app


def _has_real_api_key() -> bool:
    """检测环境变量是否为真值（不是 placeholder）。"""
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    return key and key not in ("", "***", "dummy", "sk-replace-me")


# ──────────────────────── 跳过逻辑 ────────────────────────


pytestmark = pytest.mark.skipif(
    not _has_real_api_key(),
    reason="DEEPSEEK_API_KEY 未注入真值（M1-B B.2.2 需要真 key；M0 retro 占位）",
)


def _build_test_client(db_session: Any) -> TestClient:
    """真值测试：不 override get_llm_dep，走真 DeepSeekProvider。"""
    from app.db.session import get_db

    app = build_app()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


# ───────────── 真值：chapter extract ─────────────


def test_real_llm_chapter_extract_returns_structured_fields(
    mock_db_session: Any, mock_chapter: Any
) -> None:
    """真值调用 chapter extract：返回 key_points / difficulties / teaching_suggestions 至少各 1 条。

    不锁 LLM 输出格式细节（LLM 可能返回 1-5 条）；只验长度 ≥ 1 且字符串。
    """
    client = _build_test_client(mock_db_session)
    resp = client.post(
        f"/api/v1/academic/chapters/{mock_chapter.id}/extract",
        json={},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()

    # §7.4
    assert data["ai"]["ai_generated"] is True
    assert data["ai"]["requires_teacher_review"] is True
    assert isinstance(data["ai"]["model"], str) and data["ai"]["model"]
    assert isinstance(data["ai"]["generated_at"], str)
    assert "AI" in data["ai"]["annotation"]

    # §7.5
    assert data["review"]["review_status"] == "pending"

    # 真值：每类至少 1 条
    assert len(data["key_points"]) >= 1
    assert len(data["difficulties"]) >= 1
    assert len(data["teaching_suggestions"]) >= 1
    assert all(isinstance(x, str) and x.strip() for x in data["key_points"])
    assert all(isinstance(x, str) and x.strip() for x in data["difficulties"])
    assert all(isinstance(x, str) and x.strip() for x in data["teaching_suggestions"])

    # DB 写入校验：KnowledgeReview 已创建（pending）
    from sqlalchemy import select

    from app.models import KnowledgeReview, KnowledgeReviewStatus

    s = mock_db_session
    rev = s.execute(
        select(KnowledgeReview).where(KnowledgeReview.chapter_id == mock_chapter.id)
    ).scalar_one()
    assert rev.status == KnowledgeReviewStatus.PENDING


def test_real_llm_chapter_extract_creates_three_subtables(
    mock_db_session: Any, mock_chapter: Any
) -> None:
    """真值调用：extract 后 KeyPoint / Difficulty / TeachingSuggestion 各至少 1 行（source='ai'）。"""
    client = _build_test_client(mock_db_session)
    resp = client.post(
        f"/api/v1/academic/chapters/{mock_chapter.id}/extract",
        json={},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201

    from sqlalchemy import select

    from app.models import Difficulty, KeyPoint, TeachingSuggestion

    s = mock_db_session
    kps = s.execute(
        select(KeyPoint).where(
            KeyPoint.chapter_id == mock_chapter.id, KeyPoint.source == "ai"
        )
    ).scalars().all()
    diffs = s.execute(
        select(Difficulty).where(
            Difficulty.chapter_id == mock_chapter.id, Difficulty.source == "ai"
        )
    ).scalars().all()
    suggs = s.execute(
        select(TeachingSuggestion).where(
            TeachingSuggestion.chapter_id == mock_chapter.id,
            TeachingSuggestion.source == "ai",
        )
    ).scalars().all()

    assert len(kps) >= 1, "KeyPoint 行未创建"
    assert len(diffs) >= 1, "Difficulty 行未创建"
    assert len(suggs) >= 1, "TeachingSuggestion 行未创建"


# ───────────── 真值：lesson-plan generate ─────────────


def test_real_llm_lesson_plan_generate_returns_pending(
    mock_db_session: Any, mock_chapter: Any
) -> None:
    """真值调用 lesson-plan generate：返回 §7.4 + §7.5 字段；DB 创建 LessonPlan(pending)。"""
    client = _build_test_client(mock_db_session)
    resp = client.post(
        "/api/v1/academic/lesson-plans/generate",
        json={
            "chapter_id": mock_chapter.id,
            "duration_minutes": 45,
            "student_count": 50,
            "focus": "地球运动基础概念",
        },
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()

    # §7.4
    assert data["ai"]["ai_generated"] is True
    assert data["ai"]["requires_teacher_review"] is True
    assert isinstance(data["ai"]["model"], str) and data["ai"]["model"]

    # §7.5
    assert data["review"]["review_status"] == "pending"
    assert data["review"]["reviewed_by"] is None

    # content 是字符串且长度合理（LLM 至少输出几句话）
    assert isinstance(data["content"], str)
    assert len(data["content"]) >= 50  # 至少一句话 + 几个段落标签


def test_real_llm_lesson_plan_get_persists_pending_status(
    mock_db_session: Any, mock_chapter: Any
) -> None:
    """真值：lesson-plan 创建后，GET 仍返回 pending（review_status 持久化）。"""
    client = _build_test_client(mock_db_session)
    create = client.post(
        "/api/v1/academic/lesson-plans/generate",
        json={"chapter_id": mock_chapter.id, "duration_minutes": 45},
        headers={"X-User-Id": "1"},
    )
    assert create.status_code == 201
    lp_id = create.json()["id"]

    # GET 后再确认
    get_resp = client.get(
        f"/api/v1/academic/lesson-plans/{lp_id}",
        headers={"X-User-Id": "1"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["review"]["review_status"] == "pending"


def test_real_llm_review_flow_lesson_plan_pending_to_reviewed(
    mock_db_session: Any, mock_chapter: Any
) -> None:
    """真值全流程：lesson-plan generate (pending) → PATCH /review (reviewed)。

    §7.5 流程硬约束端到端测试。
    """
    client = _build_test_client(mock_db_session)
    create = client.post(
        "/api/v1/academic/lesson-plans/generate",
        json={"chapter_id": mock_chapter.id, "duration_minutes": 45},
        headers={"X-User-Id": "1"},
    )
    assert create.status_code == 201
    lp_id = create.json()["id"]
    assert create.json()["review"]["review_status"] == "pending"

    # §7.5：PATCH /review 标记 reviewed
    review_resp = client.patch(
        f"/api/v1/academic/lesson-plans/{lp_id}/review",
        json={"status": "reviewed", "notes": "真值 OK"},
        headers={"X-User-Id": "2"},
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["review"]["review_status"] == "reviewed"
    assert review_resp.json()["review"]["reviewed_by"] == 2
    assert review_resp.json()["review"]["reviewed_at"] is not None

    # GET 确认持久化
    get_resp = client.get(
        f"/api/v1/academic/lesson-plans/{lp_id}",
        headers={"X-User-Id": "1"},
    )
    assert get_resp.json()["review"]["review_status"] == "reviewed"
    assert get_resp.json()["review"]["reviewed_by"] == 2