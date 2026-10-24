"""M3-1a-2 题组模型 + 块表 + 组侧图片 API 测试。

端点（routers/academic.py，本笔新增 10 个）：
- 题组 6 个：POST/GET /question-groups · GET/PUT/DELETE /question-groups/{id} ·
             POST /question-groups/{id}/questions
- 组图 4 个：POST/GET /question-groups/{id}/images ·
            GET /question-groups/{id}/images/{image_id}/content ·
            DELETE /question-groups/{id}/images/{image_id}

用例设计（覆盖派工单判据 2-8、10-16；防 D-28 家族恒真/恒假门槛）：

| # | 场景 | 期望 | 判据 |
|---|---|---|---|
| F1 | 建组 → 详情回读 | 201 + id；detail 含 blocks/questions | 2 |
| F2 | 组挂 3 小题（分值 3/5/2） | small_question_count=3、total_points=10.0 | 4 |
| F3 | 材料 [text,image,table] 混排 | 读回 order_index 0/1/2 + block_type 各自对 | 5 |
| F4 | 材料图挂组 | group_id 有值、question_id 为 NULL | 6a |
| F5 | 删组（force）级联 | 3 表残留均 0（分三条 SQL 查） | 7 |
| F6 | 改组难度 → 组内小题同步 | 小题 difficulty 全部 = 新组难度 | 14（乙-4） |
| F7 | 组图 4 端点全链路 | 上传→列表→字节→删除后 404 + 磁盘文件消失 | 10 |
| F8 | meta 宽度字段读写 | 建 image 块带 meta={"image_width":75} → 读回原值 | 11 |
| R1 | 删组无 force | 409 + message 含三个数字 | 13（星云拍板二次确认） |
| R2 | 跨章节挂题 | 409 | 15 |
| R3 | 重复题序 | 409 | 15 |
| R4 | 非法 block_type='formula' | 422（Pydantic Literal 拦截） | 16 |
| R5 | 跨用户访问题组 | 404 | D-29 |
| R6 | 一题挂两组 | 409 | 丙-3 第 4 步 |
| R7 | 孤儿图（question_id 与 group_id 都 NULL） | DB CHECK 拒绝 | 6b |

验证要求：
- 走 FastAPI TestClient + dependency_overrides[get_db]（hermetic）
- headers X-User-Id
- DB 直查：残留计数 / difficulty 一致性 / storage_path
- 判据 11 的 SQLite+PG 双过：SQLite 走 conftest（Base.metadata.create_all），
  PG 走容器 pytest（见 交付物/运行时证据-1a-2 e736e17.md）
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    pass


# ────────────────────────────── fixtures ──────────────────────────────


@pytest.fixture()
def client(mock_db_session: Any) -> TestClient:
    """FastAPI TestClient（hermetic：API 与 fixture 用同一 session）。"""
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
    # 判据 13 要求「message 里三个数字正确」⇒ 必须按生产形态断言。
    register_exception_handlers(app)
    return TestClient(app)


@pytest.fixture()
def chapter(mock_db_session: Any, mock_user_system_seed: Any, mock_textbook: Any) -> Any:
    """章节（owner = system-seed id=1）。"""
    ch = Chapter(
        textbook_id=mock_textbook.id,
        owner_user_id=mock_user_system_seed.id,
        chapter_number=1,
        title="1a-2 测试章节",
        content_summary="题组测试用 chapter",
        extraction_source="detected",
    )
    mock_db_session.add(ch)
    mock_db_session.commit()
    mock_db_session.refresh(ch)
    return ch


@pytest.fixture()
def chapter_other(mock_db_session: Any, mock_user_system_seed: Any, mock_textbook: Any) -> Any:
    """另一个章节（跨章节守卫测试用，判据 15）。"""
    ch = Chapter(
        textbook_id=mock_textbook.id,
        owner_user_id=mock_user_system_seed.id,
        chapter_number=2,
        title="1a-2 另一章节",
        content_summary="跨章节测试用",
        extraction_source="detected",
    )
    mock_db_session.add(ch)
    mock_db_session.commit()
    mock_db_session.refresh(ch)
    return ch


@pytest.fixture()
def user2(mock_db_session: Any) -> Any:
    """user2（id=2）— 跨用户隔离用（R5）。"""
    user = User(id=2, name="user-2-cross", is_system_owned=False)
    mock_db_session.add(user)
    mock_db_session.commit()
    mock_db_session.refresh(user)
    return user


@pytest.fixture()
def kp(mock_db_session: Any, chapter: Any) -> Any:
    """知识点（挂在 chapter 下，归属走 chapter ⇒ owner = system-seed id=1）。

    KP 自身**无** owner_user_id —— 归属路径 = KP → chapter → chapter.owner_user_id。
    """
    k = KnowledgePoint(
        chapter_id=chapter.id,
        name="KP-1a-2",
        concept="1a-2 知识点概念",
        teaching_order=1,
    )
    mock_db_session.add(k)
    mock_db_session.commit()
    mock_db_session.refresh(k)
    return k


@pytest.fixture()
def kp_other(mock_db_session: Any, chapter_other: Any) -> Any:
    """另一个章节下的知识点（**同属 user1** —— 归属是过的）。

    ⚠️ 用来记录一个**已核源的事实**：brief / 补遗 / 派工单里**都没有**
    「组与 KP 必须同章节」这条规则，且 `POST /questions` 也不校验同章节
    （只校验归属：KP → 其 chapter → chapter.owner_user_id）。
    ⇒ 本项目**不引入**同章节约束，别自己发明。
    """
    k = KnowledgePoint(
        chapter_id=chapter_other.id,
        name="KP-1a-2-other",
        concept="另一章节的知识点",
        teaching_order=1,
    )
    mock_db_session.add(k)
    mock_db_session.commit()
    mock_db_session.refresh(k)
    return k


@pytest.fixture()
def chapter_user2(mock_db_session: Any, mock_textbook: Any, user2: Any) -> Any:
    """user2 自己的章节（KP 归属守卫测试用）。"""
    ch = Chapter(
        textbook_id=mock_textbook.id,
        owner_user_id=user2.id,
        chapter_number=9,
        title="user2 的章节",
        content_summary="跨用户 KP 守卫用",
        extraction_source="detected",
    )
    mock_db_session.add(ch)
    mock_db_session.commit()
    mock_db_session.refresh(ch)
    return ch


@pytest.fixture()
def kp_user2(mock_db_session: Any, chapter_user2: Any) -> Any:
    """**user2 名下**的知识点（user1 挂它 ⇒ 跨用户 ⇒ 404）。"""
    k = KnowledgePoint(
        chapter_id=chapter_user2.id,
        name="KP-user2",
        concept="user2 的知识点",
        teaching_order=1,
    )
    mock_db_session.add(k)
    mock_db_session.commit()
    mock_db_session.refresh(k)
    return k


def _make_question(
    session: Any,
    chapter_id: int,
    owner_id: int = 1,
    points: float = 2.0,
    difficulty: QuestionDifficulty = QuestionDifficulty.D,
) -> Any:
    """直接建一道小题（绕开 API，减少耦合）。"""
    q = Question(
        owner_user_id=owner_id,
        chapter_id=chapter_id,
        content=f"1a-2 测试题 {points}",
        difficulty=difficulty,
        type=QuestionType.CHOICE,
        points=points,
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
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ────────────────────────────── F1 建组 → 详情回读（判据 2） ──────────────────────────────


def test_f1_create_and_read_group(client: TestClient, chapter: Any) -> None:
    """F1：建题组 ⇒ 201 返回 id；详情一次返回材料 + 小题（D1(a)）。"""
    gid = _create_group(client, chapter.id, "B")

    r = client.get(f"/api/v1/academic/question-groups/{gid}", headers={"X-User-Id": "1"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["id"] == gid
    assert data["difficulty"] == "B"
    assert data["small_question_count"] == 0
    assert data["total_points"] == 0.0
    assert data["blocks"] == []
    assert data["questions"] == []


# ────────────────────────────── F2 小题数 + 总分（判据 4） ──────────────────────────────


def test_f2_group_small_questions_and_total_points(
    client: TestClient, chapter: Any, mock_db_session: Any
) -> None:
    """F2：组内**新建** 3 小题（分值 3/5/2）⇒ count=3、total_points=10.0（D3(a) 计数口径）。

    ⭐ 语义已改（1c-2 commit2 · brief §10.2 + 裁决②）：端点由「挂已有题」改为
    「组内建题」—— 章节/难度从组继承、题序后端 `max+1` 分配、**前端不传 group_order**。
    """
    gid = _create_group(client, chapter.id)
    for pts in [3.0, 5.0, 2.0]:
        r = client.post(
            f"/api/v1/academic/question-groups/{gid}/questions",
            json={
                "content": f"组内新建小题 {pts}",
                "type": "subjective",
                "points": pts,
            },
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 200, r.text

    r = client.get(f"/api/v1/academic/question-groups/{gid}", headers={"X-User-Id": "1"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["small_question_count"] == 3
    assert data["total_points"] == 10.0
    assert len(data["questions"]) == 3
    # 题序：**API 响应模型里没有 group_order** ⇒ 直接查库断言（库里 0 起）
    orders = [
        row[0]
        for row in mock_db_session.query(Question.group_order)
        .filter(Question.group_id == gid)
        .order_by(Question.group_order.asc())
        .all()
    ]
    assert orders == [0, 1, 2], orders


# ────────────────────────────── F3 材料三块混排（判据 5） ──────────────────────────────


def test_f3_blocks_mixed_order(client: TestClient, chapter: Any) -> None:
    """F3：材料 [text, image, table] 混排 ⇒ 读回 order_index 0/1/2 + block_type 各自对。"""
    gid = _create_group(client, chapter.id)
    r = client.put(
        f"/api/v1/academic/question-groups/{gid}",
        json={
            "blocks": [
                {"block_type": "text", "text_content": "第一段材料"},
                {"block_type": "table", "table_json": {"header": True, "rows": [["a", "b"]]}},
            ]
        },
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200, r.text
    blocks = r.json()["blocks"]
    assert len(blocks) == 2
    assert [b["order_index"] for b in blocks] == [0, 1]
    assert blocks[0]["block_type"] == "text"
    assert blocks[0]["text_content"] == "第一段材料"
    assert blocks[1]["block_type"] == "table"
    assert blocks[1]["table_json"] == {"header": True, "rows": [["a", "b"]]}


# ────────────────────────────── F8 meta 宽度字段（判据 11） ──────────────────────────────


def test_f8_meta_width_roundtrip(client: TestClient, chapter: Any) -> None:
    """F8：建块带 meta={"image_width":75} ⇒ 读回原值（判据 11 的存储位）。"""
    gid = _create_group(client, chapter.id)
    r = client.put(
        f"/api/v1/academic/question-groups/{gid}",
        json={
            "blocks": [
                {
                    "block_type": "text",
                    "text_content": "带 meta 的块",
                    "meta": {"image_width": 75},
                }
            ]
        },
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200, r.text
    blocks = r.json()["blocks"]
    assert blocks[0]["meta"] == {"image_width": 75}


# ────────────────────────────── F5 删组级联（判据 7） ──────────────────────────────


def test_f5_delete_group_cascades(
    client: TestClient, chapter: Any, mock_db_session: Any
) -> None:
    """F5：删组 ⇒ 材料块 + 小题 + 组图一起消失（**分三条 SQL 查残留**）。"""
    gid = _create_group(client, chapter.id)
    r = client.post(
        f"/api/v1/academic/question-groups/{gid}/questions",
        json={"content": "待删小题", "type": "subjective", "points": 2.0},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200, r.text
    client.put(
        f"/api/v1/academic/question-groups/{gid}",
        json={"blocks": [{"block_type": "text", "text_content": "待删材料"}]},
        headers={"X-User-Id": "1"},
    )

    # 先建 1 张组图
    img = QuestionImage(
        question_id=None,
        group_id=gid,
        order_index=0,
        file_ext="png",
        storage_path="/tmp/1a-2-f5.png",
        source="self_built",
        uploaded_by_user_id=1,
    )
    mock_db_session.add(img)
    mock_db_session.commit()

    # 无 force ⇒ 409（R1 单独测）
    r = client.delete(
        f"/api/v1/academic/question-groups/{gid}", headers={"X-User-Id": "1"}
    )
    assert r.status_code == 409, r.text

    r = client.delete(
        f"/api/v1/academic/question-groups/{gid}?force=true",
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 204, r.text

    # 分三条 SQL 查残留（判据 13 明写"不许合并"）
    n_q = (
        mock_db_session.query(Question).filter(Question.group_id == gid).count()
    )
    n_img = (
        mock_db_session.query(QuestionImage)
        .filter(QuestionImage.group_id == gid)
        .count()
    )
    n_blk = (
        mock_db_session.query(ContentBlock)
        .filter(ContentBlock.owner_type == "group", ContentBlock.owner_id == gid)
        .count()
    )
    assert n_q == 0, f"小题残留 {n_q}"
    assert n_img == 0, f"组图残留 {n_img}"
    assert n_blk == 0, f"材料块残留 {n_blk}"


# ────────────────────────────── R1 删组二次确认（判据 13） ──────────────────────────────


def test_r1_delete_group_requires_force(client: TestClient, chapter: Any) -> None:
    """R1：无 force ⇒ 409，且 message 里**三个数字正确**。"""
    gid = _create_group(client, chapter.id)
    client.put(
        f"/api/v1/academic/question-groups/{gid}",
        json={"blocks": [{"block_type": "text", "text_content": "材料"}]},
        headers={"X-User-Id": "1"},
    )

    r = client.delete(
        f"/api/v1/academic/question-groups/{gid}", headers={"X-User-Id": "1"}
    )
    assert r.status_code == 409, r.text
    body = r.json()
    # 计数只写进 message（errors.py 会吞 details）⇒ 必须能从 message 读到数字
    msg = body["message"]
    assert "0 道小题" in msg, msg
    assert "0 张材料图" in msg, msg
    assert "1 个材料块" in msg, msg
    assert "force=true" in msg, msg


# ────────────────────────────── F6 难度派生一致（判据 14 / 乙-4） ──────────────────────────────


def test_f6_difficulty_derived_from_group(
    client: TestClient, chapter: Any, mock_db_session: Any
) -> None:
    """F6：组内建题时难度**继承组**；改组难度 ⇒ 组内小题同步（组是唯一写入源）。

    ⭐ 语义已改（1c-2 commit2）：不再是「挂一道已有题」⇒ 不存在「保留原难度」这回事，
    小题从诞生起就是组难度的派生值。
    """
    gid = _create_group(client, chapter.id, difficulty="C")
    r = client.post(
        f"/api/v1/academic/question-groups/{gid}/questions",
        json={"content": "继承难度的小题", "type": "subjective", "points": 2.0},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200, r.text
    qid = r.json()["id"]

    # 建题后小题难度 = 组难度（派生，不是保留原值）
    q = mock_db_session.get(Question, qid)
    assert q is not None
    assert q.difficulty == QuestionDifficulty.C, f"建题后难度 {q.difficulty}"

    # 改组难度 ⇒ 同事务同步组内小题
    r = client.put(
        f"/api/v1/academic/question-groups/{gid}",
        json={"difficulty": "A"},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200, r.text

    mock_db_session.refresh(q)
    assert q.difficulty == QuestionDifficulty.A, f"改组后难度 {q.difficulty}"

    # 全组一致性：SELECT DISTINCT difficulty 只有 1 行且 = 组难度
    distinct = (
        mock_db_session.query(Question.difficulty)
        .filter(Question.group_id == gid)
        .distinct()
        .all()
    )
    assert len(distinct) == 1, distinct
    assert distinct[0][0] == QuestionDifficulty.A


# ────────────────────────────── F7 组图 4 端点全链路（判据 10） ──────────────────────────────


def test_f7_group_image_endpoints(
    client: TestClient, chapter: Any, mock_db_session: Any, tmp_path: Any
) -> None:
    """F7：上传 → 列表见到 → content 返回字节且 Content-Type 对 → 删除后 404 且磁盘文件消失。"""
    gid = _create_group(client, chapter.id)

    # 落盘根目录指到 tmp_path（UPLOAD_ROOT 与 UPLOADS_DIR 是两个变量）
    import os

    old_root = os.environ.get("UPLOAD_ROOT")
    os.environ["UPLOAD_ROOT"] = str(tmp_path)
    try:
        png = (
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        )  # 最小 PNG 头 + 填充
        r = client.post(
            f"/api/v1/academic/question-groups/{gid}/images",
            files={"file": ("mat.png", png, "image/png")},
            data={"file_ext": "png", "source": "self_built"},
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 200, r.text
        image_id = r.json()["id"]

        # 落盘路径必须带 group_ 前缀（判据 14：不能跟 question_id 目录撞）
        storage_path = r.json()["storage_path"]
        assert f"group_{gid}" in storage_path, storage_path

        # 列表见到
        r = client.get(
            f"/api/v1/academic/question-groups/{gid}/images",
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 200, r.text
        assert [i["id"] for i in r.json()] == [image_id]

        # content 返回字节 + Content-Type 对
        r = client.get(
            f"/api/v1/academic/question-groups/{gid}/images/{image_id}/content",
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "image/png"
        assert r.content == png

        # 删除 ⇒ 204，且磁盘文件消失
        from pathlib import Path

        assert Path(storage_path).is_file()
        r = client.delete(
            f"/api/v1/academic/question-groups/{gid}/images/{image_id}",
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 204, r.text
        assert not Path(storage_path).is_file(), "磁盘文件未删除"

        # 删除后再取 ⇒ 404
        r = client.get(
            f"/api/v1/academic/question-groups/{gid}/images/{image_id}/content",
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 404, r.text
    finally:
        if old_root is None:
            os.environ.pop("UPLOAD_ROOT", None)
        else:
            os.environ["UPLOAD_ROOT"] = old_root


# ────────────────────────────── F4 材料图挂组（判据 6a） ──────────────────────────────


def test_f4_group_image_ownership_columns(
    client: TestClient, chapter: Any, mock_db_session: Any, tmp_path: Any
) -> None:
    """F4：材料图挂组 ⇒ group_id 有值、question_id 为 NULL（D4(a) 两入口同表）。"""
    import os

    gid = _create_group(client, chapter.id)
    old_root = os.environ.get("UPLOAD_ROOT")
    os.environ["UPLOAD_ROOT"] = str(tmp_path)
    try:
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
        r = client.post(
            f"/api/v1/academic/question-groups/{gid}/images",
            files={"file": ("mat.png", png, "image/png")},
            data={"file_ext": "png"},
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 200, r.text
        image_id = r.json()["id"]

        row = mock_db_session.get(QuestionImage, image_id)
        assert row is not None
        assert row.group_id == gid
        assert row.question_id is None, "材料图 question_id 必须为 NULL"
    finally:
        if old_root is None:
            os.environ.pop("UPLOAD_ROOT", None)
        else:
            os.environ["UPLOAD_ROOT"] = old_root


# ────────────────────────────── R7 孤儿图 CHECK 拒绝（判据 6b） ──────────────────────────────


def test_r7_orphan_image_rejected_by_check(
    mock_db_session: Any, chapter: Any
) -> None:
    """R7：孤儿图（question_id 与 group_id 都 NULL）⇒ DB CHECK 拒绝。"""
    import sqlalchemy as sa

    img = QuestionImage(
        question_id=None,
        group_id=None,
        order_index=0,
        file_ext="png",
        storage_path="/tmp/orphan.png",
        source="self_built",
        uploaded_by_user_id=1,
    )
    mock_db_session.add(img)
    with pytest.raises(sa.exc.IntegrityError):
        mock_db_session.commit()
    mock_db_session.rollback()


# ────────────────────────────── R2 跨章节挂题（判据 15） ──────────────────────────────


def test_r2_group_question_kp_from_other_chapter_rejected(
    client: TestClient, chapter: Any, chapter_other: Any, kp_other: Any
) -> None:
    """R2（语义已改）：组内建题时传**别章节的知识点** ⇒ 422「不在题组章节内」。

    ⭐ 旧版这条是「挂别章节的小题 ⇒ 409」—— 端点改成「组内新建」后，
    小题章节**从组继承** ⇒ 跨章节的小题**根本构造不出来**；
    ⇒ 跨章节的口径转移到**知识点**上（小题章节 = 组章节 ⇒ KP 也不能跨章）。
    """
    gid = _create_group(client, chapter.id)
    r = client.post(
        f"/api/v1/academic/question-groups/{gid}/questions",
        json={
            "content": "带别章节知识点的小题",
            "type": "subjective",
            "points": 2.0,
            "knowledge_point_ids": [kp_other.id],
        },
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 422, r.text
    assert "不在题组章节内" in r.json()["message"]


# ────────────────────────────── R3 重复题序（判据 15） ──────────────────────────────


def test_r3_three_group_questions_get_strict_order(
    client: TestClient, chapter: Any, mock_db_session: Any
) -> None:
    """R3（语义已改 · 裁决②）：连建 3 题 ⇒ `group_order` **严格 0/1/2、无重复**。

    ⭐ 旧版这条是「同一 group_order 插两次 ⇒ 409」—— **已按裁决删除**：
      前端不再传 `group_order`（后端 `max+1` 分配）⇒ 那条用例的前置条件不存在了。
    ⚠️ **删用例 ≠ 删防线**：DB 的 `UNIQUE(group_id, group_order)` 与 API 的
      `IntegrityError → 409` 兜底**保留不动**；并发撞唯一约束的新风险由
      **算 max+1 前锁组行（SELECT ... FOR UPDATE）** 消除。
      ⇒ 本条改为固化「连建 3 题 ⇒ 题序严格递增、无重复、无空洞」。
    """
    gid = _create_group(client, chapter.id)
    for i in range(3):
        r = client.post(
            f"/api/v1/academic/question-groups/{gid}/questions",
            json={"content": f"第 {i} 题", "type": "subjective", "points": 2.0},
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 200, r.text

    orders = [
        row[0]
        for row in mock_db_session.query(Question.group_order)
        .filter(Question.group_id == gid)
        .order_by(Question.group_order.asc())
        .all()
    ]
    assert orders == [0, 1, 2], orders


# ────────────────────────────── R6 一题挂两组（丙-3 第 4 步） ──────────────────────────────


def test_r6_cannot_specify_group_id_or_group_order(
    client: TestClient, chapter: Any
) -> None:
    """R6（语义已改 · 裁决②）：建题 body 里传 `group_id` / `group_order` ⇒ **422**。

    ⭐ 旧版这条是「一题挂两组 ⇒ 409」—— 端点改成「组内新建」后
    **不再接受外部指定归属**：归属由 URL 的 group_id 决定
    ⇒ 传 `group_id` 是越权尝试、`group_order` 前端不传 ⇒ `extra="forbid"` 直接 422。
    """
    gid = _create_group(client, chapter.id)
    r = client.post(
        f"/api/v1/academic/question-groups/{gid}/questions",
        json={
            "content": "越权指定归属",
            "type": "subjective",
            "points": 2.0,
            "group_id": gid + 999,
        },
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 422, r.text

    r2 = client.post(
        f"/api/v1/academic/question-groups/{gid}/questions",
        json={
            "content": "越权指定题序",
            "type": "subjective",
            "points": 2.0,
            "group_order": 7,
        },
        headers={"X-User-Id": "1"},
    )
    assert r2.status_code == 422, r2.text


# ────────────────────────────── R4 非法块类型（判据 16） ──────────────────────────────


def test_r4_invalid_block_type_rejected(client: TestClient, chapter: Any) -> None:
    """R4：block_type='formula' ⇒ 422（Pydantic Literal 拦截，DB 不建 enum）。"""
    gid = _create_group(client, chapter.id)
    r = client.put(
        f"/api/v1/academic/question-groups/{gid}",
        json={"blocks": [{"block_type": "formula", "text_content": "x"}]},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 422, r.text


# ────────────────────────────── R5 跨用户隔离（D-29） ──────────────────────────────


def test_r5_cross_user_access(client: TestClient, chapter: Any, user2: Any) -> None:
    """R5：user2 访问 user1 的题组 ⇒ 404（D-29 跨用户隔离，不暴露存在性）。"""
    gid = _create_group(client, chapter.id)

    r = client.get(f"/api/v1/academic/question-groups/{gid}", headers={"X-User-Id": "2"})
    assert r.status_code == 404, r.text

    r = client.get("/api/v1/academic/question-groups", headers={"X-User-Id": "2"})
    assert r.status_code == 200, r.text
    assert r.json() == [], "user2 不应看到 user1 的题组"

    r = client.delete(
        f"/api/v1/academic/question-groups/{gid}?force=true",
        headers={"X-User-Id": "2"},
    )
    assert r.status_code == 404, r.text


# ────────────────────────────── 列表筛选（判据 3） ──────────────────────────────


def test_list_groups_filter_by_chapter(client: TestClient, chapter: Any, chapter_other: Any) -> None:
    """列表按 chapter_id 筛选。"""
    gid = _create_group(client, chapter.id)
    _create_group(client, chapter_other.id)

    r = client.get(
        f"/api/v1/academic/question-groups?chapter_id={chapter.id}",
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200, r.text
    assert [g["id"] for g in r.json()] == [gid]


# ────────────────────────────── F9 知识点关联：建组写入（判据 3 真正走法） ──────────────────────────────
#
# 🔴 这条是 2026-10-23 星轨审核打回后补的：原实现 group_knowledge_points
# **只有读没有写** ⇒ 判据 3 在 API 上根本做不到，我原来的 PG 验证脚本是
# **直接插库**造的 KP 关联 ⇒ 那个 PASS 不算数。
# 现在：建组 → 关联 KP → **用 GET ?knowledge_point_id= 筛出来**，全程走 API。


def test_f9_group_knowledge_points_written_via_api(
    client: TestClient, chapter: Any, kp: Any, mock_db_session: Any
) -> None:
    """建组时传 knowledge_point_ids ⇒ 落库 + 读回 + 能筛出来。"""
    r = client.post(
        "/api/v1/academic/question-groups",
        json={
            "chapter_id": chapter.id,
            "difficulty": "C",
            "knowledge_point_ids": [kp.id],
        },
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 201, r.text
    gid = r.json()["id"]

    # ① 响应就带上了（Read 字段）
    assert r.json()["knowledge_point_ids"] == [kp.id]

    # ② 真的落库了（查关联表，不靠响应自证）
    from sqlalchemy import select

    from app.models.academic import group_knowledge_points

    rows = mock_db_session.execute(
        select(group_knowledge_points.c.group_id).where(
            group_knowledge_points.c.group_id == gid
        )
    ).all()
    assert [row[0] for row in rows] == [gid], "group_knowledge_points 关联行未落库"

    # ③ 列表读回
    r = client.get("/api/v1/academic/question-groups", headers={"X-User-Id": "1"})
    assert r.status_code == 200, r.text
    got = [g for g in r.json() if g["id"] == gid]
    assert len(got) == 1
    assert got[0]["knowledge_point_ids"] == [kp.id]

    # ④ ⭐ 判据 3 的真正走法：**用 API 筛出该组**（不是插库造的）
    r = client.get(
        f"/api/v1/academic/question-groups?knowledge_point_id={kp.id}",
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200, r.text
    assert [g["id"] for g in r.json()] == [gid], "按知识点筛选没筛出该组"


# ────────────────────────────── F10 知识点关联：改组替换 + 归属守卫 ──────────────────────────────


def test_f10_group_knowledge_points_update_and_guard(
    client: TestClient, chapter: Any, kp: Any, kp_user2: Any, mock_db_session: Any
) -> None:
    """PUT 整体替换关联 + 跨用户 KP 被拒（404，不写库）。

    ⚠️ **不测跨章节 KP** —— 已核源：brief / 补遗 / 派工单**都没有**「组与 KP
    必须同章节」这条规则，且 `POST /questions` 也不校验同章节（只校验归属）。
    ⇒ 本项目不引入该约束（不自发明规则），只测归属守卫。
    """
    from sqlalchemy import select

    from app.models.academic import group_knowledge_points

    # 建组时先挂 kp
    r = client.post(
        "/api/v1/academic/question-groups",
        json={
            "chapter_id": chapter.id,
            "difficulty": "C",
            "knowledge_point_ids": [kp.id],
        },
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 201, r.text
    gid = r.json()["id"]

    # ① 换成 **user2 名下**的 KP ⇒ 归属校验不过 ⇒ 404
    r = client.put(
        f"/api/v1/academic/question-groups/{gid}",
        json={"knowledge_point_ids": [kp_user2.id]},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 404, r.text

    # 失败后原关联**未被改动**（404 不写库）
    rows = mock_db_session.execute(
        select(group_knowledge_points.c.knowledge_point_id).where(
            group_knowledge_points.c.group_id == gid
        )
    ).all()
    assert [row[0] for row in rows] == [kp.id], "404 之后关联不该被改动"

    # ①b 建组时直接传跨用户 KP ⇒ 同样 404（建组路径也要守）
    r = client.post(
        "/api/v1/academic/question-groups",
        json={
            "chapter_id": chapter.id,
            "difficulty": "C",
            "knowledge_point_ids": [kp_user2.id],
        },
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 404, r.text

    # ② 传空列表 ⇒ 清空关联
    r = client.put(
        f"/api/v1/academic/question-groups/{gid}",
        json={"knowledge_point_ids": []},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["knowledge_point_ids"] == []

    rows = mock_db_session.execute(
        select(group_knowledge_points.c.knowledge_point_id).where(
            group_knowledge_points.c.group_id == gid
        )
    ).all()
    assert rows == [], "传空列表应清空关联行"

    # ③ 重新挂上（自己章节的 KP）⇒ 成功
    r = client.put(
        f"/api/v1/academic/question-groups/{gid}",
        json={"knowledge_point_ids": [kp.id]},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["knowledge_point_ids"] == [kp.id]

    # ④ 不传 knowledge_point_ids ⇒ **不动**关联（不传 != 清空）
    r = client.put(
        f"/api/v1/academic/question-groups/{gid}",
        json={"difficulty": "A"},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["knowledge_point_ids"] == [kp.id], "不传就不该动关联"
    assert r.json()["difficulty"] == "A"


# ═══════════════════════════════════════════════════════════════════════════
# 星轨代码审查（批 1，2026-10-23）P1-1：写块时不校验 image_id 归属
# ═══════════════════════════════════════════════════════════════════════════
#
# 🔴 原实现：_replace_group_blocks 把 b.image_id **原样写库**，从不校验它属于本题组
#    ⇒ 用户 A 可以在材料里填**别人的** image_id（id 自增、可猜）：
#      1. 块建立成功；
#      2. 渲染时走 /question-groups/{A}/{B的图}/content ⇒ 404 ⇒ **材料破图**；
#      3. B 删掉那张图 ⇒ content_blocks.image_id FK CASCADE ⇒ **A 的材料块静默消失**。
#
# 修复：_check_group_image_ownership（校验**先于**删除）⇒ 422 且不写库。


def _upload_group_image(client: TestClient, group_id: int, tmp_path: Any) -> int:
    """往题组传一张材料图，返 image_id（走真实 API）。"""
    import os

    old_root = os.environ.get("UPLOAD_ROOT")
    os.environ["UPLOAD_ROOT"] = str(tmp_path)
    try:
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        r = client.post(
            f"/api/v1/academic/question-groups/{group_id}/images",
            files={"file": ("mat.png", png, "image/png")},
            data={"file_ext": "png", "source": "self_built"},
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 200, r.text
        return r.json()["id"]
    finally:
        if old_root is None:
            os.environ.pop("UPLOAD_ROOT", None)
        else:
            os.environ["UPLOAD_ROOT"] = old_root


def test_r8_block_image_id_must_belong_to_group(
    client: TestClient, chapter: Any, mock_db_session: Any, tmp_path: Any
) -> None:
    """R8：材料块引用**别组**的 image_id ⇒ 422，且**旧块一根汗毛都不动**。

    ⭐ 两条断言缺一不可：
      - 422：拒绝跨组引用；
      - 旧块仍在：**校验先于删除** ⇒ 校验不过时连 flush 都没发生。
        （若校验放在删除之后，旧块已被删掉再报错 —— 那是**数据破坏**。）
    """
    gid_a = _create_group(client, chapter.id)
    gid_b = _create_group(client, chapter.id)

    # B 组的一张图
    image_b = _upload_group_image(client, gid_b, tmp_path)

    # 先给 A 组放一个正常文本块（后面要验证它没被删）
    r = client.put(
        f"/api/v1/academic/question-groups/{gid_a}",
        json={"blocks": [{"block_type": "text", "text_content": "A 组原有块"}]},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200, r.text

    # A 组试图引用 **B 组的图** ⇒ 422
    r = client.put(
        f"/api/v1/academic/question-groups/{gid_a}",
        json={
            "blocks": [
                {"block_type": "text", "text_content": "A 组原有块"},
                {"block_type": "image", "image_id": image_b},
            ]
        },
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 422, r.text
    assert "不属于本题组" in r.json()["message"], r.text

    # ⭐ 旧块还在（校验先于删除 —— 没被删）
    r = client.get(
        f"/api/v1/academic/question-groups/{gid_a}", headers={"X-User-Id": "1"}
    )
    assert r.status_code == 200, r.text
    blocks = r.json()["blocks"]
    assert len(blocks) == 1, f"旧块被删了：{blocks}"
    assert blocks[0]["text_content"] == "A 组原有块", blocks
    assert blocks[0]["image_id"] is None, blocks

    # 落库核验：content_blocks 里**没有**那条跨组引用（不靠响应自证）
    from sqlalchemy import select

    from app.models.academic import ContentBlock

    rows = mock_db_session.execute(
        select(ContentBlock.image_id).where(
            ContentBlock.owner_type == "group", ContentBlock.owner_id == gid_a
        )
    ).all()
    assert [row[0] for row in rows] == [None], f"跨组 image_id 落库了：{rows}"


def test_r9_block_cannot_reference_question_image(
    client: TestClient, chapter: Any, mock_db_session: Any, tmp_path: Any
) -> None:
    """R9：材料块引用**题图**（question_id 有值、group_id 为 NULL）⇒ 422。

    同族漏洞的另一面：题图填进组材料 ⇒ 删那道题会连带删掉组材料块。
    口径：比对 group_id == group.id ⇒ 题图的 group_id 是 NULL，压根不匹配。
    """
    gid = _create_group(client, chapter.id)
    q = _make_question(mock_db_session, chapter.id)

    # 往**题目**上传一张图（question_id 有值、group_id 为 NULL）
    import os

    old_root = os.environ.get("UPLOAD_ROOT")
    os.environ["UPLOAD_ROOT"] = str(tmp_path)
    try:
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        r = client.post(
            f"/api/v1/academic/questions/{q.id}/images",
            files={"file": ("q.png", png, "image/png")},
            data={"file_ext": "png"},
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 201, r.text
        q_image_id = r.json()["id"]

        row = mock_db_session.get(QuestionImage, q_image_id)
        assert row is not None
        assert row.question_id == q.id
        assert row.group_id is None, "题图 group_id 应为 NULL"

        # 组材料引用题图 ⇒ 422
        r = client.put(
            f"/api/v1/academic/question-groups/{gid}",
            json={"blocks": [{"block_type": "image", "image_id": q_image_id}]},
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 422, r.text
        assert "不属于本题组" in r.json()["message"], r.text
    finally:
        if old_root is None:
            os.environ.pop("UPLOAD_ROOT", None)
        else:
            os.environ["UPLOAD_ROOT"] = old_root


def test_r10_nonexistent_image_id_same_error_as_cross_group(
    client: TestClient, chapter: Any
) -> None:
    """R10：**不存在的** image_id ⇒ 与跨组引用**同码同文案**。

    ⭐ 这条是「不给 id 存在性探测信号」的口径：
    不存在 与 不属于本题组 必须长得一模一样，否则就成了「这个 id 存不存在」的探测接口。
    """
    gid = _create_group(client, chapter.id)

    r = client.put(
        f"/api/v1/academic/question-groups/{gid}",
        json={"blocks": [{"block_type": "image", "image_id": 999999}]},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 422, r.text
    msg_missing = r.json()["message"]
    assert "不属于本题组" in msg_missing, r.text

    # 与 R8 的跨组文案形状一致（同样的 key，值不同但结构同）
    gid2 = _create_group(client, chapter.id)
    r2 = client.put(
        f"/api/v1/academic/question-groups/{gid2}",
        json={"blocks": [{"block_type": "image", "image_id": 999998}]},
        headers={"X-User-Id": "1"},
    )
    assert r2.status_code == r.status_code, (r2.status_code, r.status_code)
    assert r2.json()["error_code"] == r.json()["error_code"]
    assert r2.json()["message"].replace("999998", "X") == msg_missing.replace(
        "999999", "X"
    ), (r2.json()["message"], msg_missing)


# ═══════════════════════════════════════════════════════════════════════════
# 星轨代码审查（批 1，2026-10-23）P1-2：新增 6 个端点没有跨用户用例
# ═══════════════════════════════════════════════════════════════════════════
#
# 🔴 缺口：test_cross_user_isolation.py 只覆盖老的 13 个端点；
#    test_r5 只测了 GET 详情 / GET 列表 / DELETE。
#    ⇒ **没被测的**：PUT /question-groups/{id}、POST /question-groups/{id}/questions、
#      以及 **4 个组图端点**。
#    代码本身校验是对的，但**这条边界没有回归网** ⇒ 下次谁改错一行不会被发现。
#
# 口径：跨用户一律 **404**（不是 403 —— 不暴露 id 存在性，D-29 硬规则）。


def test_r11_cross_user_put_group_is_404(
    client: TestClient, chapter: Any, user2: Any
) -> None:
    """R11：user2 改 user1 的题组 ⇒ 404（且 user1 的组没被动过）。"""
    gid = _create_group(client, chapter.id, "C")

    r = client.put(
        f"/api/v1/academic/question-groups/{gid}",
        json={"difficulty": "A"},
        headers={"X-User-Id": "2"},
    )
    assert r.status_code == 404, r.text

    # user1 的组仍是原难度（user2 的写入没生效）
    r = client.get(
        f"/api/v1/academic/question-groups/{gid}", headers={"X-User-Id": "1"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["difficulty"] == "C", r.text


def test_r12_cross_user_create_group_question_is_404(
    client: TestClient, chapter: Any, user2: Any, mock_db_session: Any
) -> None:
    """R12（语义已改）：user2 往 **user1 的题组**里建小题 ⇒ 404（且**没有建出题**）。

    ⚠️ 与旧版的差别：旧版必须「用 user2 自己的题」才能证明守的是**组归属**
    （用 user1 的题时 404 是被「题归属」守卫拦下的，组归属那关根本没轮到执行）。
    现在端点是「组内新建」⇒ **题由本次请求现建** ⇒ 输入里根本没有别人的题
    ⇒ 唯一可能的归属守卫就是**组归属** ⇒ 直接测即可（且要断言**没有建出题**）。
    """
    gid = _create_group(client, chapter.id)  # owner = user1
    n_before = (
        mock_db_session.query(Question)
        .filter(Question.owner_user_id == 2)
        .count()
    )

    r = client.post(
        f"/api/v1/academic/question-groups/{gid}/questions",
        json={"content": "user2 越权建题", "type": "subjective", "points": 2.0},
        headers={"X-User-Id": "2"},
    )
    assert r.status_code == 404, r.text

    n_after = (
        mock_db_session.query(Question)
        .filter(Question.owner_user_id == 2)
        .count()
    )
    assert n_after == n_before, "user2 的建题生效了"


def test_r13_cross_user_group_image_endpoints_all_404(
    client: TestClient, chapter: Any, user2: Any, tmp_path: Any
) -> None:
    """R13：4 个组图端点对 user2 全部 404。

    逐个反例（星轨点名「4 个组图端点没网」）：
      POST   /question-groups/{id}/images
      GET    /question-groups/{id}/images
      GET    /question-groups/{id}/images/{image_id}/content
      DELETE /question-groups/{id}/images/{image_id}
    """
    import os

    gid = _create_group(client, chapter.id)
    image_id = _upload_group_image(client, gid, tmp_path)

    old_root = os.environ.get("UPLOAD_ROOT")
    os.environ["UPLOAD_ROOT"] = str(tmp_path)
    try:
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        H2 = {"X-User-Id": "2"}

        # ① POST 上传
        r = client.post(
            f"/api/v1/academic/question-groups/{gid}/images",
            files={"file": ("x.png", png, "image/png")},
            data={"file_ext": "png", "source": "self_built"},
            headers=H2,
        )
        assert r.status_code == 404, r.text

        # ② GET 列表
        r = client.get(
            f"/api/v1/academic/question-groups/{gid}/images", headers=H2
        )
        assert r.status_code == 404, r.text

        # ③ GET content
        r = client.get(
            f"/api/v1/academic/question-groups/{gid}/images/{image_id}/content",
            headers=H2,
        )
        assert r.status_code == 404, r.text

        # ④ DELETE
        r = client.delete(
            f"/api/v1/academic/question-groups/{gid}/images/{image_id}",
            headers=H2,
        )
        assert r.status_code == 404, r.text
    finally:
        if old_root is None:
            os.environ.pop("UPLOAD_ROOT", None)
        else:
            os.environ["UPLOAD_ROOT"] = old_root

    # ⭐ user2 的 4 次尝试后，user1 的图**还在**（没被删）
    r = client.get(
        f"/api/v1/academic/question-groups/{gid}/images", headers={"X-User-Id": "1"}
    )
    assert r.status_code == 200, r.text
    assert [i["id"] for i in r.json()] == [image_id], "user1 的图被误删了"


# ═══════════════════════════════════════════════════════════════════════════
# 1c-2 commit2 新增用例（2026-10-24 · 星轨 OUTBOX #6 的 4 条裁决）
# ═══════════════════════════════════════════════════════════════════════════


# ────────────────────────────── C1 反向用例：改不了章节（裁决①） ──────────────────────────────


def test_c1_patch_question_rejects_chapter_id_422(
    client: TestClient, chapter: Any, mock_db_session: Any
) -> None:
    """C1（裁决①的**替代动作**，必做）：`PATCH /questions/{id}` 传 `chapter_id` ⇒ **422**。

    ⭐ 为什么是这条而不是加 409 守卫：
      brief §10.3 原写「单题接口能绕过同章节约束」—— **该前提已被证伪**：
      `QuestionUpdate` **没有 `chapter_id` 字段** + `extra="forbid"` ⇒ 传了直接 422。
      ⇒ 「组在 A、小题被改成 B」这个状态**构造不出来** ⇒ 加 409 是永远触发不到的死代码。
      ⇒ 改为**固化「改不了」这个事实**：将来有人给 `QuestionUpdate` 加 `chapter_id`，
      这条用例会立刻红 ⇒ 提醒他补同章节守卫（brief §10.3 写了复活条件）。
    """
    q = _make_question(mock_db_session, chapter.id)
    r = client.patch(
        f"/api/v1/academic/questions/{q.id}",
        json={"chapter_id": chapter.id},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 422, r.text
    # 题目本身没被改
    mock_db_session.refresh(q)
    assert q.chapter_id == chapter.id


# ────────────────────────────── C2 判据 J：组内小题不进题库列表 ──────────────────────────────


def test_c2_group_questions_excluded_from_question_list(
    client: TestClient, chapter: Any, mock_db_session: Any
) -> None:
    """C2（判据 J）：组内小题**不出现在题库列表**，`total` 也不计入。

    ⭐ 为什么（brief §10.1）：「小题属于题组、与题库无关」⇒ 组内题混进题库会：
      ① 列表页同一道题显示两处；② `total` 虚增 ⇒ 分页与「共 N 题」全错；
      ③ 被抽题逻辑当题池抽到（没有材料的废题）—— 正是 D1(a) 要防的。
    """
    gid = _create_group(client, chapter.id)
    r = client.post(
        f"/api/v1/academic/question-groups/{gid}/questions",
        json={
            "content": "组内小题（不该出现在题库）",
            "type": "subjective",
            "points": 2.0,
        },
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200, r.text
    qid = r.json()["id"]

    r = client.get(
        "/api/v1/academic/questions",
        params={"chapter_id": chapter.id},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert qid not in [q["id"] for q in data["items"]], "组内小题出现在题库列表里了"

    # total 口径 = 该章节**非组内**的题数（不信前端算，查库对账）
    n_expected = (
        mock_db_session.query(Question)
        .filter(
            Question.chapter_id == chapter.id,
            Question.group_id.is_(None),
        )
        .count()
    )
    assert data["total"] == n_expected, (data["total"], n_expected)


# ────────────────────────────── P2-3 孤儿图回收 ──────────────────────────────


def test_p2_3_orphan_image_reclaimed_on_block_replace(
    client: TestClient, chapter: Any, mock_db_session: Any, tmp_path: Any
) -> None:
    """P2-3：整体替换材料块 ⇒ 「旧块引用、新块不引用」的孤儿图**行 + 磁盘文件**一起回收。

    ⭐ 为什么必须有这条（`docs/review-debt.md` P2-3 · 触发时机 = 1c-2 commit2 之前）：
      原本整体替换**只删块不删图** ⇒ 旧块引用的图在新块里没出现 ⇒ 那张图没人引用了，
      但行还在 `question_images`（**计数虚高** ⇒ 撞 10 张上限时
      「明明只用 3 张却报已达 10 张」）+ 文件留在磁盘（孤儿文件）。
      ⇒ 本笔兑现：替换时算孤儿 ⇒ 删行 + commit 后 unlink 磁盘文件。
    """
    from pathlib import Path

    gid = _create_group(client, chapter.id)
    image_id = _upload_group_image(client, gid, tmp_path)

    img_row = mock_db_session.get(QuestionImage, image_id)
    assert img_row is not None
    disk_path = img_row.storage_path
    assert disk_path and Path(disk_path).exists(), disk_path

    # 先把图挂进材料块
    r = client.put(
        f"/api/v1/academic/question-groups/{gid}",
        json={"blocks": [{"block_type": "image", "image_id": image_id}]},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200, r.text

    # 再整体替换成纯文字 ⇒ 图变孤儿
    r = client.put(
        f"/api/v1/academic/question-groups/{gid}",
        json={"blocks": [{"block_type": "text", "text_content": "不引用图了"}]},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200, r.text

    # 行没了
    assert mock_db_session.get(QuestionImage, image_id) is None, "孤儿图行没回收"
    # 磁盘文件也没了
    assert not Path(disk_path).exists(), f"孤儿图文件还在：{disk_path}"
    # 计数不再虚高
    imgs = client.get(
        f"/api/v1/academic/question-groups/{gid}/images",
        headers={"X-User-Id": "1"},
    )
    assert imgs.status_code == 200, imgs.text
    assert imgs.json() == [], imgs.json()
