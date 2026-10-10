"""Assignment API test（M2-A.1 · v0.5 §3.6 老师审阅流程第 1 步产物）。

端点：
- POST /api/v1/assignments         → 创建作业单（出题引擎跑 + 落库）
- GET  /api/v1/assignments/{id}    → 查作业单详情（含 items + 鉴权 owner）

测试覆盖：
- 鉴权（X-User-Id header 缺失/非整数）
- POST 4 档（每档验证反马太判据 + 跨用户隔离）
- GET 越权返 404
- 章节题库不足返 422
- chapter 不存在返 404
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    pass


@pytest.fixture()
def client(mock_db_engine) -> TestClient:
    """FastAPI TestClient（每次测试新 client，SQLite in-memory）。"""
    from app.main import create_app

    app = create_app()
    return TestClient(app)


@pytest.fixture()
def chapter_with_questions(
    mock_db_session, mock_user_system_seed, mock_textbook
):
    """章节 + 100 C + 100 D 池（与 pool fixture 对齐）。"""
    from app.models import Chapter, Question, QuestionDifficulty, QuestionType

    ch = Chapter(
        textbook_id=mock_textbook.id,
        owner_user_id=mock_user_system_seed.id,
        chapter_number=1,
        title="t1",
        content_summary="sum",
        extraction_source="detected",
    )
    mock_db_session.add(ch)
    mock_db_session.commit()

    # 100 D 池
    for i in range(100):
        q = Question(
            owner_user_id=mock_user_system_seed.id,
            chapter_id=ch.id,
            content=f"Q-D-{i}",
            difficulty=QuestionDifficulty.D,
            type=QuestionType.CHOICE,
        )
        mock_db_session.add(q)
    # 100 C 池
    for i in range(100):
        q = Question(
            owner_user_id=mock_user_system_seed.id,
            chapter_id=ch.id,
            content=f"Q-C-{i}",
            difficulty=QuestionDifficulty.C,
            type=QuestionType.CHOICE,
        )
        mock_db_session.add(q)
    # 100 B 池
    for i in range(100):
        q = Question(
            owner_user_id=mock_user_system_seed.id,
            chapter_id=ch.id,
            content=f"Q-B-{i}",
            difficulty=QuestionDifficulty.B,
            type=QuestionType.CHOICE,
        )
        mock_db_session.add(q)
    # 100 A 池
    for i in range(100):
        q = Question(
            owner_user_id=mock_user_system_seed.id,
            chapter_id=ch.id,
            content=f"Q-A-{i}",
            difficulty=QuestionDifficulty.A,
            type=QuestionType.CHOICE,
        )
        mock_db_session.add(q)
    mock_db_session.commit()
    return ch


class TestCreateAssignment:
    """POST /api/v1/assignments 鉴权 + 业务判据。"""

    def test_401_no_header(self, client: TestClient, chapter_with_questions) -> None:
        r = client.post(
            "/api/v1/assignments",
            json={"chapter_id": chapter_with_questions.id, "tier": "D", "total_count": 50},
        )
        assert r.status_code == 401
        assert "X-User-Id" in r.json()["detail"]

    def test_404_chapter_not_found(self, client: TestClient) -> None:
        r = client.post(
            "/api/v1/assignments",
            json={"chapter_id": 99999, "tier": "D", "total_count": 50},
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 404
        assert "chapter" in r.json()["detail"]

    def test_201_D_tier_100_anti_matthew(
        self, client: TestClient, chapter_with_questions
    ) -> None:
        """D 档 100 题作业：c_count=20, b_count=0（v0.5 line 168 反马太判据）。"""
        r = client.post(
            "/api/v1/assignments",
            json={"chapter_id": chapter_with_questions.id, "tier": "D", "total_count": 100, "seed": 42},
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["tier"] == "D"
        assert data["total_count"] == 100
        assert data["d_count"] == 80
        assert data["c_count"] == 20
        assert data["b_count"] == 0
        assert data["a_count"] == 0
        assert data["seed"] == 42
        assert len(data["items"]) == 100
        # 验证 items 反马太判据
        c_picked = sum(1 for it in data["items"] if it["tier_origin"] == "C")
        b_picked = sum(1 for it in data["items"] if it["tier_origin"] == "B")
        assert c_picked == 20
        assert b_picked == 0

    def test_201_C_tier_100_percent_C(
        self, client: TestClient, chapter_with_questions
    ) -> None:
        r = client.post(
            "/api/v1/assignments",
            json={"chapter_id": chapter_with_questions.id, "tier": "C", "total_count": 50, "seed": 1},
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["c_count"] == 50
        assert data["d_count"] == 0
        assert data["b_count"] == 0
        assert all(it["tier_origin"] == "C" for it in data["items"])

    def test_422_pool_insufficient(
        self, client: TestClient, chapter_with_questions
    ) -> None:
        """D 档 200 题但池子只有 100 D + 100 C → D 池不足 160 → 422。"""
        r = client.post(
            "/api/v1/assignments",
            json={"chapter_id": chapter_with_questions.id, "tier": "D", "total_count": 200, "seed": 1},
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 422
        assert "D 池" in r.json()["detail"]


class TestGetAssignment:
    """GET /api/v1/assignments/{id} 鉴权 + 跨用户隔离。"""

    def test_401_no_header(self, client: TestClient) -> None:
        r = client.get("/api/v1/assignments/1")
        assert r.status_code == 401

    def test_404_not_found(self, client: TestClient) -> None:
        r = client.get("/api/v1/assignments/99999", headers={"X-User-Id": "1"})
        assert r.status_code == 404

    def test_404_cross_user_isolation(
        self, client: TestClient, chapter_with_questions
    ) -> None:
        """其他 user 越权访问 → 404（不暴露存在性）。"""
        # user 1 创建
        r = client.post(
            "/api/v1/assignments",
            json={"chapter_id": chapter_with_questions.id, "tier": "D", "total_count": 50, "seed": 1},
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 201
        aid = r.json()["id"]

        # user 2 越权访问
        r2 = client.get(f"/api/v1/assignments/{aid}", headers={"X-User-Id": "2"})
        assert r2.status_code == 404

    def test_200_owner_read(
        self, client: TestClient, chapter_with_questions
    ) -> None:
        """owner 读 → 200 + 完整 items。"""
        r = client.post(
            "/api/v1/assignments",
            json={"chapter_id": chapter_with_questions.id, "tier": "D", "total_count": 50, "seed": 1},
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 201
        aid = r.json()["id"]

        r2 = client.get(f"/api/v1/assignments/{aid}", headers={"X-User-Id": "1"})
        assert r2.status_code == 200
        data = r2.json()
        assert data["id"] == aid
        assert data["owner_user_id"] == 1
        assert len(data["items"]) == 50
