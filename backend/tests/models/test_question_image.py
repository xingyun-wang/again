"""M2-A.1 QuestionImage 模型 + 3 endpoint API 测试（v0.5 §3.4 + brief §7.2）。

路径：backend/tests/models/test_question_image.py（brief §7.2 拍板）。

用例设计（7 用例 = 4 正向 7.2.1-7.2.4 + 3 反向 R1-R3 防 D-28 家族）：

| # | 场景 | 期望 | 闸门 |
|---|---|---|---|
| 7.2.1 | POST upload + GET read | 201 + 200 + 字段匹配 + 文件落盘 | 基础 CRUD |
| 7.2.2 | 3 image 不同 order_index | DB 顺序 = order_index asc | 排序 |
| 7.2.3 | 删 Question → cascade 清 image | 删 question 后 image row 没了 | 级联清理 |
| 7.2.4 | file_ext='svg' 不支持 | 422 | 字段约束 |
| R1 | DELETE 不存在 image_id | 404 | 存在性预言机 |
| R2 | user2 操作 user1 image | 404 | D-29 跨用户隔离 |
| R3 | 上传 5MB+ 文件 + 不允许 mime | 413 + 422 | 容量 + 内容闸门 |

验证要求：
- 容器 PG pytest：DATABASE_URL=postgresql... 跑出 7 passed
- 本地 SQLite 路径不验证（10-10 §三 实证会假红/假绿）
- 走 FastAPI TestClient + dependency_overrides[get_db]（hermetic）
- headers X-User-Id
- UPLOAD_ROOT monkeypatch 到 tmp_path（避免污染真实目录）
- DB 直查：image row 存在性 + 字段
- 仿 test_assignment_review.py 5+1 模式（hermetic client + dependency override +
  DB 直查 + caplog 防状态污染）
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

# A2 修法补充: module level import 所有 model,让 conftest 的 Base.metadata.create_all
# 看到它们(否则 fixture setup 阶段就崩: "no such table: users")
from app.models import (  # noqa: F401
    Chapter,
    Question,
    QuestionDifficulty,
    QuestionType,
    User,
)
from app.models.academic import (  # noqa: F401  # QuestionImage 未在 app.models.__init__ re-export
    DesensitizationStatus as ORMDesensitizationStatus,
)
from app.models.academic import (
    QuestionImage,
)
from app.models.academic import (
    QuestionImageSource as ORMQuestionImageSource,
)

if TYPE_CHECKING:
    pass


# ────────────────────────────── fixtures ──────────────────────────────


@pytest.fixture()
def client(mock_db_session: Any) -> TestClient:
    """FastAPI TestClient（hermetic：API 与 fixture 用同一 session）。

    A2 fix v3 极简 app：只挂 academic_router + dependency_overrides[get_db]。
    """
    from fastapi import FastAPI

    from app.api.v1.routers.academic import router as academic_router
    from app.db.session import get_db

    app = FastAPI()

    def _override_get_db() -> Any:
        yield mock_db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.include_router(academic_router, prefix="/api/v1")
    return TestClient(app)


@pytest.fixture()
def user_question(
    mock_db_session: Any, mock_user_system_seed: Any, mock_textbook: Any
) -> Any:
    """user1（system-seed）拥有的 question（chapter 来自 mock_textbook）。

    chapter + question 一并建好；返回 question（含 chapter_id）。
    """
    ch = Chapter(
        textbook_id=mock_textbook.id,
        owner_user_id=mock_user_system_seed.id,
        chapter_number=1,
        title="M2-A.1-test-chapter",
        content_summary="M2-A.1 §7.2 测试用 chapter",
        extraction_source="detected",
    )
    mock_db_session.add(ch)
    mock_db_session.commit()

    q = Question(
        owner_user_id=mock_user_system_seed.id,
        chapter_id=ch.id,
        content="M2-A.1 测试题目",
        difficulty=QuestionDifficulty.C,
        type=QuestionType.CHOICE,
    )
    mock_db_session.add(q)
    mock_db_session.commit()
    mock_db_session.refresh(q)
    return q


@pytest.fixture()
def user2(mock_db_session: Any) -> Any:
    """user2（id=2）— 跨用户隔离测试用。"""
    user = User(id=2, name="user-2-cross-image", is_system_owned=False)
    mock_db_session.add(user)
    mock_db_session.commit()
    mock_db_session.refresh(user)
    return user


@pytest.fixture()
def upload_root(monkeypatch: Any, tmp_path: Path) -> str:
    """monkeypatch UPLOAD_ROOT 到 tmp_path，返 path str。

    endpoint 写文件路径 = os.environ.get("UPLOAD_ROOT", DEFAULT_UPLOADS_DIR)
    + /{chapter_id}/{question_id}/{image_id}.{ext}

    monkeypatch 结束自动还原 env var；tmp_path 自动清理。
    """
    root = str(tmp_path / "uploads")
    monkeypatch.setenv("UPLOAD_ROOT", root)
    return root


def _make_image_bytes(size: int = 100) -> bytes:
    """构造 N bytes 的伪 PNG（仅用于 size 校验；不做真 PNG 解析）。

    8 字节 PNG magic 头 + 任意 padding；流式 read 8K chunks 验证 size 闸门。
    """
    header = b"\x89PNG\r\n\x1a\n"
    padding = b"\x00" * max(0, size - len(header))
    return header + padding


def _upload_image(
    client: TestClient,
    question_id: int,
    *,
    file_ext: str = "png",
    content_type: str = "image/png",
    order_index: int = 0,
    source: str = "self_built",
    file_bytes: bytes | None = None,
    user_id: int = 1,
) -> Any:
    """通过 TestClient 上传图片（multipart），返 response。"""
    if file_bytes is None:
        file_bytes = _make_image_bytes(100)
    return client.post(
        f"/api/v1/questions/{question_id}/images",
        files={"file": (f"test.{file_ext}", BytesIO(file_bytes), content_type)},
        data={
            "file_ext": file_ext,
            "order_index": str(order_index),
            "source": source,
        },
        headers={"X-User-Id": str(user_id)},
    )


# ─────────────────────── 7.2.1: create + query ────────────────────────


def test_7_2_1_create_and_query(
    client: TestClient,
    user_question: Any,
    upload_root: str,
    mock_db_session: Any,
) -> None:
    """基础 CRUD：POST upload → 201；GET read → 200 + 字段匹配 + 文件落盘。

    防恒假门槛：
    - 预检 POST 返 201 + 关键字段（id / file_ext / order_index / source /
      desensitization_status / uploaded_by_user_id / uploaded_at）
    - 预检 GET 返 200 + response == POST response（GET 不重写字段）
    - DB 直查：row 存在 + 关键字段匹配
    - 文件实际落盘：路径 = ${UPLOAD_ROOT}/{chapter_id}/{question_id}/{image_id}.{ext}
    """
    resp = _upload_image(client, user_question.id)
    assert resp.status_code == 201, (
        f"POST upload 应 201，实际 {resp.status_code}：{resp.text}"
    )
    data = resp.json()
    assert data["file_ext"] == "png"
    assert data["order_index"] == 0
    assert data["source"] == "self_built"
    assert data["desensitization_status"] == "pending"
    assert data["uploaded_by_user_id"] == 1
    assert data["uploaded_by_user_id"] == user_question.owner_user_id
    assert "id" in data and data["id"] > 0
    assert "uploaded_at" in data

    img_id = data["id"]

    # GET read
    get_resp = client.get(
        f"/api/v1/questions/{user_question.id}/images/{img_id}",
        headers={"X-User-Id": "1"},
    )
    assert get_resp.status_code == 200, (
        f"GET 应 200，实际 {get_resp.status_code}：{get_resp.text}"
    )
    get_data = get_resp.json()
    assert get_data == data, (
        f"GET 响应应与 POST 响应一致；POST={data} vs GET={get_data}"
    )

    # DB 直查
    row = mock_db_session.get(QuestionImage, img_id)
    assert row is not None, f"DB 无 image_id={img_id} 行"
    assert row.file_ext == "png"
    assert row.order_index == 0
    assert row.source == ORMQuestionImageSource.SELF_BUILT
    assert row.desensitization_status == ORMDesensitizationStatus.PENDING
    assert row.uploaded_by_user_id == 1
    assert row.question_id == user_question.id

    # 文件实际落盘（brief §4.1 路径模板）
    expected_path = (
        Path(upload_root)
        / str(user_question.chapter_id)
        / str(user_question.id)
        / f"{img_id}.png"
    )
    assert expected_path.exists(), f"文件未落盘 {expected_path}"
    assert expected_path.stat().st_size > 0, "落盘文件为空"


# ─────────────────────── 7.2.2: sort order_index ────────────────────────


def test_7_2_2_sort_by_order_index(
    client: TestClient,
    user_question: Any,
    upload_root: str,
    mock_db_session: Any,
) -> None:
    """3 image 不同 order_index，DB 顺序 = order_index asc（与 Choice 同款）。

    防恒假门槛：
    - 上传顺序 0/2/1（乱序）
    - DB 查 order_by order_index asc → 0, 1, 2
    - relationship selectin eager load 验证 question.images 也按 order_index 排
    """
    # 上传 3 image，order_index 0, 2, 1（乱序上传）
    order_pairs = [(0, "a"), (2, "b"), (1, "c")]
    for order, _label in order_pairs:
        resp = _upload_image(client, user_question.id, order_index=order)
        assert resp.status_code == 201, (
            f"upload order={order} 应 201，实际 {resp.status_code}：{resp.text}"
        )

    # DB 直查：order_by order_index asc
    rows = (
        mock_db_session.query(QuestionImage)
        .filter(QuestionImage.question_id == user_question.id)
        .order_by(QuestionImage.order_index.asc())
        .all()
    )
    assert len(rows) == 3, f"应有 3 张图，实际 {len(rows)}"
    assert [r.order_index for r in rows] == [0, 1, 2], (
        f"DB 顺序应 [0, 1, 2]，实际 {[r.order_index for r in rows]}"
    )

    # relationship selectin 验证：question.images 也按 order_index 排
    # （refresh 强制重发 SQL 加载 images；原 user_question 对象在 upload 前已
    #  commit，其 selectin cache = 空 list；用 refresh 避免 stale cache 陷阱）
    q = mock_db_session.get(Question, user_question.id)
    assert q is not None
    mock_db_session.refresh(q, attribute_names=["images"])
    assert len(q.images) == 3
    assert [img.order_index for img in q.images] == [0, 1, 2], (
        f"relationship 顺序应 [0, 1, 2]，实际 {[img.order_index for img in q.images]}"
    )


# ─────────────────────── 7.2.3: delete cascade ────────────────────────


def test_7_2_3_question_delete_cascades_to_images(
    client: TestClient,
    user_question: Any,
    upload_root: str,
    mock_db_session: Any,
) -> None:
    """§治理 级联清理：删 Question → QuestionImage 自动 cascade 清空（all, delete-orphan）。

    防恒假门槛：
    - 预检 image row 存在
    - DELETE question 返 204
    - DB 直查：image row 没了（cascade 自动清理）
    """
    # 先上传 1 image
    resp = _upload_image(client, user_question.id)
    assert resp.status_code == 201, (
        f"upload 应 201，实际 {resp.status_code}：{resp.text}"
    )
    img_id = resp.json()["id"]

    # DB 直查：image row 存在
    assert mock_db_session.get(QuestionImage, img_id) is not None, (
        f"image_id={img_id} 应存在"
    )

    # 删 question（既有 endpoint；不属 M2-A.1 范围）
    del_resp = client.delete(
        f"/api/v1/questions/{user_question.id}",
        headers={"X-User-Id": "1"},
    )
    assert del_resp.status_code == 204, (
        f"DELETE question 应 204，实际 {del_resp.status_code}：{del_resp.text}"
    )

    # DB 直查：image row 没了（cascade 自动清理）
    assert mock_db_session.get(QuestionImage, img_id) is None, (
        f"删 question 后 image {img_id} 应 cascade 删，但 row 还在"
    )


# ─────────────────────── 7.2.4: 字段约束（file_ext 白名单） ────────────────────────


def test_7_2_4_invalid_file_ext_422(
    client: TestClient,
    user_question: Any,
    upload_root: str,
) -> None:
    """Pydantic + 业务校验：file_ext='svg'（不支持）→ 422。

    防恒假门槛：
    - pre-check: file_ext='svg' 不在 _ALLOWED_FILE_EXTS 白名单
    - post-check: 422 + 响应 detail 提及 'svg 不收' 或 '不支持'
    """
    resp = _upload_image(client, user_question.id, file_ext="svg")
    assert resp.status_code == 422, (
        f"file_ext='svg' 应 422（svg 不收 — brief §5.3），实际 {resp.status_code}：{resp.text}"
    )
    detail = resp.text.lower()
    assert "svg" in detail or "不支持" in detail or "not supported" in detail, (
        f"422 detail 应说明 svg 不收，实际：{resp.text}"
    )


# ─────────────────────── R1: DELETE 不存在 image → 404 ────────────────────────


def test_R1_delete_nonexistent_image_404(
    client: TestClient,
    user_question: Any,
) -> None:
    """存在性预言机：DELETE 不存在 image_id → 404（不暴露存在性）。"""
    resp = client.delete(
        f"/api/v1/questions/{user_question.id}/images/99999",
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 404, (
        f"DELETE 不存在 image 应 404，实际 {resp.status_code}：{resp.text}"
    )


# ─────────────────────── R2: 跨 user 操作 image → 404 ────────────────────────


def test_R2_cross_user_image_404(
    client: TestClient,
    user_question: Any,
    user2: Any,
    upload_root: str,
    mock_db_session: Any,
) -> None:
    """D-29 跨用户隔离：user2 操作 user1 image → 404（不暴露存在性）。

    防恒假门槛：
    - user1 上传 image 成功
    - user2 GET user1 image → 404（不暴露 image 存在性）
    - user2 DELETE user1 image → 404（不暴露 image 存在性）
    - DB 直查：image row 还在（user2 越权被拒，未改 DB）
    """
    # user1 上传 1 image
    up_resp = _upload_image(client, user_question.id)
    assert up_resp.status_code == 201, (
        f"user1 upload 应 201，实际 {up_resp.status_code}：{up_resp.text}"
    )
    img_id = up_resp.json()["id"]

    # user2 GET → 404
    get_resp = client.get(
        f"/api/v1/questions/{user_question.id}/images/{img_id}",
        headers={"X-User-Id": "2"},
    )
    assert get_resp.status_code == 404, (
        f"user2 GET user1 image 应 404，实际 {get_resp.status_code}：{get_resp.text}"
    )

    # user2 DELETE → 404
    del_resp = client.delete(
        f"/api/v1/questions/{user_question.id}/images/{img_id}",
        headers={"X-User-Id": "2"},
    )
    assert del_resp.status_code == 404, (
        f"user2 DELETE user1 image 应 404，实际 {del_resp.status_code}：{del_resp.text}"
    )

    # DB 直查：image row 还在（user2 操作被拒，未改 DB）
    row = mock_db_session.get(QuestionImage, img_id)
    assert row is not None, "user2 越权后 image row 还在（应还在，证明 404 没改 DB）"


# ─────────────────────── R3: 上传超 5MB 或不允许 mime → 413/422 ────────────────────────


def test_R3_upload_oversize_or_disallowed_mime(
    client: TestClient,
    user_question: Any,
    upload_root: str,
) -> None:
    """容量 + 内容闸门：上传 5MB+ → 413；上传 application/octet-stream → 422。

    仿 brief §5.3 「超 5MB 或不允许 mime」合并 1 用例（防 D-28 第 2 类 = 闩样
    假绿；判据同时覆盖容量 + 内容两个闸门）。

    防恒假门槛：
    - 5MB + 1 byte 上传 → 413（容量闸门）
    - application/octet-stream MIME 上传 → 422（内容闸门）
    """
    # 容量闸门：5MB + 1 byte → 413
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (5 * 1024 * 1024 + 1)
    resp_413 = _upload_image(client, user_question.id, file_bytes=big)
    assert resp_413.status_code == 413, (
        f"5MB+1 byte 上传应 413，实际 {resp_413.status_code}：{resp_413.text}"
    )

    # 内容闸门：application/octet-stream MIME → 422
    resp_422 = _upload_image(
        client,
        user_question.id,
        file_ext="png",
        content_type="application/octet-stream",
    )
    assert resp_422.status_code == 422, (
        f"application/octet-stream 应 422，实际 {resp_422.status_code}：{resp_422.text}"
    )
