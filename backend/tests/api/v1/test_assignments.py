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

# A2 修法补充: module level import 所有模型,让 conftest 的 Base.metadata.create_all
# 看到它们(否则 fixture setup 阶段就崩: "no such table: users")
from app.models import (  # noqa: F401
    Assignment,
    AssignmentItem,
    Chapter,
    Question,
    QuestionDifficulty,
    QuestionType,
    User,
)

if TYPE_CHECKING:
    pass


@pytest.fixture()
def client(mock_db_session) -> TestClient:
    """FastAPI TestClient（hermetic：API 与 fixture 用同一 session）。

    A2 fix v3: 极简 app（只挂 assignments_router）+ dependency_overrides[get_db]
    + mock_db_session。

    为什么不走 create_app()：
    - create_app() 拉所有 router + lifespan 链 lifespan 拉模块级 engine（默认 PG URL）
    - lifespan 在 setup 时连不到 PG → 可能阻塞 app 启动
    - 多 router include 会被其他 fixture 干扰（如 get_llm_dep）
    - 极简 app + 单 router + get_db override = 最小副作用路径

    hermetic 保证：override 走 mock_db_session ⇒ API 与 fixture 用同一 session。
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
    mock_db_session, mock_user_system_seed, mock_textbook
):
    """章节 + 100 C + 100 D 池（与 pool fixture 对齐）。"""
    from app.models import Question, QuestionDifficulty, QuestionType

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

    def test_404_chapter_not_found(
        self, client: TestClient, mock_user_system_seed
    ) -> None:
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

    def test_post_cross_user_chapter_404(
        self, client: TestClient, chapter_with_questions, mock_db_session
    ) -> None:
        """A1 pre-fix red: user2 POST with user1's chapter_id → 404（跨用户隔离）。

        Pre-fix: chapter 404 判断之后无 owner 校验 ⇒ user2 拿到 201（存在性预言机 + 跨用户引用污染）。
        Post-fix: chapter 404 之后调 _enforce_owner_or_404(chapter, user_id) ⇒ user2 拿到 404。
        """

        user2 = User(id=2, name="user-2-cross", is_system_owned=False)
        mock_db_session.add(user2)
        mock_db_session.commit()

        r = client.post(
            "/api/v1/assignments",
            json={"chapter_id": chapter_with_questions.id, "tier": "C", "total_count": 10, "seed": 1},
            headers={"X-User-Id": "2"},  # user2; chapter 属 user1
        )
        assert r.status_code == 404, (
            f"Expected 404 (cross-user), got {r.status_code}: {r.text}"
        )

    def test_client_uses_fixture_session_hermetic(
        self, client: TestClient, mock_db_session, mock_user_system_seed, mock_textbook
    ) -> None:
        """A2 pre-fix red: client 与 fixture 用同一 session（hermetic）。

        Pre-fix: client 走模块级 engine（app/db/session.py:25 settings.database_url）
        ≠ fixture mock_db_session（SQLite in-memory）⇒ API 看不到 fixture 创的 chapter。
        Post-fix: dependency_overrides[get_db] = mock_db_session ⇒ 同一 session。

        本地 SQLite 路径（DATABASE_URL=""）验证：
        - Pre-fix: 404（找不到 chapter）
        - Post-fix: 422（找到 chapter 但 C 池不足）— 也是 hermetic 成功证据
        - 本测再加 10 道 C 池题 → 走到 201

        验收：API 能看到 fixture 创的 chapter（从 404 → 422 转变是 hermetic 标志）。
        """

        ch = Chapter(
            textbook_id=mock_textbook.id,
            owner_user_id=mock_user_system_seed.id,
            chapter_number=1,
            title="hermetic-test-chapter",
            content_summary="test",
            extraction_source="detected",
        )
        mock_db_session.add(ch)
        mock_db_session.commit()  # commit 后 ch.id 才有值
        # 给 chapter 加 10 道 C 池题（让 C 档 10 题作业能走到 201）
        for i in range(10):
            q = Question(
                owner_user_id=mock_user_system_seed.id,
                chapter_id=ch.id,
                content=f"hermetic-q-{i}",
                difficulty=QuestionDifficulty.C,
                type=QuestionType.CHOICE,
            )
            mock_db_session.add(q)
        mock_db_session.commit()

        r = client.post(
            "/api/v1/assignments",
            json={"chapter_id": ch.id, "tier": "C", "total_count": 10, "seed": 1},
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 201, (
            f"Expected 201 (hermetic: client sees fixture's chapter + C 池足), "
            f"got {r.status_code}: {r.text}"
        )

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
