"""M3-1b 题库列表页 后端最小补充测试（M3-1b brief §1b-1）。

覆盖 3 处后端改动：
1. keyword 搜索（GET /questions?keyword=，SQLAlchemy .ilike()）
2. knowledge_point_ids 多选（OR 语义 + .distinct() 防 total 重复计数）
3. QuestionRead 暴露 knowledge_point_names + image_count（只读 property，无 N+1）

外加 1 个回归：既有单选 knowledge_point_id 行为不变（M3-1a 测试依赖）。

回执要点（per brief §5）：
- pytest 显式 -e DATABASE_URL=...tiered_homework_test（不污染 dev 库）
- 跑测试用 builder 镜像（runtime 镜像无 pytest）
- 每轮 pytest 前先 DROP alembic_version + alembic upgrade head（conftest teardown 不清它）
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

# py3.8 跳过：与 test_m3_1a.py 同款（B2 baseline 同步）
_skip_on_py38 = pytest.mark.skipif(
    sys.version_info < (3, 9),
    reason="B2 baseline: py3.9+ required for Mapped (PEP 585)",
)
pytestmark = _skip_on_py38


def _build_test_client(db_session: object, llm_provider: object) -> object:
    """构造带 DB + LLM 依赖 override 的 TestClient（与 test_m3_1a.py 同款）。"""
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


@pytest.fixture()
def kp_a(mock_db_session, user_1_chapter):  # type: ignore[no-untyped-def]
    """user_1_chapter 下 KP-A。"""
    from app.models import KnowledgePoint

    kp = KnowledgePoint(
        chapter_id=user_1_chapter.id,
        name="KP-A 等值线判读",
        concept="等值线概念",
        teaching_order=1,
    )
    mock_db_session.add(kp)
    mock_db_session.commit()
    mock_db_session.refresh(kp)
    return kp


@pytest.fixture()
def kp_b(mock_db_session, user_1_chapter):  # type: ignore[no-untyped-def]
    """user_1_chapter 下 KP-B（与 kp_a 同章不同名 → 不触发 1a 的 409 同章重名）。"""
    from app.models import KnowledgePoint

    kp = KnowledgePoint(
        chapter_id=user_1_chapter.id,
        name="KP-B 大气环流",
        concept="环流概念",
        teaching_order=2,
    )
    mock_db_session.add(kp)
    mock_db_session.commit()
    mock_db_session.refresh(kp)
    return kp


def _mk_question(
    client: object,  # type: ignore[no-untyped-def]
    chapter_id: int,
    content: str,
    difficulty: str = "D",
    qtype: str = "fill",
    kp_ids: list[int] | None = None,
) -> int:
    """建 1 题（POST /questions）→ 返回题 id。"""
    body: dict = {
        "chapter_id": chapter_id,
        "content": content,
        "difficulty": difficulty,
        "type": qtype,
    }
    if kp_ids:
        body["knowledge_point_ids"] = kp_ids
    resp = client.post(  # type: ignore[attr-defined]
        "/api/v1/academic/questions",
        json=body,
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ─────────────────── 改动 1：keyword 搜索 ────────────────────────────


def test_keyword_filters_questions(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_1_chapter: object,
) -> None:
    """GET /questions?keyword=等值线 → 仅命中题干含该词的题。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)

    q_iso = _mk_question(client, user_1_chapter.id, "读等值线图判断气压梯度")
    q_circ = _mk_question(client, user_1_chapter.id, "大气环流的形成机制")

    # 命中 1 题
    resp = client.get(
        "/api/v1/academic/questions?keyword=等值线",
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert [it["id"] for it in body["items"]] == [q_iso]

    # 换词命中另 1 题（证明不是恒等匹配）
    resp2 = client.get(
        "/api/v1/academic/questions?keyword=大气环流",
        headers={"X-User-Id": "1"},
    )
    assert resp2.status_code == 200, resp2.text
    assert [it["id"] for it in resp2.json()["items"]] == [q_circ]

    # 无命中 → 空列表（不报错）
    resp3 = client.get(
        "/api/v1/academic/questions?keyword=不存在的词XYZ",
        headers={"X-User-Id": "1"},
    )
    assert resp3.status_code == 200, resp3.text
    assert resp3.json()["total"] == 0
    assert resp3.json()["items"] == []

    # 不传 keyword → 见全部 2 题（参数可选）
    resp4 = client.get(
        "/api/v1/academic/questions", headers={"X-User-Id": "1"}
    )
    assert resp4.status_code == 200, resp4.text
    assert resp4.json()["total"] == 2


def test_keyword_min_length_guard(mock_db_session: object, mock_llm_provider: object) -> None:
    """keyword 空串 → 422（min_length=1 守卫；前端不该传空串）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get(
        "/api/v1/academic/questions?keyword=", headers={"X-User-Id": "1"}
    )
    assert resp.status_code == 422, resp.text


# ─────────────────── 改动 2：知识点多选（OR） ────────────────────────


def test_knowledge_point_ids_multi_or_semantics(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_1_chapter: object,
    kp_a: object,
    kp_b: object,
) -> None:
    """GET /questions?knowledge_point_ids=A,B → OR 语义命中 2 题。

    数据集：3 题 = 关联 KP-A / 关联 KP-B / 不关联任何 KP。
    关键断言：total == 2（**不重复计数** ⇒ 实现必须 .distinct()）。
    额外：给「同时关联 A+B」的题，验证 join 重复行被 distinct 消掉。
    """
    client = _build_test_client(mock_db_session, mock_llm_provider)

    q_a = _mk_question(client, user_1_chapter.id, "只看 KP-A", kp_ids=[kp_a.id])
    q_b = _mk_question(client, user_1_chapter.id, "只看 KP-B", kp_ids=[kp_b.id])
    q_none = _mk_question(client, user_1_chapter.id, "无 KP 题")
    # 双 KP 题：join 后会产生 2 行 —— distinct 的真正试金石
    q_ab = _mk_question(
        client, user_1_chapter.id, "双 KP 题", kp_ids=[kp_a.id, kp_b.id]
    )

    # 不带过滤 → 4 题
    resp_all = client.get("/api/v1/academic/questions", headers={"X-User-Id": "1"})
    assert resp_all.status_code == 200, resp_all.text
    assert resp_all.json()["total"] == 4

    # 多选 [A, B] → OR：命中 3 题（含双 KP 题）；total 不因 join 重复而膨胀
    resp = client.get(
        f"/api/v1/academic/questions?knowledge_point_ids={kp_a.id}&knowledge_point_ids={kp_b.id}",
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    got_ids = [it["id"] for it in body["items"]]
    assert body["total"] == 3, f"OR 多选 total 应为 3（distinct 失效？）：{body}"
    assert len(got_ids) == len(set(got_ids)), f"items 出现重复行：{got_ids}"
    assert set(got_ids) == {q_a, q_b, q_ab}
    assert q_none not in got_ids

    # 只选 [A] → 命中 2 题（含双 KP 题）
    resp_a = client.get(
        f"/api/v1/academic/questions?knowledge_point_ids={kp_a.id}",
        headers={"X-User-Id": "1"},
    )
    assert resp_a.status_code == 200, resp_a.text
    assert set(it["id"] for it in resp_a.json()["items"]) == {q_a, q_ab}

    # 不存在的 KP id → 空列表（不报错）
    resp_404 = client.get(
        "/api/v1/academic/questions?knowledge_point_ids=99999",
        headers={"X-User-Id": "1"},
    )
    assert resp_404.status_code == 200, resp_404.text
    assert resp_404.json()["total"] == 0


def test_knowledge_point_ids_and_single_combined_is_and(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_1_chapter: object,
    kp_a: object,
    kp_b: object,
) -> None:
    """单选 knowledge_point_id + 多选 knowledge_point_ids 同时给 = AND。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)

    q_ab = _mk_question(
        client, user_1_chapter.id, "双 KP 题", kp_ids=[kp_a.id, kp_b.id]
    )
    q_b = _mk_question(client, user_1_chapter.id, "只看 KP-B", kp_ids=[kp_b.id])

    # 单选 A ∧ 多选 [A, B] → 仅双 KP 题
    resp = client.get(
        "/api/v1/academic/questions"
        f"?knowledge_point_id={kp_a.id}&knowledge_point_ids={kp_a.id}&knowledge_point_ids={kp_b.id}",
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert [it["id"] for it in body["items"]] == [q_ab]
    assert q_b not in [it["id"] for it in body["items"]]


# ─────────────────── 改动 3：QuestionRead 展示字段 ───────────────────


def test_question_read_exposes_names_and_image_count(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_1_chapter: object,
    kp_a: object,
    kp_b: object,
) -> None:
    """QuestionRead 带 knowledge_point_names + image_count。

    - 1 题关联 2 个 KP → knowledge_point_names 含两个名（集合比对：
      Question.knowledge_points 关系无 order_by，顺序不保证，按集合断言）
    - image_count == 0（无图）
    """
    client = _build_test_client(mock_db_session, mock_llm_provider)

    q_id = _mk_question(
        client, user_1_chapter.id, "双 KP 题", kp_ids=[kp_a.id, kp_b.id]
    )

    resp = client.get("/api/v1/academic/questions", headers={"X-User-Id": "1"})
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    target = next(it for it in items if it["id"] == q_id)

    assert "knowledge_point_names" in target, "响应缺 knowledge_point_names"
    assert "image_count" in target, "响应缺 image_count"
    assert sorted(target["knowledge_point_names"]) == sorted(
        ["KP-A 等值线判读", "KP-B 大气环流"]
    )
    assert target["image_count"] == 0


def test_question_read_image_count_counts_images(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_1_chapter: object,
) -> None:
    """给题挂 2 张图 → image_count == 2（len(Question.images) 真值）。"""
    from app.models.academic import QuestionImage, QuestionImageSource

    client = _build_test_client(mock_db_session, mock_llm_provider)
    q_id = _mk_question(client, user_1_chapter.id, "带图题")

    for idx in (1, 2):
        mock_db_session.add(
            QuestionImage(
                question_id=q_id,
                order_index=idx,
                file_ext="png",
                storage_path=f"uploads/0/q{q_id}-{idx}.png",
                source=QuestionImageSource.SELF_BUILT,
                uploaded_by_user_id=1,
            )
        )
    mock_db_session.commit()

    resp = client.get("/api/v1/academic/questions", headers={"X-User-Id": "1"})
    assert resp.status_code == 200, resp.text
    target = next(it for it in resp.json()["items"] if it["id"] == q_id)
    assert target["image_count"] == 2
    # 无 KP 的题 → 空列表而非报错
    assert target["knowledge_point_names"] == []


# ─────────────────── 回归：既有单选参数不变 ──────────────────────────


def test_existing_single_knowledge_point_id_still_works(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_1_chapter: object,
    kp_a: object,
    kp_b: object,
) -> None:
    """回归（M3-1a brief §1.4）：单选 knowledge_point_id 行为不变。

    本笔改了同一段过滤代码，必须保证 1a 的 15 个测试不破。
    """
    client = _build_test_client(mock_db_session, mock_llm_provider)

    q_a = _mk_question(client, user_1_chapter.id, "只看 KP-A", kp_ids=[kp_a.id])
    q_b = _mk_question(client, user_1_chapter.id, "只看 KP-B", kp_ids=[kp_b.id])

    resp = client.get(
        f"/api/v1/academic/questions?knowledge_point_id={kp_a.id}",
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == q_a
    assert q_b not in [it["id"] for it in body["items"]]

    # 不存在的单选 KP → 空列表（1a 既有语义）
    resp_missing = client.get(
        "/api/v1/academic/questions?knowledge_point_id=9999",
        headers={"X-User-Id": "1"},
    )
    assert resp_missing.status_code == 200, resp_missing.text
    assert resp_missing.json()["total"] == 0


# ─────────────────── 组合：keyword + 多选 + 分页 ─────────────────────


def test_keyword_and_kp_multi_with_pagination(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1: object,
    user_1_chapter: object,
    kp_a: object,
) -> None:
    """组合过滤 + limit/offset 分页（1b 列表页真实用法）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)

    for i in range(3):
        _mk_question(
            client, user_1_chapter.id, f"等值线练习 {i}", kp_ids=[kp_a.id]
        )
    _mk_question(client, user_1_chapter.id, "等值线但无 KP")

    resp = client.get(
        "/api/v1/academic/questions"
        f"?keyword=等值线&knowledge_point_ids={kp_a.id}&limit=2&offset=0",
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 3, f"total 应为 3（total 不受 limit 影响）：{body}"
    assert len(body["items"]) == 2

    resp_p2 = client.get(
        "/api/v1/academic/questions"
        f"?keyword=等值线&knowledge_point_ids={kp_a.id}&limit=2&offset=2",
        headers={"X-User-Id": "1"},
    )
    assert resp_p2.status_code == 200, resp_p2.text
    body_p2 = resp_p2.json()
    assert body_p2["total"] == 3
    assert len(body_p2["items"]) == 1

    # 两页无重叠
    ids_p1 = {it["id"] for it in body["items"]}
    ids_p2 = {it["id"] for it in body_p2["items"]}
    assert not (ids_p1 & ids_p2), f"分页重叠：{ids_p1 & ids_p2}"


# ─────────────────── P3-1：建 KP 查重前 strip（星轨复核 66783cb） ──────────


def test_create_knowledge_point_dedupes_after_strip(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1_chapter: object,
) -> None:
    """'  大气  ' 与 '大气' 视为同名 → 第二个 409；且落库值已 strip。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    url = f"/api/v1/academic/chapters/{user_1_chapter.id}/knowledge-points"
    headers = {"X-User-Id": "1"}

    r1 = client.post(url, json={"name": "  大气  "}, headers=headers)
    assert r1.status_code in (200, 201), r1.text
    # 落库值必须已 strip，不能是 "  大气  "
    assert r1.json()["name"] == "大气", r1.json()

    # 仅差首尾空白 → 查重命中 → 409
    r2 = client.post(url, json={"name": "大气"}, headers=headers)
    assert r2.status_code == 409, r2.text


def test_create_knowledge_point_blank_only_name_rejected(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1_chapter: object,
) -> None:
    """纯空白 name → 422（strip 后判空，不落库）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        f"/api/v1/academic/chapters/{user_1_chapter.id}/knowledge-points",
        json={"name": "   "},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 422, resp.text


# ─────────────────── P3-2：keyword 的 LIKE 通配符转义 ───────────────────────


def test_keyword_escapes_like_wildcards(
    mock_db_session: object,
    mock_llm_provider: object,
    user_1_chapter: object,
) -> None:
    """keyword='%' / '_' 按字面量匹配，不得当通配符命中全部题。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    headers = {"X-User-Id": "1"}

    _mk_question(client, user_1_chapter.id, "读等值线图判断气压梯度")
    _mk_question(client, user_1_chapter.id, "大气环流的形成机制")

    total = client.get("/api/v1/academic/questions?limit=200", headers=headers)
    assert total.json()["total"] == 2, total.json()

    # '%' 转义后 = 字面量，库里无题干含 '%' → 0（未转义时会命中全部 2）
    pct = client.get("/api/v1/academic/questions", params={"keyword": "%"}, headers=headers)
    assert pct.status_code == 200, pct.text
    assert pct.json()["total"] == 0, pct.json()

    # '_' 同理
    us = client.get("/api/v1/academic/questions", params={"keyword": "_"}, headers=headers)
    assert us.status_code == 200, us.text
    assert us.json()["total"] == 0, us.json()

    # 转义不得破坏正常匹配
    ok = client.get("/api/v1/academic/questions", params={"keyword": "等值线"}, headers=headers)
    assert ok.json()["total"] == 1, ok.json()
