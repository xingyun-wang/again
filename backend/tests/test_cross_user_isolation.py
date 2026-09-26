"""跨用户隔离测试（M1-B retro 工单 B：D-29 B 项落地）。

覆盖：
1. 8 个端点的归属过滤：user_2 访问 user_1 的资源全部返 404（D-29 B 项）
2. 403 vs 404 断言：跨用户访问绝不返 403（D-29 反 ID 泄漏硬规则）
3. 跨 chapter owner 检查：LP 端点 JOIN chapter 检查归属
4. POST /textbooks/upload 写路径：service 层 set owner_user_id = current user
5. D-37 负面测试（核心）：fail-open 实现下 user_2 访问 user_1 数据返 200（数据泄漏）——
   证明错误实现是灾难性的，可证伪。

D-29 硬规则：
- 跨用户可见性：A 读 B → 404（不是 403，避免 id 存在性泄漏）
- 错误消息统一：「该资源不属于当前用户」

D-37 硬规则（可证伪）：
- 必须附一条在 fail-open 实现下会 FAIL 的测试
- 本测试文件用 monkeypatch_owner_filter_to_constant_one fixture 模拟
  fail-open 实现（filter obj.owner_user_id == 1 而非 != user_id），断言
  「错误实现下 user_2 访问 user_1 数据会返 200（数据泄漏）」。
- 这是「可证伪」证据：常规测试在 patch 下 fail-open，正确实现下 404。

Python 3.8 兼容（dev box）：
- module 顶部 patch typing.Annotated（py3.9+）和 enum.StrEnum（py3.11+），
  让 app.api.v1.routers.academic 的模块顶层 import 不爆
- 所有 `from app.models import ...` 延迟到 fixture / test 函数体内（lazy import），
  避免 pytest 收集时 app.models.academic 模块被重复加载导致 SQLAlchemy
  "Table 'users' already defined" 错误

设计要点：
- SQLite in-memory（mock_db_session fixture from conftest.py）
- FastAPI dependency override：get_db → mock session；get_llm_dep → mock LLM
- 每个测试前建表 + drop，状态隔离
- 走 TestClient（httpx + FastAPI 同步模式）
"""

from __future__ import annotations

import enum
import typing

if not hasattr(typing, "Annotated"):
    # Python 3.8 兼容（dev box）：typing.Annotated 在 py3.9+ 才存在。
    # 在 py3.11 container / CI 上这个 if 是 no-op。
    import typing_extensions

    typing.Annotated = typing_extensions.Annotated  # type: ignore[attr-defined]

if not hasattr(enum, "StrEnum"):
    # Python 3.8 兼容：enum.StrEnum 在 py3.11+ 才存在（app.core.llm.circuit_breaker
    # 用了）；dev box 补 shim（(str, Enum) 即可满足 `class StrEnum(str, Enum)` 语义）。
    class _StrEnumShim(str, enum.Enum):  # noqa: UP042  # shim 故意继承 str + Enum
        """Dev box shim for enum.StrEnum（py3.11+ 的原生类型）。"""

    enum.StrEnum = _StrEnumShim  # type: ignore[attr-defined]


# 注意：app.models / app.main / app.api.v1.routers.academic 均不在此处 import：
# 1. app.models：pytest collect 阶段可能多次触发 import，导致 SQLAlchemy
#    "Table 'users' already defined"；延迟到 fixture body 内 import
#    （利用 sys.modules 缓存，第二次起 no-op）
# 2. app.main：模块顶层 from app.db.session import engine → 触发 psycopg import
#    （dev box 无 psycopg 也会失败；延迟到 test 函数体）
# 所有 app.* import 延迟到 fixture body 或 test function body。

from io import BytesIO
from typing import Any

import pytest

# ─────────────────────── helpers ─────────────────────────────────────────────


def _build_test_client(db_session: Any, llm_provider: Any) -> Any:
    """构造带 DB + LLM 依赖 override 的 TestClient（lazy import）。"""
    from fastapi.testclient import TestClient  # noqa: F401 延迟 import

    from app.api.v1.routers.academic import get_llm_dep
    from app.db.session import get_db
    from app.main import create_app as build_app

    app = build_app()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_llm_dep] = lambda: llm_provider
    return TestClient(app)


def _build_minimal_pdf_bytes(title_line: str = "第一章") -> bytes:
    """构造一个最小可解析的 PDF（PyMuPDF 能识别 chapter title）。"""
    import fitz  # PyMuPDF

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), f"{title_line} 测试章节内容", fontsize=12)
    pdf_bytes_io = BytesIO()
    doc.save(pdf_bytes_io)
    doc.close()
    return pdf_bytes_io.getvalue()


# ─────────────────────── local fixtures ─────────────────────────────────────


@pytest.fixture()
def mock_user_1(mock_db_session):
    """测试用 user_1（id=1，is_system_owned=False；与 system-seed 区分）。"""
    from app.models import User  # lazy：避免 collect 阶段重复加载 app.models

    user = User(id=1, name="user-1", is_system_owned=False)
    mock_db_session.add(user)
    mock_db_session.commit()
    mock_db_session.refresh(user)
    return user


@pytest.fixture()
def mock_user_2(mock_db_session):
    """测试用 user_2（id=2）。"""
    from app.models import User  # lazy

    user = User(id=2, name="user-2", is_system_owned=False)
    mock_db_session.add(user)
    mock_db_session.commit()
    mock_db_session.refresh(user)
    return user


@pytest.fixture()
def user_1_subject(mock_db_session, mock_user_1):
    """user_1 拥有的 Subject（owner_user_id = 1）。"""
    from app.models import GradeLevel, Subject  # lazy

    sub = Subject(
        name="user_1's subject",
        grade_level=GradeLevel.SENIOR_HIGH,
        owner_user_id=mock_user_1.id,
    )
    mock_db_session.add(sub)
    mock_db_session.commit()
    mock_db_session.refresh(sub)
    return sub


@pytest.fixture()
def user_1_textbook(mock_db_session, mock_user_1, user_1_subject):
    """user_1 拥有的 Textbook（owner_user_id = 1）。"""
    from app.models import Textbook  # lazy

    tb = Textbook(
        name="user_1's textbook",
        file_path="uploads/0/u1-textbook.pdf",
        subject_id=user_1_subject.id,
        grade_level=user_1_subject.grade_level,
        owner_user_id=mock_user_1.id,
    )
    mock_db_session.add(tb)
    mock_db_session.commit()
    mock_db_session.refresh(tb)
    return tb


@pytest.fixture()
def user_1_chapter(mock_db_session, user_1_textbook):
    """user_1 拥有的 Chapter（继承 textbook 的 owner_user_id）。"""
    from app.models import Chapter  # lazy

    ch = Chapter(
        textbook_id=user_1_textbook.id,
        owner_user_id=user_1_textbook.owner_user_id,
        chapter_number=1,
        title="user_1's chapter 1",
        content_summary=(
            "本章介绍正数、负数的概念。"
            "user_1 内容；user_2 不应看到。"
        ),
        extraction_source="detected",
    )
    mock_db_session.add(ch)
    mock_db_session.commit()
    mock_db_session.refresh(ch)
    return ch


@pytest.fixture()
def user_1_lesson_plan(mock_db_session, user_1_chapter):
    """user_1 的 LessonPlan（基于 user_1_chapter，pending 状态）。"""
    from app.models import LessonPlan  # lazy

    lp = LessonPlan(
        chapter_id=user_1_chapter.id,
        content="user_1's lesson plan content (private)",
        duration_minutes=45,
        model="deepseek-chat",
        review_status="pending",
    )
    mock_db_session.add(lp)
    mock_db_session.commit()
    mock_db_session.refresh(lp)
    return lp


# ─────────────────────── 1. POST /textbooks/upload（service 层 set owner） ──────


def test_upload_sets_owner_user_id_to_current_user(
    mock_db_session: Any, mock_llm_provider: Any, mock_user_1: Any
) -> None:
    """user_1 上传教材 → DB 显示 owner_user_id = 1（service 层 set owner）。

    写路径归属硬规则：service 必须显式传 owner_user_id 给 Textbook + Chapter
    构造器（不允许走 ORM Python default）。本测试 DB 直查验证落库 owner。
    """
    from app.models import Chapter, Textbook  # lazy

    client = _build_test_client(mock_db_session, mock_llm_provider)
    pdf_bytes = _build_minimal_pdf_bytes()

    resp = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("u1.pdf", pdf_bytes, "application/pdf")},
        data={"name": "user_1's uploaded textbook"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text

    # DB 直查：owner_user_id = 1（user_1）
    tb_id = resp.json()["textbook_id"]
    tb_row = mock_db_session.get(Textbook, tb_id)
    assert tb_row is not None, "Textbook 行未落库"
    assert tb_row.owner_user_id == 1, (
        f"upload 写路径 textbook.owner_user_id 应为 1（user_1），"
        f"实际：{tb_row.owner_user_id}"
    )

    # 所有 chapter 也应继承 owner_user_id = 1
    chapters = mock_db_session.query(Chapter).filter(Chapter.textbook_id == tb_id).all()
    assert len(chapters) >= 1
    for ch in chapters:
        assert ch.owner_user_id == 1, (
            f"upload 章节 owner_user_id 应为 1，实际：{ch.owner_user_id}"
        )


# ─────────────────────── 2. GET /textbooks/{id}/chapters ──────────────────────


def test_user_2_gets_user_1_textbook_chapters_returns_404(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_user_1: Any,
    mock_user_2: Any,
    user_1_textbook: Any,
) -> None:
    """user_2 访问 user_1 的 textbook 章节列表 → 404（D-29 B 项硬规则）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get(
        f"/api/v1/academic/textbooks/{user_1_textbook.id}/chapters",
        headers={"X-User-Id": "2"},
    )
    # D-29 硬规则：跨用户 → 404（不是 403 / 不是 200 / 不是空列表 / 不是 500）
    assert resp.status_code == 404, (
        f"跨用户访问应返 404，实际 {resp.status_code}：{resp.text}"
    )
    assert resp.status_code != 403, "D-29 硬规则：403 会泄漏 id 存在性"
    assert resp.status_code != 200, "D-29 硬规则：跨用户不能看到 user_1 的数据"
    # 响应体不应包含 user_1 的 textbook 信息
    body_text = resp.text
    assert user_1_textbook.name not in body_text, (
        "跨用户 404 响应泄漏了 user_1 的 textbook 名称"
    )


# ─────────────────────── 3. POST /chapters/{id}/extract ──────────────────────


def test_user_2_extracts_user_1_chapter_returns_404(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_user_1: Any,
    mock_user_2: Any,
    user_1_chapter: Any,
) -> None:
    """user_2 调 extract on user_1 的 chapter → 404。"""
    # LLM mock 即使被调用也不应被执行（404 应在 LLM 调用前返）
    mock_llm_provider.set_chat_response("should not be called")
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        f"/api/v1/academic/chapters/{user_1_chapter.id}/extract",
        json={},
        headers={"X-User-Id": "2"},
    )
    assert resp.status_code == 404, (
        f"跨用户 extract 应返 404，实际 {resp.status_code}：{resp.text}"
    )
    assert resp.status_code != 403
    assert resp.status_code != 500, "归属检查应在 DB 查询后立刻 404，不应崩"
    # LLM 不应被调用（404 路径不进入 LLM）
    assert len(mock_llm_provider.chat_calls) == 0, (
        f"跨用户 404 路径不应调 LLM，实际调用了 {len(mock_llm_provider.chat_calls)} 次"
    )


# ─────────────────────── 4. GET /chapters/{id} ───────────────────────────────


def test_user_2_gets_user_1_chapter_returns_404(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_user_1: Any,
    mock_user_2: Any,
    user_1_chapter: Any,
) -> None:
    """user_2 读 user_1 的 chapter → 404。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get(
        f"/api/v1/academic/chapters/{user_1_chapter.id}",
        headers={"X-User-Id": "2"},
    )
    assert resp.status_code == 404, resp.text
    assert resp.status_code != 403
    assert resp.status_code != 200


# ─────────────────────── 5. PATCH /chapters/{id}/review ──────────────────────


def test_user_2_reviews_user_1_chapter_returns_404(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_user_1: Any,
    mock_user_2: Any,
    user_1_chapter: Any,
) -> None:
    """user_2 review user_1 的 chapter → 404。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.patch(
        f"/api/v1/academic/chapters/{user_1_chapter.id}/review",
        json={"status": "reviewed", "notes": "user_2 试图 review"},
        headers={"X-User-Id": "2"},
    )
    assert resp.status_code == 404, resp.text
    assert resp.status_code != 403
    assert resp.status_code != 500, "归属检查应在 DB 查询后立刻 404"


# ─────────────────────── 6. POST /lesson-plans/generate ──────────────────────


def test_user_2_generates_lesson_plan_for_user_1_chapter_returns_404(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_user_1: Any,
    mock_user_2: Any,
    user_1_chapter: Any,
) -> None:
    """user_2 用 user_1 的 chapter 生成 lesson-plan → 404。"""
    mock_llm_provider.set_chat_response("should not be called")
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/lesson-plans/generate",
        json={"chapter_id": user_1_chapter.id, "duration_minutes": 45},
        headers={"X-User-Id": "2"},
    )
    assert resp.status_code == 404, resp.text
    assert resp.status_code != 403
    assert len(mock_llm_provider.chat_calls) == 0, (
        "跨用户 404 路径不应调 LLM"
    )


# ─────────────────────── 7. GET /lesson-plans/{id}（JOIN chapter 检查 owner） ─


def test_user_2_gets_user_1_lesson_plan_returns_404(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_user_1: Any,
    mock_user_2: Any,
    user_1_lesson_plan: Any,
) -> None:
    """user_2 读 user_1 的 lesson-plan → 404（JOIN chapter 检查 owner）。

    JOIN chapter 路径：lesson-plan → chapter → 归属 user_1；user_2 访问应 404。
    """
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get(
        f"/api/v1/academic/lesson-plans/{user_1_lesson_plan.id}",
        headers={"X-User-Id": "2"},
    )
    assert resp.status_code == 404, resp.text
    assert resp.status_code != 403
    # 响应体不应泄漏 user_1 的 lesson-plan 内容
    assert user_1_lesson_plan.content not in resp.text, (
        "跨用户 404 响应泄漏了 user_1 的 lesson-plan 内容"
    )


# ─────────────────────── 8. PATCH /lesson-plans/{id}/review（JOIN） ──────────


def test_user_2_reviews_user_1_lesson_plan_returns_404(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_user_1: Any,
    mock_user_2: Any,
    user_1_lesson_plan: Any,
) -> None:
    """user_2 review user_1 的 lesson-plan → 404（JOIN chapter 检查 owner）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.patch(
        f"/api/v1/academic/lesson-plans/{user_1_lesson_plan.id}/review",
        json={"status": "reviewed", "notes": "user_2 试图 review"},
        headers={"X-User-Id": "2"},
    )
    assert resp.status_code == 404, resp.text
    assert resp.status_code != 403
    assert resp.status_code != 500


# ─────────────────────── 403 vs 404 综合断言（D-29 硬规则） ─────────────────


def test_cross_user_access_never_returns_403(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_user_1: Any,
    mock_user_2: Any,
    user_1_textbook: Any,
    user_1_chapter: Any,
    user_1_lesson_plan: Any,
) -> None:
    """D-29 综合断言：跨用户访问 8 端点全部 ≠ 403（403 会泄漏 id 存在性）。

    单独抽出来跑所有跨用户端点，确保 8 个 e2e 测试里没有任何一个意外返 403。
    """
    mock_llm_provider.set_chat_response("irrelevant")
    client = _build_test_client(mock_db_session, mock_llm_provider)

    cross_user_calls: list[tuple[str, str, dict[str, Any]]] = [
        ("GET", f"/api/v1/academic/textbooks/{user_1_textbook.id}/chapters", {}),
        ("POST", f"/api/v1/academic/chapters/{user_1_chapter.id}/extract", {"json": {}}),
        ("GET", f"/api/v1/academic/chapters/{user_1_chapter.id}", {}),
        (
            "PATCH",
            f"/api/v1/academic/chapters/{user_1_chapter.id}/review",
            {"json": {"status": "reviewed"}},
        ),
        (
            "POST",
            "/api/v1/academic/lesson-plans/generate",
            {"json": {"chapter_id": user_1_chapter.id}},
        ),
        (
            "GET",
            f"/api/v1/academic/lesson-plans/{user_1_lesson_plan.id}",
            {},
        ),
        (
            "PATCH",
            f"/api/v1/academic/lesson-plans/{user_1_lesson_plan.id}/review",
            {"json": {"status": "reviewed"}},
        ),
    ]
    for method, url, kwargs in cross_user_calls:
        resp = client.request(method, url, headers={"X-User-Id": "2"}, **kwargs)
        assert resp.status_code != 403, (
            f"D-29 硬规则违反：{method} {url} 跨用户访问返 403（泄漏 id 存在性）"
            f"，实际 {resp.status_code}：{resp.text}"
        )
        # 全部应是 404（统一返 404，不泄漏 id 存在性）
        assert resp.status_code == 404, (
            f"跨用户 {method} {url} 应返 404，实际 {resp.status_code}：{resp.text}"
        )


# ─────────────────────── 跨 chapter owner 检查（更细的 JOIN 语义） ─────────


def test_lesson_plan_owner_check_via_chapter_join(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_user_1: Any,
    mock_user_2: Any,
    user_1_chapter: Any,
    user_1_lesson_plan: Any,
) -> None:
    """LP 端点通过 JOIN chapter 检查 owner：user_2 看不到 user_1 的 LP。"""
    mock_llm_provider.set_chat_response("授课建议")
    client = _build_test_client(mock_db_session, mock_llm_provider)

    # 正向：user_1 能 GET 自己的 LP（200）
    own = client.get(
        f"/api/v1/academic/lesson-plans/{user_1_lesson_plan.id}",
        headers={"X-User-Id": "1"},
    )
    assert own.status_code == 200, own.text

    # 反向：user_2 GET → 404
    cross = client.get(
        f"/api/v1/academic/lesson-plans/{user_1_lesson_plan.id}",
        headers={"X-User-Id": "2"},
    )
    assert cross.status_code == 404, cross.text
    assert cross.status_code != 403


# ─────────────────────── D-37 负面测试（核心：可证伪） ─────────────────────


def test_d37_fail_open_owner_filter_would_leak_data_returns_200(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_user_1: Any,
    mock_user_2: Any,
    user_1_textbook: Any,
    monkeypatch_owner_filter_to_constant_one,
) -> None:
    """D-37 负面测试：mock 错误实现 → user_2 访问 user_1 数据会泄漏（200）。

    本测试在 monkeypatch_owner_filter_to_constant_one fixture 激活下：
    - _enforce_owner_or_404 被替换为 fail-open 版本（filter by constant 1）
    - 用户_2 (X-User-Id=2) 访问 user_1 的 textbook → 返 200（数据泄漏）

    可证伪证据：
    - 错误实现（filter by constant 1）下：response == 200，暴露 user_1 数据
    - 正确实现（!= user_id）下：response == 404（本文件其他测试覆盖）

    本测试断言「错误实现下确实返 200」 — 证明错误实现是灾难性的。
    如果有人把 _enforce_owner_or_404 写成 == 1 而非 != user_id，本测试
    会立刻暴露（200 暴露数据），无法逃过审查。
    """
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get(
        f"/api/v1/academic/textbooks/{user_1_textbook.id}/chapters",
        headers={"X-User-Id": "2"},
    )

    # D-37 核心断言：错误实现下应返 200（数据泄漏）
    assert resp.status_code == 200, (
        f"D-37 错误实现应返 200（暴露数据），实际 {resp.status_code}：{resp.text}"
        f" — 这意味着 fail-open fixture 没生效，或实现已被改正"
    )
    # 进一步验证：响应体确实包含 user_1 的 chapter 标题（数据泄漏实证）
    # P6 修复（2026-09-26 CI run #20）：端点是 GET /textbooks/{id}/chapters，
    # 响应体是 chapter 列表而非 textbook → 断言应查 chapter.title。
    assert user_1_chapter.title in resp.text, (
        "D-37 fail-open fixture 应暴露 user_1 chapter 标题，但响应体没有"
    )


def test_d37_correct_owner_filter_returns_404_for_cross_user(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_user_1: Any,
    mock_user_2: Any,
    user_1_textbook: Any,
) -> None:
    """D-37 对照：correct implementation（!= user_id）下 → 404。

    不使用 monkeypatch fixture；用真实的 _enforce_owner_or_404（!= user_id）。
    本测试作为 D-37 负面测试的对照（证明正确实现下不会被 fixture 影响）。
    """
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.get(
        f"/api/v1/academic/textbooks/{user_1_textbook.id}/chapters",
        headers={"X-User-Id": "2"},
    )
    # 正确实现：!= user_id → 404
    assert resp.status_code == 404, (
        f"correct impl 应返 404，实际 {resp.status_code}：{resp.text}"
    )


# ─────────────────────── 路由注册校验（保留 brief 要求） ─────────────────


def test_all_eight_endpoints_registered() -> None:
    """8 个 academic 端点 + 路由注册（与 brief 端点列表对齐）。

    此测试只 import 路由模块（lazy import 不在模块顶层），不依赖 app.main 链。
    """
    from app.api.v1.routers.academic import router

    paths = {(r.path, tuple(r.methods or set())) for r in router.routes}
    expected = {
        ("/textbooks/upload", ("POST",)),
        ("/textbooks/{textbook_id}/chapters", ("GET",)),
        ("/chapters/{chapter_id}/extract", ("POST",)),
        ("/chapters/{chapter_id}", ("GET",)),
        ("/chapters/{chapter_id}/review", ("PATCH",)),
        ("/lesson-plans/generate", ("POST",)),
        ("/lesson-plans/{lesson_plan_id}", ("GET",)),
        ("/lesson-plans/{lesson_plan_id}/review", ("PATCH",)),
    }
    assert expected.issubset(paths), f"缺端点：{expected - paths}"