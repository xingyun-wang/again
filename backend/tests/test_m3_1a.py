"""M3-1a 题库层第 1 步 后端补齐测试。

覆盖（M3-1a brief §4.4）：
1. GET /textbooks（题库属教师个人资产）
2. POST /chapters/{chapter_id}/knowledge-points（创建 KP）
3. GET /questions 加 knowledge_point_id 过滤
4. POST /questions with points=10.0 + knowledge_point_ids=[1]
5. 0012 迁移 = questions.points + questions.answer_text 两列（PG schema 真值）

回执要点（per brief §5）：
- 4 法核源（不写"我以为"或"已支持"）
- pytest 显式 -e DATABASE_URL=...tiered_homework_test（不污染 dev 库）
"""

from __future__ import annotations

import enum
import sys
import typing

if not hasattr(typing, "Annotated"):
    import typing_extensions

    typing.Annotated = typing_extensions.Annotated  # type: ignore[attr-defined]

if not hasattr(enum, "StrEnum"):
    class _StrEnumShim(str, enum.Enum):  # noqa: UP042
        pass

    enum.StrEnum = _StrEnumShim  # type: ignore[attr-defined]


import pytest

# py3.8 跳过：本测试 py3.11 strict 强制（B2 baseline 同步 test_question_crud.py）
_skip_on_py38 = pytest.mark.skipif(
    sys.version_info < (3, 9),
    reason="B2 baseline: py3.9+ required for Mapped (PEP 585)",
)
pytestmark = _skip_on_py38


def _build_test_client(db_session: object, llm_provider: object) -> object:
    """构造带 DB + LLM 依赖 override 的 TestClient。"""
    from fastapi.testclient import TestClient

    from app.api.v1.routers.academic import get_llm_dep
    from app.db.session import get_db
    from app.main import create_app as build_app

    app = build_app()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_llm_dep] = lambda: llm_provider
    return TestClient(app)


# user_2 fixture：跨用户隔离测试
@pytest.fixture()
def user_2(mock_db_session):  # type: ignore[no-untyped-def]
    from app.models import User

    u = User(id=2, name="user-2", is_system_owned=False)
    mock_db_session.add(u)
    mock_db_session.commit()
    mock_db_session.refresh(u)
    return u


# user_1_kp fixture：M2-A.0 已存在（test_question_crud.py:96），但 pytest
# fixture 解析规则 = 找最近 scope 的文件级 fixture。M2-A.0 测试文件级定义不
# 全局可复用（pytest 文档：fixture 必须在 file 或 conftest 定义）。本测试文件
# 重新定义一份等价 KP（M3-1a brief §1.3 需要）。
@pytest.fixture()
def user_1_kp(mock_db_session, user_1_chapter):  # type: ignore[no-untyped-def]
    from app.models import KnowledgePoint

    kp = KnowledgePoint(
        chapter_id=user_1_chapter.id,
        name="KP-1",
        concept="user_1 KP 概念",
        teaching_order=1,
    )
    mock_db_session.add(kp)
    mock_db_session.commit()
    mock_db_session.refresh(kp)
    return kp


# ─────────────────── 0012 迁移 PG schema 真值证据 ───────────────────


def test_0012_questions_table_has_points_and_answer_text_columns(mock_db_engine):
    """§5 必报项·0012 字段真值证据（PG schema 直接查）。

    用 mock_db_engine fixture 保证 tables 已创建（不依赖上一轮的 fixture 状态）。
    PG 路径：用 SQLAlchemy inspect 查两列存在 + 类型。

    只检查两列 = 严格两列（brief §1.1 + §2.3）。
    """
    from sqlalchemy import inspect

    insp = inspect(mock_db_engine)
    cols = insp.get_columns("questions")
    col_map = {c["name"]: c for c in cols}

    # 1. points 列存在 + numeric(5,1) + NOT NULL
    assert "points" in col_map, "0012 迁移未加 points 列"
    p = col_map["points"]
    assert "NUMERIC" in str(p["type"]).upper() or p["type"].python_type is float, (
        f"points 列类型非 Numeric(5,1)：{p['type']}"
    )
    assert not p["nullable"], "points 必须 NOT NULL"

    # 2. answer_text 列存在 + text + NULL
    assert "answer_text" in col_map, "0012 迁移未加 answer_text 列"
    a = col_map["answer_text"]
    assert "TEXT" in str(a["type"]).upper(), (
        f"answer_text 列类型非 Text：{a['type']}"
    )
    assert a["nullable"], "answer_text 必须 nullable"

    # 3. 严格两列 = 0012 迁移不应已夹带 batch / student / barcode 字段
    #    （这些字段属 0013，brief §2.3 锁）
    for forbidden in ("batch_id", "student_id", "barcode"):
        assert forbidden not in col_map, (
            f"0012 夹带了 {forbidden} 字段（brief §2.3 锁 — 应属 0013）"
        )


# ─────────────────── GET /textbooks ────────────────────────────────


def test_get_textbooks_lists_only_own(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_2: object,
    mock_subject: object,
) -> None:
    """GET /textbooks 仅返当前用户教材（D-29 §1.4 题库个人资产）。"""
    from app.models import Textbook

    # user_1 建 2 本教材
    for i in range(2):
        tb = Textbook(
            name=f"user_1 TB {i}",
            file_path=f"uploads/0/mock-{i}.pdf",
            owner_user_id=user_1.id,
            subject_id=mock_subject.id,
            grade_level=mock_subject.grade_level,
        )
        mock_db_session.add(tb)
    # user_2 建 1 本教材
    tb2 = Textbook(
        name="user_2 TB",
        file_path="uploads/0/mock-u2.pdf",
        owner_user_id=user_2.id,
        subject_id=mock_subject.id,
        grade_level=mock_subject.grade_level,
    )
    mock_db_session.add(tb2)
    mock_db_session.commit()

    client = _build_test_client(mock_db_session, mock_llm_provider)

    # user_1 列：应见 2 本
    resp_1 = client.get("/api/v1/academic/textbooks", headers={"X-User-Id": "1"})
    assert resp_1.status_code == 200, resp_1.text
    body_1 = resp_1.json()
    assert len(body_1) == 2
    titles = [b["title"] for b in body_1]
    assert "user_1 TB 0" in titles
    assert "user_1 TB 1" in titles
    assert "user_2 TB" not in titles

    # user_2 列：应见 1 本
    resp_2 = client.get("/api/v1/academic/textbooks", headers={"X-User-Id": "2"})
    assert resp_2.status_code == 200, resp_2.text
    body_2 = resp_2.json()
    assert len(body_2) == 1
    assert body_2[0]["title"] == "user_2 TB"


def test_get_textbooks_empty_for_new_user(
    mock_db_session: object,
    mock_llm_provider: object,
) -> None:
    """GET /textbooks 新用户（无教材）→ 200 + []。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get("/api/v1/academic/textbooks", headers={"X-User-Id": "99"})
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


def test_get_textbooks_summary_fields(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    mock_subject: object,
) -> None:
    """GET /textbooks 返回 TextbookSummary = id / title / grade / subject 4 字段。"""
    from app.models import Textbook

    tb = Textbook(
        name="人教版地理选择性必修 1",
        file_path="uploads/0/mock-textbook.pdf",
        owner_user_id=user_1.id,
        subject_id=mock_subject.id,
        grade_level=mock_subject.grade_level,
    )
    mock_db_session.add(tb)
    mock_db_session.commit()

    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get("/api/v1/academic/textbooks", headers={"X-User-Id": "1"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    item = body[0]
    # 4 字段
    assert set(item.keys()) >= {"id", "title", "grade", "subject"}
    assert item["title"] == "人教版地理选择性必修 1"
    assert item["grade"] == "senior_high"
    assert item["subject"] == "高中地理"


# ─────────────────── POST /chapters/{id}/knowledge-points ───────────


def test_post_knowledge_point_creates(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_1_chapter: object,
) -> None:
    """POST /chapters/{chapter_id}/knowledge-points 建 KP → 201 + 返回详情。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        f"/api/v1/academic/chapters/{user_1_chapter.id}/knowledge-points",
        json={
            "name": "地球自转",
            "concept": "地球绕自身轴旋转一周，自西向东，约 24 小时",
            "teaching_order": 1,
        },
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "地球自转"
    assert "地球绕自身轴" in body["concept"]
    assert body["teaching_order"] == 1
    assert "id" in body


def test_post_knowledge_point_minimal(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_1_chapter: object,
) -> None:
    """POST KP 只传 name（concept 空 + teaching_order 默认 0）→ 201。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        f"/api/v1/academic/chapters/{user_1_chapter.id}/knowledge-points",
        json={"name": "最小 KP"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "最小 KP"
    assert body["teaching_order"] == 0


def test_post_knowledge_point_empty_name_returns_422(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_1_chapter: object,
) -> None:
    """POST KP name 空字符串 → 422（Pydantic min_length=1 + router 守一手）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        f"/api/v1/academic/chapters/{user_1_chapter.id}/knowledge-points",
        json={"name": ""},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code in (422, 400), resp.text


def test_post_knowledge_point_nonexistent_chapter_returns_404(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
) -> None:
    """POST KP 用不存在的 chapter_id → 404。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/chapters/999999/knowledge-points",
        json={"name": "KP-orphan"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 404, resp.text


def test_post_knowledge_point_cross_user_returns_404(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_2: object,
    user_1_chapter: object,
) -> None:
    """POST KP 用 user_2 在 user_1 的 chapter 下 → 404（D-29 §1.4）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        f"/api/v1/academic/chapters/{user_1_chapter.id}/knowledge-points",
        json={"name": "user_2 试图在 user_1 chapter 下建 KP"},
        headers={"X-User-Id": "2"},
    )
    assert resp.status_code == 404, resp.text
    assert resp.status_code != 403


def test_get_chapter_includes_newly_created_kp(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_1_chapter: object,
) -> None:
    """POST KP 后 GET /chapters/{id} 应见 KP（在 knowledge_points 列表）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)

    # 建 3 个 KP
    created_ids = []
    for i in range(3):
        resp = client.post(
            f"/api/v1/academic/chapters/{user_1_chapter.id}/knowledge-points",
            json={"name": f"KP-{i}", "teaching_order": i},
            headers={"X-User-Id": "1"},
        )
        assert resp.status_code == 201, resp.text
        created_ids.append(resp.json()["id"])

    # GET chapter 验证 KP 列表含 3 个
    resp = client.get(
        f"/api/v1/academic/chapters/{user_1_chapter.id}",
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    kps = body["knowledge_points"]
    assert len(kps) == 3
    kp_ids = {k["id"] for k in kps}
    assert set(created_ids) == kp_ids


# ─────────────────── GET /questions 加 knowledge_point_id 过滤 ──────


def test_create_question_with_points_and_kp(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_1_chapter: object,
    user_1_kp: object,
) -> None:
    """POST /questions with points=10.0 + knowledge_point_ids=[1] → 201 + 返回 + KP 关联。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "地球公转一周是多少天？",
            "difficulty": "C",
            "type": "fill",
            "points": 10.0,
            "answer_text": "365.25 天",
            "knowledge_point_ids": [user_1_kp.id],
        },
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["points"] == 10.0
    assert body["answer_text"] == "365.25 天"
    assert body["knowledge_point_ids"] == [user_1_kp.id]


def test_create_question_default_points_2(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_1_chapter: object,
) -> None:
    """POST /questions 不传 points → 默认 2.0（model default + schema default 双门）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "默认分值测试",
            "difficulty": "D",
            "type": "fill",
        },
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["points"] == 2.0


def test_list_questions_filter_by_knowledge_point_id(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_1_chapter: object,
    user_1_kp: object,
) -> None:
    """GET /questions?knowledge_point_id=X 筛出含 KP X 的题。

    数据集：建 2 题，1 题关联 user_1_kp，另 1 题不关联。
    断言：?knowledge_point_id=user_1_kp.id 仅返关联的那 1 题。
    """
    client = _build_test_client(mock_db_session, mock_llm_provider)

    # 题 1 = 关联 KP
    r1 = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "关联 KP 题",
            "difficulty": "D",
            "type": "fill",
            "knowledge_point_ids": [user_1_kp.id],
        },
        headers={"X-User-Id": "1"},
    )
    assert r1.status_code == 201, r1.text
    q_with_kp_id = r1.json()["id"]

    # 题 2 = 不关联 KP
    r2 = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "不关联 KP 题",
            "difficulty": "C",
            "type": "fill",
        },
        headers={"X-User-Id": "1"},
    )
    assert r2.status_code == 201, r2.text
    q_without_kp_id = r2.json()["id"]

    # 不带 knowledge_point_id → 见 2 题
    resp_all = client.get(
        "/api/v1/academic/questions", headers={"X-User-Id": "1"}
    )
    assert resp_all.status_code == 200, resp_all.text
    body_all = resp_all.json()
    assert body_all["total"] == 2

    # 带 knowledge_point_id → 仅 1 题（只含 KP 那题）
    resp_filter = client.get(
        f"/api/v1/academic/questions?knowledge_point_id={user_1_kp.id}",
        headers={"X-User-Id": "1"},
    )
    assert resp_filter.status_code == 200, resp_filter.text
    body_filter = resp_filter.json()
    assert body_filter["total"] == 1
    assert body_filter["items"][0]["id"] == q_with_kp_id
    assert q_without_kp_id not in [it["id"] for it in body_filter["items"]]


def test_list_questions_filter_by_kp_nonexistent(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_1_chapter: object,
) -> None:
    """GET /questions?knowledge_point_id=9999 → 空列表（不报错）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    # 建 1 题（不关联 KP）
    client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "测试",
            "difficulty": "D",
            "type": "fill",
        },
        headers={"X-User-Id": "1"},
    )
    resp = client.get(
        "/api/v1/academic/questions?knowledge_point_id=9999",
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


# ─────────────────── 路由注册校验 ────────────────────────────────


def test_m3_1a_routes_registered() -> None:
    """M3-1a 新增/修改路由注册校验（4 法核源 · brief §3）。

    期望新增 / 修改 路由：
    - GET /textbooks（新增）
    - POST /chapters/{chapter_id}/knowledge-points（新增）
    - GET /questions 已存在 + knowledge_point_id 参数（修改）
    """
    from app.api.v1.routers.academic import router

    paths = {(r.path, tuple(sorted(r.methods or set()))) for r in router.routes}

    # 1. GET /textbooks（新增）
    assert ("/textbooks", ("GET",)) in paths, "GET /textbooks 未注册"

    # 2. POST /chapters/{chapter_id}/knowledge-points（新增）
    assert (
        "/chapters/{chapter_id}/knowledge-points",
        ("POST",),
    ) in paths, "POST /chapters/{}/knowledge-points 未注册"

    # 3. GET /questions（已存在；knowledge_point_id 参数通过 query 校验）
    assert ("/questions", ("GET",)) in paths, "GET /questions 未注册"
    # 检查 GET /questions 的 params 含 knowledge_point_id
    get_questions_route = None
    for r in router.routes:
        if r.path == "/questions" and "GET" in (r.methods or set()):
            get_questions_route = r
            break
    assert get_questions_route is not None
    param_names = {p.name for p in getattr(get_questions_route, "dependant", None).query_params}
    assert "knowledge_point_id" in param_names, (
        f"GET /questions 缺 knowledge_point_id 参数；当前 params: {param_names}"
    )


# ─────────── 星轨复核 814a334 P2 修补 ───────────
# P2-1：teaching_order 服务端自增
# P2-2：同章重名 → 409


def test_kp_teaching_order_auto_increments(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_1_chapter: object,
) -> None:
    """P2-1：不传 teaching_order → 服务端按本章 max+1 自增（0, 1, 2, 3）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)

    observed = []
    for i in range(4):
        resp = client.post(
            f"/api/v1/academic/chapters/{user_1_chapter.id}/knowledge-points",
            json={"name": f"自增KP-{i}"},  # 故意不传 teaching_order
            headers={"X-User-Id": "1"},
        )
        assert resp.status_code == 201, resp.text
        observed.append(resp.json()["teaching_order"])

    print(f"\n[P2-1] teaching_order 自增序列 = {observed}")
    assert observed == [0, 1, 2, 3], f"自增序列应为 [0,1,2,3]，实际 {observed}"


def test_kp_duplicate_name_in_same_chapter_returns_409(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_1_chapter: object,
) -> None:
    """P2-2：同章同名 → 409；不同章同名 → 201（不跨章查重）。"""
    from app.models import Chapter

    client = _build_test_client(mock_db_session, mock_llm_provider)
    name = "大气的组成"

    # 另一个 chapter（同 textbook，chapter_number=2；conftest mock_chapter 是
    # chapter_number=1，同 textbook 下会撞 uq_chapters_textbook_id_chapter_number）
    other_chapter = Chapter(
        textbook_id=user_1_chapter.textbook_id,
        owner_user_id=user_1_chapter.owner_user_id,
        chapter_number=2,
        title="user_1 第二章",
        content_summary="user_1 内容",
        extraction_source="detected",
    )
    mock_db_session.add(other_chapter)
    mock_db_session.commit()
    mock_db_session.refresh(other_chapter)

    # 1. 同章第一次 → 201
    first = client.post(
        f"/api/v1/academic/chapters/{user_1_chapter.id}/knowledge-points",
        json={"name": name},
        headers={"X-User-Id": "1"},
    )
    assert first.status_code == 201, first.text
    first_id = first.json()["id"]

    # 2. 同章同名第二次 → 409，detail 含该名字
    dup = client.post(
        f"/api/v1/academic/chapters/{user_1_chapter.id}/knowledge-points",
        json={"name": name},
        headers={"X-User-Id": "1"},
    )
    print(f"\n[P2-2] 同章重名 → status={dup.status_code}, body={dup.json()}")
    assert dup.status_code == 409, f"同章重名应 409，实际 {dup.status_code}: {dup.text}"
    # 全局 error handler（app/core/errors.py）把 detail 改写成 message/error_code
    body = dup.json()
    detail = body["message"]
    assert name in detail, f"409 message 应含知识点名，实际: {detail}"
    assert str(first_id) in detail, f"409 message 应含已存在 KP id，实际: {detail}"

    # 3. 另一个 chapter 同名 → 201（不跨章查重）
    other = client.post(
        f"/api/v1/academic/chapters/{other_chapter.id}/knowledge-points",
        json={"name": name},
        headers={"X-User-Id": "1"},
    )
    print(f"[P2-2] 跨章同名 → status={other.status_code}")
    assert other.status_code == 201, f"跨章同名应 201，实际 {other.status_code}: {other.text}"
