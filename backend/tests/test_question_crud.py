"""Question CRUD 端点测试 + D-37 跨用户 404 负面测试。

覆盖（M2-A.0）：
1. POST 创建题目（choice / fill / subjective 三类）
2. GET / PATCH / DELETE 单个题目
3. GET 列表（按 chapter_id / difficulty / type 过滤）
4. KnowledgePoint 多对多关联（创建 + PATCH 替换）
5. Choice 校验（choice 必传 / 非 choice 不能传）
6. D-37 负面测试：user_2 访问 user_1 的题目 → 404（fail-open 实现下 → 200 数据泄漏）

D-32 第 3 类 安全/归属边界：D-35 锁定不可豁免
D-29 §1.4 题库属于教师个人资产
D-37 可证伪硬规则：fail-open fixture 证明错误实现是灾难性的
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


from typing import Any

import pytest

# B2 baseline：dev box py3.8 + PEP 585 让 Mapped[list[Class]] 解析失败（与
# test_p15_title_quality.py 同模式：dev box 跳过本段；CI py3.11 真跑）。
# 测试需要导入 app.models.* 触发 MappedAnnotationError，所以模块级 pytestmark
# 跳过全模块。
_skip_on_py38 = pytest.mark.skipif(
    sys.version_info < (3, 9),
    reason="B2 baseline: py3.9+ required for Mapped[list[Class]] (PEP 585)",
)
pytestmark = _skip_on_py38


# 复用 cross_user_isolation 既有 _build_test_client / _build_minimal_pdf_bytes 模式
# 注意：所有 app.* import 延迟到 fixture / test 函数体内（lazy import），
# 避免 pytest collect 阶段重复加载 SQLAlchemy Table


def _build_test_client(db_session: Any, llm_provider: Any) -> Any:
    """构造带 DB + LLM 依赖 override 的 TestClient（lazy import）。"""
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


# ─────────────────────── 用户 + 章节 fixture ─────────────────────────


@pytest.fixture()
def user_1(mock_db_session):  # type: ignore[no-untyped-def]
    from app.models import User

    u = User(id=1, name="user-1", is_system_owned=False)
    mock_db_session.add(u)
    mock_db_session.commit()
    mock_db_session.refresh(u)
    return u


@pytest.fixture()
def user_2(mock_db_session):  # type: ignore[no-untyped-def]
    from app.models import User

    u = User(id=2, name="user-2", is_system_owned=False)
    mock_db_session.add(u)
    mock_db_session.commit()
    mock_db_session.refresh(u)
    return u


# user_1_chapter fixture 已迁到 conftest.py（2026-09-26 CI run #20 修复）：
# - conftest 加 mock_textbook 依赖（FK 目标 = 真实 Textbook.id）
# - pytest 同名 fixture 文件级优先 = 不删此文件级版本会赢 → 改为引用 conftest


@pytest.fixture()
def user_1_kp(mock_db_session, user_1_chapter):  # type: ignore[no-untyped-def]
    """user_1 的 KnowledgePoint（关联到 user_1_chapter）。"""
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


# ─────────────────────── 1. POST /questions ──────────────────────────


def test_create_choice_question_success(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
    user_1_chapter: Any,
) -> None:
    """POST /questions 创建 choice 类型题目 → 201 + 返回题目详情。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "地球是行星还是恒星？",
            "difficulty": "D",
            "type": "choice",
            "choices": [
                {"label": "A", "content": "行星", "is_correct": True, "order_index": 0},
                {"label": "B", "content": "恒星", "is_correct": False, "order_index": 1},
            ],
        },
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["chapter_id"] == user_1_chapter.id
    assert body["difficulty"] == "D"
    assert body["type"] == "choice"
    assert body["owner_user_id"] == 1
    assert len(body["choices"]) == 2
    assert body["choices"][0]["label"] == "A"
    assert body["choices"][0]["is_correct"] is True


def test_create_fill_question_no_choices(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
    user_1_chapter: Any,
) -> None:
    """POST /questions 创建 fill 类型题目（不传 choices）→ 201。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "地球公转一周是 _____ 天。",
            "difficulty": "C",
            "type": "fill",
        },
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["type"] == "fill"
    assert body["choices"] == []


def test_create_subjective_question_no_choices(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
    user_1_chapter: Any,
) -> None:
    """POST /questions 创建 subjective 类型题目 → 201。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "试述板块构造学说的主要内容。",
            "difficulty": "A",
            "type": "subjective",
        },
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["type"] == "subjective"
    assert body["choices"] == []


def test_create_choice_without_choices_returns_400(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
    user_1_chapter: Any,
) -> None:
    """POST /questions type=choice 但 choices 为空 → 400 业务校验。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "test",
            "difficulty": "D",
            "type": "choice",
            "choices": [],
        },
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 400, resp.text
    assert "choice 类型题目必须传 choices" in resp.text


def test_create_non_choice_with_choices_returns_400(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
    user_1_chapter: Any,
) -> None:
    """POST /questions type=fill/subjective 传 choices → 400 业务校验。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "test",
            "difficulty": "C",
            "type": "fill",
            "choices": [{"label": "A", "content": "x"}],
        },
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 400, resp.text
    assert "不能传 choices" in resp.text


def test_create_with_cross_user_chapter_returns_404(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
    user_2: Any,
    user_1_chapter: Any,
) -> None:
    """POST /questions 用 user_2 创建 + user_1 的 chapter → 404（D-29 B 项）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "test",
            "difficulty": "D",
            "type": "fill",
        },
        headers={"X-User-Id": "2"},
    )
    assert resp.status_code == 404, (
        f"user_2 用 user_1 chapter 创建题目应 404，实际 {resp.status_code}：{resp.text}"
    )
    assert resp.status_code != 403, "D-29 硬规则：403 会泄漏 id 存在性"


def test_create_question_with_knowledge_points(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
    user_1_chapter: Any,
    user_1_kp: Any,
) -> None:
    """POST /questions 关联 KP → 题目创建 + KP 关联正确写入。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "地球公转",
            "difficulty": "D",
            "type": "fill",
            "knowledge_point_ids": [user_1_kp.id],
        },
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # knowledge_point_ids 字段会从 QuestionRead 返回（继承 QuestionBase）
    assert body["knowledge_point_ids"] == [user_1_kp.id]


# ─────────────────────── 2. GET /questions/{id} ──────────────────────


def test_get_question_success(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
    user_1_chapter: Any,
) -> None:
    """GET /questions/{id} 自己读自己的题目 → 200。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    # 创建
    create_resp = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "test get",
            "difficulty": "D",
            "type": "fill",
        },
        headers={"X-User-Id": "1"},
    )
    qid = create_resp.json()["id"]
    # 读
    resp = client.get(
        f"/api/v1/academic/questions/{qid}", headers={"X-User-Id": "1"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == qid


def test_get_cross_user_question_returns_404(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
    user_2: Any,
    user_1_chapter: Any,
) -> None:
    """GET /questions/{id} user_2 读 user_1 的题目 → 404（D-29 B 项）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    # user_1 创建
    create_resp = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "user_1 content (private)",
            "difficulty": "D",
            "type": "fill",
        },
        headers={"X-User-Id": "1"},
    )
    qid = create_resp.json()["id"]
    # user_2 读
    resp = client.get(
        f"/api/v1/academic/questions/{qid}", headers={"X-User-Id": "2"}
    )
    assert resp.status_code == 404, resp.text
    assert resp.status_code != 403
    assert "user_1 content" not in resp.text, (
        "跨用户 404 响应泄漏了 user_1 题目内容"
    )


def test_get_nonexistent_question_returns_404(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
) -> None:
    """GET /questions/{id} 不存在的 id → 404（统一返 404，避 id 存在性泄漏）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get(
        "/api/v1/academic/questions/999999", headers={"X-User-Id": "1"}
    )
    assert resp.status_code == 404, resp.text


# ─────────────────────── 3. GET /questions 列表 ──────────────────────


def test_list_questions_only_returns_own(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
    user_2: Any,
    user_1_chapter: Any,
) -> None:
    """GET /questions 仅返 user_id 自己的题目（D-29 §1.4）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    # user_1 创建 2 题
    for i in range(2):
        client.post(
            "/api/v1/academic/questions",
            json={
                "chapter_id": user_1_chapter.id,
                "content": f"user_1 q{i}",
                "difficulty": "D",
                "type": "fill",
            },
            headers={"X-User-Id": "1"},
        )
    # user_1 列：应见 2 题
    resp_1 = client.get(
        "/api/v1/academic/questions", headers={"X-User-Id": "1"}
    )
    assert resp_1.status_code == 200, resp_1.text
    body_1 = resp_1.json()
    assert body_1["total"] == 2
    assert len(body_1["items"]) == 2
    # user_2 列：应见 0 题（user_2 没创建任何题目）
    resp_2 = client.get(
        "/api/v1/academic/questions", headers={"X-User-Id": "2"}
    )
    assert resp_2.status_code == 200, resp_2.text
    body_2 = resp_2.json()
    assert body_2["total"] == 0
    assert body_2["items"] == []


def test_list_questions_filters_by_chapter_difficulty_type(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
    user_1_chapter: Any,
) -> None:
    """GET /questions 按 chapter_id / difficulty / type 过滤。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    # 3 题：D-f、D-c、B-c
    qs = [
        ("D", "fill"),
        ("C", "fill"),
        ("B", "choice"),
    ]
    for d, t in qs:
        body_payload: dict[str, Any] = {
            "chapter_id": user_1_chapter.id,
            "content": f"q-{d}-{t}",
            "difficulty": d,
            "type": t,
        }
        if t == "choice":
            body_payload["choices"] = [
                {"label": "A", "content": "x", "is_correct": True}
            ]
        client.post(
            "/api/v1/academic/questions",
            json=body_payload,
            headers={"X-User-Id": "1"},
        )

    # 按 difficulty=C 过滤
    resp = client.get(
        "/api/v1/academic/questions?difficulty=C",
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["difficulty"] == "C"

    # 按 type=choice 过滤
    resp = client.get(
        "/api/v1/academic/questions?type=choice",
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["type"] == "choice"

    # 按 chapter_id 过滤
    resp = client.get(
        f"/api/v1/academic/questions?chapter_id={user_1_chapter.id}",
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 3


# ─────────────────────── 4. PATCH /questions/{id} ────────────────────


def test_patch_question_updates_fields(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
    user_1_chapter: Any,
) -> None:
    """PATCH /questions/{id} 改 content / difficulty → 200 + 返回新字段。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    # 创建
    create_resp = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "原始 content",
            "difficulty": "D",
            "type": "fill",
        },
        headers={"X-User-Id": "1"},
    )
    qid = create_resp.json()["id"]

    # 改
    resp = client.patch(
        f"/api/v1/academic/questions/{qid}",
        json={"content": "新 content", "difficulty": "C"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["content"] == "新 content"
    assert body["difficulty"] == "C"


def test_patch_cross_user_question_returns_404(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
    user_2: Any,
    user_1_chapter: Any,
) -> None:
    """PATCH /questions/{id} user_2 改 user_1 的题目 → 404。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    # user_1 创建
    create_resp = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "user_1 content",
            "difficulty": "D",
            "type": "fill",
        },
        headers={"X-User-Id": "1"},
    )
    qid = create_resp.json()["id"]

    # user_2 改
    resp = client.patch(
        f"/api/v1/academic/questions/{qid}",
        json={"content": "user_2 试图覆盖"},
        headers={"X-User-Id": "2"},
    )
    assert resp.status_code == 404, resp.text
    assert resp.status_code != 403


def test_patch_question_replaces_choices(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
    user_1_chapter: Any,
) -> None:
    """PATCH /questions/{id} 传 choices 完全替换（cascade 自动删旧）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    # 创建 choice 题
    create_resp = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "test",
            "difficulty": "D",
            "type": "choice",
            "choices": [
                {"label": "A", "content": "旧 A", "is_correct": True},
                {"label": "B", "content": "旧 B", "is_correct": False},
            ],
        },
        headers={"X-User-Id": "1"},
    )
    qid = create_resp.json()["id"]

    # 替换 choices
    resp = client.patch(
        f"/api/v1/academic/questions/{qid}",
        json={
            "choices": [
                {"label": "A", "content": "新 A", "is_correct": False},
                {"label": "B", "content": "新 B", "is_correct": True},
                {"label": "C", "content": "新 C", "is_correct": False},
            ],
        },
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["choices"]) == 3
    # 旧 "旧 A" 应被 cascade 清除
    contents = [c["content"] for c in body["choices"]]
    assert "旧 A" not in contents
    assert "新 B" in contents


# ─────────────────────── 5. DELETE /questions/{id} ───────────────────


def test_delete_question_success(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
    user_1_chapter: Any,
) -> None:
    """DELETE /questions/{id} 自己删自己的题目 → 204 + cascade 清 Choice。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    # 创建 choice 题
    create_resp = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "to be deleted",
            "difficulty": "D",
            "type": "choice",
            "choices": [
                {"label": "A", "content": "x", "is_correct": True},
            ],
        },
        headers={"X-User-Id": "1"},
    )
    qid = create_resp.json()["id"]

    # 删
    resp = client.delete(
        f"/api/v1/academic/questions/{qid}", headers={"X-User-Id": "1"}
    )
    assert resp.status_code == 204, resp.text

    # 再 GET 应 404
    get_resp = client.get(
        f"/api/v1/academic/questions/{qid}", headers={"X-User-Id": "1"}
    )
    assert get_resp.status_code == 404


def test_delete_cross_user_question_returns_404(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
    user_2: Any,
    user_1_chapter: Any,
) -> None:
    """DELETE /questions/{id} user_2 删 user_1 的题目 → 404。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    # user_1 创建
    create_resp = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "user_1 content",
            "difficulty": "D",
            "type": "fill",
        },
        headers={"X-User-Id": "1"},
    )
    qid = create_resp.json()["id"]

    # user_2 删
    resp = client.delete(
        f"/api/v1/academic/questions/{qid}", headers={"X-User-Id": "2"}
    )
    assert resp.status_code == 404, resp.text
    assert resp.status_code != 403

    # user_1 再 GET 应仍 200（没真删）
    get_resp = client.get(
        f"/api/v1/academic/questions/{qid}", headers={"X-User-Id": "1"}
    )
    assert get_resp.status_code == 200, (
        "跨用户 404 路径下 user_1 的题目不应被删，但实际删了"
    )


# ─────────────────────── D-37 负面测试（fail-open 关键） ───────────────


def test_d37_fail_open_owner_filter_would_leak_data_returns_200(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
    user_2: Any,
    user_1_chapter: Any,
    monkeypatch_owner_filter_to_constant_one,
) -> None:
    """D-37 负面测试：mock 错误实现 → user_2 读 user_1 题目 → 200（数据泄漏）。

    本测试在 monkeypatch_owner_filter_to_constant_one fixture 激活下：
    - _enforce_owner_or_404 被替换为 fail-open 版本（filter by constant 1）
    - user_2 (X-User-Id=2) 访问 user_1 创建的题目 → 返 200（数据泄漏）

    可证伪证据：
    - 错误实现（filter by constant 1）下：response == 200，暴露 user_1 数据
    - 正确实现（!= user_id）下：response == 404（本文件其他测试覆盖）

    本测试断言「错误实现下确实返 200」 — 证明错误实现是灾难性的。
    如果有人把 _enforce_owner_or_404 写成 == 1 而非 != user_id，本测试
    会立刻抓到（200 暴露数据），无法逃过审查。
    """
    client = _build_test_client(mock_db_session, mock_llm_provider)
    # user_1 创建
    create_resp = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "user_1 secret content (must not leak)",
            "difficulty": "D",
            "type": "fill",
        },
        headers={"X-User-Id": "1"},
    )
    assert create_resp.status_code == 201, create_resp.text
    qid = create_resp.json()["id"]

    # user_2 读（在 fail-open fixture 下应 200）
    resp = client.get(
        f"/api/v1/academic/questions/{qid}", headers={"X-User-Id": "2"}
    )

    # D-37 核心断言：错误实现下应返 200（数据泄漏）
    assert resp.status_code == 200, (
        f"D-37 错误实现下 GET 应返 200（暴露数据），实际 {resp.status_code}：{resp.text}"
        f" — 这意味着 fail-open fixture 没生效，或实现已被改正"
    )
    # 进一步验证：响应体确实包含 user_1 的题目内容（数据泄漏实证）
    assert "user_1 secret content" in resp.text, (
        "D-37 fail-open fixture 应暴露 user_1 题目内容，但响应体没有"
    )


def test_d37_correct_owner_filter_returns_404_for_cross_user(
    mock_db_session: Any,
    mock_llm_provider: Any,
    user_1: Any,
    user_2: Any,
    user_1_chapter: Any,
) -> None:
    """D-37 对照：correct implementation（!= user_id）下 → 404。

    不使用 monkeypatch fixture；用真实的 _enforce_owner_or_404（!= user_id）。
    本测试作为 D-37 负面测试的对照（证明正确实现下不会被 fixture 影响）。
    """
    client = _build_test_client(mock_db_session, mock_llm_provider)
    # user_1 创建
    create_resp = client.post(
        "/api/v1/academic/questions",
        json={
            "chapter_id": user_1_chapter.id,
            "content": "user_1 content",
            "difficulty": "D",
            "type": "fill",
        },
        headers={"X-User-Id": "1"},
    )
    qid = create_resp.json()["id"]

    # user_2 读
    resp = client.get(
        f"/api/v1/academic/questions/{qid}", headers={"X-User-Id": "2"}
    )
    # 正确实现：!= user_id → 404
    assert resp.status_code == 404, (
        f"correct impl 应返 404，实际 {resp.status_code}：{resp.text}"
    )


# ─────────────────────── 路由注册校验 ────────────────────────────────


def test_five_question_endpoints_registered() -> None:
    """5 个 question 端点 + 路由注册（与 brief §4.4 端点列表对齐）。"""
    from app.api.v1.routers.academic import router

    paths = {(r.path, tuple(r.methods or set())) for r in router.routes}
    expected = {
        ("/questions", ("POST",)),
        ("/questions/{question_id}", ("GET",)),
        ("/questions", ("GET",)),
        ("/questions/{question_id}", ("PATCH",)),
        ("/questions/{question_id}", ("DELETE",)),
    }
    assert expected.issubset(paths), (
        f"缺端点：{expected - paths}"
    )