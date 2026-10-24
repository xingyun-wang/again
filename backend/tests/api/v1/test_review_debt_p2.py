"""星轨代码审查（批 1，2026-10-23）P2 欠账回归网 —— P2-1 / P2-2 / P2-4 / P2-5。

台账：``docs/review-debt.md``（批 1 · 星轨 2026-10-23 登记）。

| 用例 | 欠账 | 守的不变式 |
|---|---|---|
| ``test_p2_1_...`` | P2-1 | 删题组时，**组内小题自己的题图**的磁盘文件也要被回收 |
| ``test_p2_2_...`` | P2-2 | 5xx 响应体的 message **不得含内部实现细节**（SQL / 表名 / 约束名） |
| ``test_p2_4_...`` | P2-4 | 删单题时，题图的**磁盘文件**要被回收 |
| ``test_p2_5_...`` | P2-5 | 单题图 / 组材料图的大小上限是**两个独立常量** |

写法沿用 ``backend/tests/api/v1/test_question_groups.py``（不另创风格）：
- ``client`` fixture：FastAPI TestClient + ``dependency_overrides[get_db]``
  ⇒ **API 与 fixture 用同一个 session 对象** ⇒ 可以
  ``monkeypatch.setattr(session, "commit", boom)`` 制造 DB 写失败；
- 落盘根目录：``os.environ["UPLOAD_ROOT"] = str(tmp_path)``
  （⚠️ ``UPLOAD_ROOT`` 与 ``UPLOADS_DIR`` 是两个变量，别搞混）；
- multipart 传图：``file`` / ``file_ext`` / ``order_index`` / ``source`` 四个 form 字段；
- DB 残留：**一律用 ``query(...).count()`` 查**（不用 ``session.get()`` ——
  fixture 的 session 是 ``expire_on_commit=False`` ⇒ 身份映射里可能留着已删的行 ⇒
  ``get()`` 会拿到 stale 对象；``query()`` 才是 DB 真值）。

⛔ 本文件**只**测这 4 条欠账；不改产品代码、不改其它文件。
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

# module level import 所有 model，让 conftest 的 Base.metadata.create_all
# 看到它们（否则 fixture setup 阶段就崩 "no such table: users"）
from app.models import (  # noqa: F401
    Chapter,
    KnowledgePoint,
    Question,
    QuestionDifficulty,
    QuestionType,
    User,
)
from app.models.academic import (  # noqa: F401
    ContentBlock,
    QuestionGroup,
    QuestionImage,
)

# 用户 1 = conftest 的 mock_user_system_seed（id=1）
_H1 = {"X-User-Id": "1"}

# 最小 PNG 头 + 填充（够 MIME/魔数校验，够落盘）
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

# P2-2：模拟 psycopg 抛出的异常文本 —— 里面有表名 / 约束名 / SQL 片段
#（真实 psycopg2 的 IntegrityError 文本长这样：客户端能读到 SQL 细节）
_SQL_SENTINEL = (
    "psycopg2.errors.UniqueViolation: duplicate key value violates unique "
    'constraint "ix_question_images_question_order"'
)

# P2-2：5xx 对外固定文案 —— **期望值**（docs/review-debt.md P2-2 建议改法原文）
_EXPECTED_INTERNAL_MESSAGE = "服务暂时不可用，请稍后重试"


# ────────────────────────────── fixtures ──────────────────────────────


@pytest.fixture()
def client(mock_db_session: Any) -> TestClient:
    """FastAPI TestClient（hermetic：API 与 fixture 用**同一个** session）。"""
    from fastapi import FastAPI

    from app.api.v1.routers.academic import router as academic_router
    from app.core.errors import register_exception_handlers
    from app.db.session import get_db

    app = FastAPI()

    def _override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.include_router(academic_router, prefix="/api/v1/academic")
    # 挂全局异常处理器 —— 生产 main.create_app() 也挂（app/core/errors.py:97）。
    # 不挂的话 HTTPException 的响应体是 FastAPI 默认的 {"detail": ...}，
    # 而生产是 {"message": ...}（全局 handler 把 detail 改写成 message）。
    register_exception_handlers(app)
    return TestClient(app)


@pytest.fixture()
def chapter(mock_db_session: Any, mock_user_system_seed: Any, mock_textbook: Any) -> Any:
    """章节（owner = system-seed id=1）。"""
    ch = Chapter(
        textbook_id=mock_textbook.id,
        owner_user_id=mock_user_system_seed.id,
        chapter_number=1,
        title="review-debt P2 测试章节",
        content_summary="P2 欠账回归网用 chapter",
        extraction_source="detected",
    )
    mock_db_session.add(ch)
    mock_db_session.commit()
    mock_db_session.refresh(ch)
    return ch


# ────────────────────────────── helpers ──────────────────────────────


@contextmanager
def _upload_root(root: Any) -> Iterator[str]:
    """把落盘根目录指到 ``root``（UPLOAD_ROOT 与 UPLOADS_DIR 是两个变量）。

    沿用既有写法（``test_question_groups.py::_upload_group_image``）：
    改环境变量 ⇒ 记旧值 ⇒ 结束时还原。
    ⚠️ 这里覆盖**整个用例**的时长（不是只包住上传那一秒）——
       删题 / 删组的实现若按 ``UPLOAD_ROOT`` 重算路径，也要拿到同一个根目录。
    """
    old_root = os.environ.get("UPLOAD_ROOT")
    os.environ["UPLOAD_ROOT"] = str(root)
    try:
        yield str(root)
    finally:
        if old_root is None:
            os.environ.pop("UPLOAD_ROOT", None)
        else:
            os.environ["UPLOAD_ROOT"] = old_root


def _make_question(session: Any, chapter_id: int, owner_id: int = 1) -> Any:
    """直接建一道小题（绕开 API，减少耦合）。"""
    q = Question(
        owner_user_id=owner_id,
        chapter_id=chapter_id,
        content="P2 欠账回归网用小题",
        difficulty=QuestionDifficulty.D,
        type=QuestionType.CHOICE,
        points=2.0,
    )
    session.add(q)
    session.commit()
    session.refresh(q)
    return q


def _create_group(client: TestClient, chapter_id: int, difficulty: str = "C") -> int:
    """走 API 建组，返 id。"""
    r = client.post(
        "/api/v1/academic/question-groups",
        json={"chapter_id": chapter_id, "difficulty": difficulty},
        headers=_H1,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload_question_image(client: TestClient, question_id: int) -> tuple[int, str]:
    """往单题传一张图（真落盘），返 (image_id, storage_path)。

    multipart 四个 form 字段：file / file_ext / order_index / source。
    """
    r = client.post(
        f"/api/v1/academic/questions/{question_id}/images",
        files={"file": ("q.png", _PNG, "image/png")},
        data={"file_ext": "png", "order_index": 0, "source": "self_built"},
        headers=_H1,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return body["id"], body["storage_path"]


def _app_sources() -> str:
    """把 ``app`` 包下所有已导入模块的源码拼起来（查常量**定义语句**用）。"""
    chunks: list[str] = []
    for name, mod in list(sys.modules.items()):
        if mod is None or not name.startswith("app."):
            continue
        f = getattr(mod, "__file__", None)
        if not f or not f.endswith(".py"):
            continue
        try:
            chunks.append(Path(f).read_text(encoding="utf-8"))
        except OSError:  # pragma: no cover - 读不到就跳过，不影响其它断言
            continue
    return "\n".join(chunks)


def _count_cases() -> int:
    """本文件里的 pytest 用例数（收尾打印用）。"""
    import inspect

    return sum(
        1
        for name, obj in vars(sys.modules[__name__]).items()
        if name.startswith("test_") and inspect.isfunction(obj)
    )


@pytest.fixture(scope="module", autouse=True)
def _report_case_count() -> Iterator[None]:
    """收尾打印一行本文件的用例数（既有测试文件的习惯）。"""
    yield
    print(f"\n[review-debt P2] test_review_debt_p2.py：共 {_count_cases()} 条回归用例")


# ═══════════════════════════════════════════════════════════════════════════
# P2-1 · 删组只 unlink 组图，小题自己的图全留在磁盘
# ═══════════════════════════════════════════════════════════════════════════
#
# 🔴 机制（docs/review-debt.md P2-1 已核源）：删组时 `storage_paths` 只收
#    `QuestionImage.group_id == group.id`（**组图**）⇒ 组内小题自己的图
#    （`question_images.question_id` 有值）随小题被 DB 级 CASCADE 带走**行**，
#    但**文件留在磁盘** ⇒ 孤儿文件。
# ⚠️ 组图那条路径本来就有回收（不是本条欠账）⇒ 本条守的是 **question_id 侧**。


def test_p2_1_delete_group_reclaims_group_question_image_file(
    client: TestClient, chapter: Any, mock_db_session: Any, tmp_path: Any
) -> None:
    """P2-1：删题组 ⇒ 组内小题的题图「行 + 磁盘文件」一起回收。

    场景：建组 → 组内新建 1 道小题 → 给这道小题传 1 张图（真落盘到 tmp_path）
    → ``DELETE /question-groups/{gid}?force=true``。
    期望：① 小题的 ``question_images`` 行没了；② **该题图的磁盘文件也没了**（核心）；
    ③ 题组行没了。
    守住的不变式：**「DB 行删干净 ⇒ 磁盘不留孤儿文件」**（删组这条路径上的
    question_id 侧）—— 只删行不删文件 ⇒ 磁盘用量只涨不跌。
    """
    with _upload_root(tmp_path):
        gid = _create_group(client, chapter.id)

        # 组内新建 1 道小题（章节 / 难度从组继承）
        r = client.post(
            f"/api/v1/academic/question-groups/{gid}/questions",
            json={"content": "组内小题（带自己的题图）", "type": "subjective", "points": 2.0},
            headers=_H1,
        )
        assert r.status_code == 200, r.text
        qid = r.json()["id"]

        # 给这道小题传 1 张图（真落盘）
        image_id, storage_path = _upload_question_image(client, qid)
        assert Path(storage_path).is_file(), f"题图没落盘：{storage_path}"

        # 删组（组内非空 ⇒ 无 force 会 409）
        r = client.delete(
            f"/api/v1/academic/question-groups/{gid}?force=true", headers=_H1
        )
        assert r.status_code == 204, r.text

        # ① 小题的题图行没了
        n_img = (
            mock_db_session.query(QuestionImage)
            .filter(QuestionImage.id == image_id)
            .count()
        )
        assert n_img == 0, f"小题题图行残留 {n_img}"

        # ② ⭐ 核心：该题图的**磁盘文件**也没了
        assert not Path(storage_path).is_file(), f"小题题图文件还在磁盘上：{storage_path}"

        # ③ 题组行没了
        n_group = (
            mock_db_session.query(QuestionGroup).filter(QuestionGroup.id == gid).count()
        )
        assert n_group == 0, f"题组行残留 {n_group}"


# ═══════════════════════════════════════════════════════════════════════════
# P2-2 · 500 响应体拼 {e} ⇒ 客户端能看到 SQL / 表名 / 约束名
# ═══════════════════════════════════════════════════════════════════════════
#
# 🔴 机制（docs/review-debt.md P2-2 已核源）：路由里 15 处
#    `raise HTTPException(status_code=500, detail=f"DB write failed: {e}")`
#    ⇒ psycopg / SQLAlchemy 的异常文本（表名 / 约束名 / SQL 片段）直接进响应体
#    ⇒ ``core/errors.py`` 的 handler 还把 ``detail`` 原样当 ``message`` 返回。
#    修法：detail 里不拼 ``{e}``（改 ``logger.exception``），客户端只看固定文案。


def test_p2_2_5xx_message_must_not_leak_internal_details(
    client: TestClient, chapter: Any, mock_db_session: Any, monkeypatch: Any
) -> None:
    """P2-2：DB 写失败 ⇒ 5xx 响应体的 message **不得含内部实现细节**。

    场景：把 session 的 ``commit`` 打成会抛「带 SQL 味文本」的异常
    （哨兵 = ``psycopg2.errors.UniqueViolation: ... unique constraint ...``），
    再打一个会走 ``except Exception → detail=f"DB write failed: {e}"`` 的端点
    （这里用 ``POST /questions/{id}/images``：它先落盘、再 commit ⇒ commit 失败
    ⇒ 走 ``except Exception`` 分支）。
    期望：① message 不含哨兵文本（也不含 ``psycopg2`` / ``unique constraint``）；
    ② message == 固定文案 ``"服务暂时不可用，请稍后重试"``。
    守住的不变式：**「5xx 对外只给固定文案，内部异常细节只进日志」** ——
    异常文本里可能有表名 / 约束名 / SQL 片段 ⇒ 拼进响应体等于给攻击者送数据库结构。
    """
    q = _make_question(mock_db_session, chapter.id)

    def boom() -> None:
        """模拟 commit 失败（异常文本里带 SQL / 约束名）。"""
        raise RuntimeError(_SQL_SENTINEL)

    # client fixture 与 mock_db_session 是**同一个 session 对象** ⇒ 直接打实例属性
    monkeypatch.setattr(mock_db_session, "commit", boom)

    r = client.post(
        f"/api/v1/academic/questions/{q.id}/images",
        files={"file": ("q.png", _PNG, "image/png")},
        data={"file_ext": "png", "order_index": 0, "source": "self_built"},
        headers=_H1,
    )
    assert r.status_code == 500, r.text

    body = r.json()
    msg = body["message"]

    # ① 哨兵 / SQL 味文本一律不许出现在 message 里
    assert _SQL_SENTINEL not in msg, msg
    assert "psycopg2" not in msg, msg
    assert "unique constraint" not in msg, msg
    assert "ix_question_images_question_order" not in msg, msg

    # ② message == 固定文案（不拼 {e}）
    assert msg == _EXPECTED_INTERNAL_MESSAGE, msg


# ═══════════════════════════════════════════════════════════════════════════
# P2-4 · delete_question 只删行不 unlink 题图（pre-existing）
# ═══════════════════════════════════════════════════════════════════════════
#
# 🔴 机制（docs/review-debt.md P2-4 已核源）：``DELETE /questions/{id}`` 里
#    ``db.delete(q)`` ⇒ ``Question.images`` 的 delete-orphan 把 ``question_images``
#    **行**删掉，但**磁盘文件留下** ⇒ 孤儿文件。
#    （对照：``DELETE /questions/{id}/images/{image_id}`` **有** unlink。）


def test_p2_4_delete_question_reclaims_question_image_file(
    client: TestClient, chapter: Any, mock_db_session: Any, tmp_path: Any
) -> None:
    """P2-4：删单题 ⇒ 题图的「行 + 磁盘文件」一起回收。

    场景：建 1 道单题（不挂组）→ 传 1 张图（真落盘到 tmp_path）
    → ``DELETE /api/v1/academic/questions/{qid}``。
    期望：① ``question_images`` 行没了；② **磁盘文件也没了**（核心）。
    守住的不变式：**「DB 行删干净 ⇒ 磁盘不留孤儿文件」**（单题这条路径）——
    与 P2-1 同族；删组会放大它（P2-1 把组内小题的图也留下）。
    """
    with _upload_root(tmp_path):
        q = _make_question(mock_db_session, chapter.id)

        image_id, storage_path = _upload_question_image(client, q.id)
        assert Path(storage_path).is_file(), f"题图没落盘：{storage_path}"

        r = client.delete(f"/api/v1/academic/questions/{q.id}", headers=_H1)
        assert r.status_code == 204, r.text

        # ① 行没了
        n_img = (
            mock_db_session.query(QuestionImage)
            .filter(QuestionImage.id == image_id)
            .count()
        )
        assert n_img == 0, f"题图行残留 {n_img}"

        # ② ⭐ 核心：磁盘文件也没了
        assert not Path(storage_path).is_file(), f"题图文件还在磁盘上：{storage_path}"


# ═══════════════════════════════════════════════════════════════════════════
# P2-5 · MAX_QUESTION_IMAGE_BYTES 被组图复用（命名与语义不符）
# ═══════════════════════════════════════════════════════════════════════════
#
# 🔴 机制（docs/review-debt.md P2-5 已核源）：常量名带 ``QUESTION``，
#    但题组材料图也用它判 5MB 上限 ⇒ 当前**无功能缺陷**，风险在未来：
#    哪天调「单题图 10MB」会**误伤组图**。
#    修法：拆成两个**独立**常量（改一个不影响另一个）。


def test_p2_5_question_and_group_image_size_limits_are_separate_constants() -> None:
    """P2-5：单题图 / 组材料图的大小上限是**两个独立常量**。

    期望：① ``MAX_QUESTION_IMAGE_BYTES`` 与 ``MAX_GROUP_IMAGE_BYTES``
    都能从 ``app.api.v1.routers.academic`` 导入；② 两者当前都 == 5MB；
    ③ 两者**不是彼此的别名**（否则「改单题上限会误伤组图」的风险仍在）；
    ④ 组图路径**真的**用组常量判上限（常量定义了却不用 = 假修）。
    守住的不变式：**「两个上限各自可调」** ——
    值断言本身就是回归网：哪天有人把其中一个改成 10MB，这条立刻红。
    """
    # ⚠️ import 写在**函数体内**（不是模块级）：旧代码里还没有
    #    MAX_GROUP_IMAGE_BYTES ⇒ 模块级 import 会让**整个文件收集失败**，
    #    连带另外 3 条用例都跑不起来。函数内 import ⇒ 只有这一条红。
    from app.api.v1.routers import academic

    # ① 两个常量都在
    assert hasattr(academic, "MAX_QUESTION_IMAGE_BYTES"), "缺少 MAX_QUESTION_IMAGE_BYTES"
    assert hasattr(academic, "MAX_GROUP_IMAGE_BYTES"), "缺少 MAX_GROUP_IMAGE_BYTES（组上限还没拆出来）"

    # ② 当前值都是 5MB
    assert academic.MAX_QUESTION_IMAGE_BYTES == 5 * 1024 * 1024
    assert academic.MAX_GROUP_IMAGE_BYTES == 5 * 1024 * 1024

    # ③ 不是彼此的别名（`MAX_GROUP_IMAGE_BYTES = MAX_QUESTION_IMAGE_BYTES` 这种写法不算拆开）
    alias = re.compile(r"MAX_GROUP_IMAGE_BYTES\s*=\s*MAX_QUESTION_IMAGE_BYTES")
    assert not alias.search(_app_sources()), "组常量是题常量的别名 ⇒ 上限还是同一个，没拆开"

    # ④ 组图路径真的用组常量（定义 + 至少一处使用）
    module_src = Path(academic.__file__).read_text(encoding="utf-8")
    assert module_src.count("MAX_GROUP_IMAGE_BYTES") >= 2, (
        "MAX_GROUP_IMAGE_BYTES 只出现 1 次（只有定义没有使用）⇒ 组图上限还在用题常量"
    )
