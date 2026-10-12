"""Students API test（M2-S2 brief §四 / §八.2）。

端点：
- GET  /api/v1/students           → 本老师本班学生列表
- GET  /api/v1/students/{id}      → 单学生详情（跨用户返 404）
- PATCH /api/v1/students/{id}     → 改 current_tier（manual override + audit）

测试覆盖：
- 鉴权（X-User-Id header 缺失/非正整数）
- 200 happy path（list / detail / patch）
- 跨用户隔离（list 看不到他人学生；detail 他人学生 404；patch 他人学生 404）
- 422：current_tier 越界（Pydantic pattern check）+ extra 字段拒绝
- audit 字段：PATCH 后 tier_changed_by_user_id + tier_changed_at 非 NULL

注意：与当前 schema 对齐（StudentListResponse.students 字段；
PATCH 响应是 StudentTierUpdateResponse 含 old/new/student_id/audit 字段）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

# A2 fix: module-level import 所有模型
from app.models import (  # noqa: F401
    Class,
    GradeLevel,
    Student,
    Subject,
    Tier,
    User,
)

if TYPE_CHECKING:
    pass


@pytest.fixture()
def client(mock_db_session) -> TestClient:
    """FastAPI TestClient（hermetic：API 与 fixture 用同一 session）。

    极简 app（只挂 students_router）+ dependency_overrides[get_db]
    + mock_db_session。
    """
    from fastapi import FastAPI

    from app.api.v1.routers.students import router as students_router
    from app.db.session import get_db

    app = FastAPI()

    def _override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.include_router(students_router, prefix="/api/v1/students")
    return TestClient(app)


@pytest.fixture()
def seed_class_with_student(mock_db_session, mock_user_system_seed, mock_subject):
    """user1 的 Class + 1 个 D 档 Student。"""
    cls = Class(
        name="高三一班",
        grade_level=GradeLevel.SENIOR_HIGH,
        subject_id=mock_subject.id,
    )
    mock_db_session.add(cls)
    mock_db_session.commit()

    stu = Student(
        name="李四",
        class_id=cls.id,
        grade_level=GradeLevel.SENIOR_HIGH,
        current_tier=Tier.D,
    )
    mock_db_session.add(stu)
    mock_db_session.commit()
    mock_db_session.refresh(cls)
    mock_db_session.refresh(stu)
    return {"class": cls, "student": stu}


@pytest.fixture()
def user_2(mock_db_session):
    """id=2 的 user2（idempotent fixture-style 创 user）。"""
    existing = mock_db_session.get(User, 2)
    if existing is not None:
        return existing
    u = User(id=2, name="user-2", is_system_owned=False)
    mock_db_session.add(u)
    mock_db_session.commit()
    mock_db_session.refresh(u)
    return u


# ──────────────────────────── GET /students ────────────────────────────


class TestListStudents:
    """GET /api/v1/students 鉴权 + 跨用户隔离。"""

    def test_401_no_header(self, client: TestClient) -> None:
        r = client.get("/api/v1/students")
        assert r.status_code == 401
        assert "X-User-Id" in r.json()["detail"]

    def test_401_non_positive_header(self, client: TestClient) -> None:
        """X-User-Id 必须是正整数。"""
        r = client.get("/api/v1/students", headers={"X-User-Id": "0"})
        assert r.status_code == 401

    def test_200_list_own_class_students(
        self, client: TestClient, seed_class_with_student, mock_user_system_seed
    ) -> None:
        """happy path: 老师拿到本班学生列表（含 1 个 D 档）。"""
        r = client.get("/api/v1/students", headers={"X-User-Id": "1"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "students" in data
        assert len(data["students"]) == 1
        assert data["students"][0]["name"] == "李四"
        assert data["students"][0]["current_tier"] == "D"
        # 持久化前 audit 字段为 NULL
        assert data["students"][0]["tier_changed_by_user_id"] is None
        assert data["students"][0]["tier_changed_at"] is None

    def test_200_empty_list_for_user_with_no_subjects(
        self, client: TestClient, user_2
    ) -> None:
        """user2 没学科 → 空列表（不 404）。"""
        r = client.get("/api/v1/students", headers={"X-User-Id": "2"})
        assert r.status_code == 200
        assert r.json() == {"students": []}

    def test_list_students_cross_teacher_isolated(
        self, client: TestClient, seed_class_with_student, user_2
    ) -> None:
        """反向: user2 GET → 看不到 user1 的学生（list 只返 user2 自己班）。"""
        r = client.get("/api/v1/students", headers={"X-User-Id": "2"})
        assert r.status_code == 200
        data = r.json()
        # user2 没学科/班级/学生 → 空列表
        assert data["students"] == []


# ──────────────────────────── GET /students/{id} ────────────────────────────


class TestGetStudent:
    """GET /api/v1/students/{id} 鉴权 + 跨用户隔离。"""

    def test_401_no_header(
        self, client: TestClient, seed_class_with_student
    ) -> None:
        r = client.get("/api/v1/students/1")
        assert r.status_code == 401

    def test_200_owner_read(
        self, client: TestClient, seed_class_with_student, mock_user_system_seed
    ) -> None:
        stu = seed_class_with_student["student"]
        r = client.get(
            f"/api/v1/students/{stu.id}", headers={"X-User-Id": "1"}
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["id"] == stu.id
        assert data["name"] == "李四"
        assert data["current_tier"] == "D"
        assert data["tier_changed_by_user_id"] is None
        assert data["tier_changed_at"] is None

    def test_404_not_found(self, client: TestClient, mock_user_system_seed) -> None:
        r = client.get(
            "/api/v1/students/99999", headers={"X-User-Id": "1"}
        )
        assert r.status_code == 404

    def test_404_cross_teacher(
        self, client: TestClient, seed_class_with_student, user_2
    ) -> None:
        """反向: user2 读 user1 的学生 → 404（不暴露存在性）。"""
        stu = seed_class_with_student["student"]
        r = client.get(
            f"/api/v1/students/{stu.id}", headers={"X-User-Id": "2"}
        )
        assert r.status_code == 404


# ──────────────────────────── PATCH /students/{id} ────────────────────────────


class TestPatchStudentTier:
    """PATCH /api/v1/students/{id} 改 current_tier + audit 字段。

    响应是 StudentTierUpdateResponse（old/new/student_id/audit 字段），
    不是 StudentRead。DB 持久化通过后续 GET /students/{id} 校验。
    """

    def test_401_no_header(
        self, client: TestClient, seed_class_with_student
    ) -> None:
        r = client.patch(
            "/api/v1/students/1", json={"current_tier": "A"}
        )
        assert r.status_code == 401

    def test_200_patch_tier_success(
        self, client: TestClient, seed_class_with_student, mock_user_system_seed
    ) -> None:
        """happy path: D→A，DB 字段更新 + audit 写入。"""
        stu = seed_class_with_student["student"]
        r = client.patch(
            f"/api/v1/students/{stu.id}",
            json={"current_tier": "A"},
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # StudentTierUpdateResponse 字段
        assert data["old"] == "D"
        assert data["new"] == "A"
        assert data["student_id"] == stu.id
        assert data["tier_changed_by_user_id"] == 1
        assert data["tier_changed_at"] is not None

        # DB 持久化校验（通过 GET /students/{id} 读 StudentRead）
        refreshed = client.get(
            f"/api/v1/students/{stu.id}", headers={"X-User-Id": "1"}
        )
        assert refreshed.status_code == 200
        assert refreshed.json()["current_tier"] == "A"
        assert refreshed.json()["tier_changed_by_user_id"] == 1
        assert refreshed.json()["tier_changed_at"] is not None

    def test_422_invalid_tier_value(
        self, client: TestClient, seed_class_with_student, mock_user_system_seed
    ) -> None:
        """反向: current_tier 非 D/C/B/A → 422（Pydantic pattern check）。"""
        stu = seed_class_with_student["student"]
        r = client.patch(
            f"/api/v1/students/{stu.id}",
            json={"current_tier": "X"},
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 422

    def test_404_cross_teacher(
        self, client: TestClient, seed_class_with_student, user_2
    ) -> None:
        """反向: user2 PATCH user1 的学生 → 404。"""
        stu = seed_class_with_student["student"]
        r = client.patch(
            f"/api/v1/students/{stu.id}",
            json={"current_tier": "A"},
            headers={"X-User-Id": "2"},
        )
        assert r.status_code == 404
        # DB 未被改
        s = seed_class_with_student["student"]
        assert s.current_tier == Tier.D
        assert s.tier_changed_by_user_id is None

    def test_404_nonexistent_student(
        self, client: TestClient, mock_user_system_seed
    ) -> None:
        r = client.patch(
            "/api/v1/students/99999",
            json={"current_tier": "A"},
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 404

    def test_422_extra_field_rejected(
        self, client: TestClient, seed_class_with_student, mock_user_system_seed
    ) -> None:
        """extra='forbid': PATCH body 多字段 → 422。"""
        stu = seed_class_with_student["student"]
        r = client.patch(
            f"/api/v1/students/{stu.id}",
            json={"current_tier": "A", "name": "新名字"},
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 422
