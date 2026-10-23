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
    """F2：挂 3 小题（分值 3/5/2）⇒ count=3、total_points=10.0（D3(a) 计数口径）。"""
    gid = _create_group(client, chapter.id)
    for i, pts in enumerate([3.0, 5.0, 2.0]):
        q = _make_question(mock_db_session, chapter.id, points=pts)
        r = client.post(
            f"/api/v1/academic/question-groups/{gid}/questions",
            json={"question_id": q.id, "group_order": i},
            headers={"X-User-Id": "1"},
        )
        assert r.status_code == 200, r.text

    r = client.get(f"/api/v1/academic/question-groups/{gid}", headers={"X-User-Id": "1"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["small_question_count"] == 3
    assert data["total_points"] == 10.0
    assert len(data["questions"]) == 3
    # 题序按 group_order 升序
    assert [q["id"] for q in data["questions"]] == sorted(
        [q["id"] for q in data["questions"]]
    )


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
    q = _make_question(mock_db_session, chapter.id)
    client.post(
        f"/api/v1/academic/question-groups/{gid}/questions",
        json={"question_id": q.id, "group_order": 0},
        headers={"X-User-Id": "1"},
    )
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
    """F6：挂题时难度继承组；改组难度 ⇒ 组内小题同步（组是唯一写入源）。"""
    gid = _create_group(client, chapter.id, difficulty="C")
    q = _make_question(mock_db_session, chapter.id, difficulty=QuestionDifficulty.D)

    r = client.post(
        f"/api/v1/academic/question-groups/{gid}/questions",
        json={"question_id": q.id, "group_order": 0},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200, r.text

    # 挂题后小题难度 = 组难度（派生，不是保留原值）
    mock_db_session.refresh(q)
    assert q.difficulty == QuestionDifficulty.C, f"挂题后难度 {q.difficulty}"

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


def test_r2_attach_question_from_other_chapter(
    client: TestClient, chapter: Any, chapter_other: Any, mock_db_session: Any
) -> None:
    """R2：挂别章节的小题 ⇒ 409「不在同一章节」。"""
    gid = _create_group(client, chapter.id)
    q = _make_question(mock_db_session, chapter_other.id)
    r = client.post(
        f"/api/v1/academic/question-groups/{gid}/questions",
        json={"question_id": q.id, "group_order": 0},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 409, r.text
    assert "同一章节" in r.json()["message"]


# ────────────────────────────── R3 重复题序（判据 15） ──────────────────────────────


def test_r3_duplicate_group_order(
    client: TestClient, chapter: Any, mock_db_session: Any
) -> None:
    """R3：同一 group_order 插两次 ⇒ 409（走 DB 唯一约束）。"""
    gid = _create_group(client, chapter.id)
    q1 = _make_question(mock_db_session, chapter.id)
    q2 = _make_question(mock_db_session, chapter.id)

    r = client.post(
        f"/api/v1/academic/question-groups/{gid}/questions",
        json={"question_id": q1.id, "group_order": 0},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200, r.text

    r = client.post(
        f"/api/v1/academic/question-groups/{gid}/questions",
        json={"question_id": q2.id, "group_order": 0},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 409, r.text
    assert "题序" in r.json()["message"]


# ────────────────────────────── R6 一题挂两组（丙-3 第 4 步） ──────────────────────────────


def test_r6_question_cannot_join_two_groups(
    client: TestClient, chapter: Any, mock_db_session: Any
) -> None:
    """R6：一题已在一组 ⇒ 再挂另一组 409（message 区分「其他题组」）。"""
    gid1 = _create_group(client, chapter.id)
    gid2 = _create_group(client, chapter.id)
    q = _make_question(mock_db_session, chapter.id)

    r = client.post(
        f"/api/v1/academic/question-groups/{gid1}/questions",
        json={"question_id": q.id, "group_order": 0},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200, r.text

    r = client.post(
        f"/api/v1/academic/question-groups/{gid2}/questions",
        json={"question_id": q.id, "group_order": 0},
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 409, r.text
    assert "其他题组" in r.json()["message"]


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
