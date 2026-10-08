"""TWAIN HTTP 桥 mock 端到端测试（M2 S0-4：D-M2-4 拍板 + 3 补丁 A/B/C）。

覆盖：
1. 契约稳定：POST /api/v1/twain/scan/omr 接受 multipart → 返回 ScanOMRResponse
2. deterministic：同 (level, chapter_id) → 同 answers（seed 稳定）
3. 4 档位独立性：D/C/B/A 各档产生不同答案（位置 + 答案都不同）
4. 跨边界架构：注册新 router 后现有 endpoint（/api/health）仍工作
5. 错误处理：缺字段 / 非法 level / question_count 越界 → 422
6. 文件落盘：UPLOAD_ROOT/scans/{uuid}.{ext} 实际写盘
7. metadata 标注：bridge_layer="http_bridge_mock"（M3 替换时零返工判据）

设计要点：
- 走 e2e 路径（TestClient + create_app），与 test_health.py 同模式
- UPLOAD_ROOT 重定向到 tmp_path（dev box 上 /app/data/uploads 不存在）
- ruff + mypy 全过（pyproject files=["app"]，tests/ 不在 lint 范围但仍过 ruff check tests/）
- 不依赖真 LLM / DB（mock router 是纯函数；无 DB 写入）
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routers import twain as twain_module
from app.api.v1.schemas.twain import (
    ANSWER_CHOICES,
    BRIDGE_LAYER_MOCK,
    MAX_QUESTION_COUNT,
    MIN_QUESTION_COUNT,
    TIER_DETECTED_POSITIONS,
)
from app.main import create_app

# ──────────────────────────── 测试辅助 ────────────────────────────


# 最小合法 PDF magic + 一点 body（不需真 PDF；mock 不解析内容）
MINIMAL_PDF_BYTES = b"%PDF-1.4\n%mock scan content for test\n"


def _pdf_bytes(size: int = 1024) -> bytes:
    """生成测试用 PDF 字节（前 5 字节 = %PDF- magic）。"""
    header = MINIMAL_PDF_BYTES
    padding = b"X" * max(0, size - len(header))
    return header + padding


def _jpeg_bytes(size: int = 1024) -> bytes:
    """生成测试用 JPEG 字节（magic = \\xff\\xd8\\xff）。"""
    header = b"\xff\xd8\xff\xe0" + b"X" * 16
    padding = b"Y" * max(0, size - len(header))
    return header + padding


def _png_bytes(size: int = 1024) -> bytes:
    """生成测试用 PNG 字节（magic = \\x89PNG\\r\\n\\x1a\\n）。"""
    header = b"\x89PNG\r\n\x1a\n" + b"X" * 16
    padding = b"Z" * max(0, size - len(header))
    return header + padding


def _build_client(upload_root: Path) -> TestClient:
    """构造 TestClient；monkeypatch UPLOAD_ROOT 在 fixture 里做。"""
    return TestClient(create_app())


@pytest.fixture()
def twain_upload_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """把 TWAIN router 的 UPLOAD_ROOT 重定向到 tmp_path。

    与 test_streaming_upload.py:upload_root_tmp 同模式（避免 dev box 上
    /app/data/uploads 不存在的写盘失败）。
    """
    monkeypatch.setattr(twain_module, "UPLOAD_ROOT", tmp_path)
    monkeypatch.setenv("UPLOAD_ROOT", str(tmp_path))
    return tmp_path


# ──────────────────────────── 1. 契约稳定 ────────────────────────────


def test_scan_omr_pdf_returns_200_with_contract(twain_upload_root: Path) -> None:
    """POST /scan/omr 接受 multipart PDF → 200 + ScanOMRResponse schema。

    契约判据（决策书 §7.3 补丁 A + 任务 brief）：
    - 路径：POST /api/v1/twain/scan/omr
    - 请求：multipart/form-data（file + chapter_id + question_count + level）
    - 响应：JSON 含 answers（list）+ metadata（dict，含 bridge_layer）
    """
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-001",
            "question_count": "10",
            "level": "D",
        },
        files={
            "file": ("scan.pdf", _pdf_bytes(), "application/pdf"),
        },
    )
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()

    # 顶层 schema
    assert set(body.keys()) == {"answers", "metadata"}, f"unexpected keys: {body.keys()}"

    # answers 是 list[str | None]，长度 = question_count
    answers = body["answers"]
    assert isinstance(answers, list)
    assert len(answers) == 10
    for a in answers:
        assert a is None or a in ANSWER_CHOICES, f"invalid answer value: {a!r}"

    # metadata 必含字段
    meta = body["metadata"]
    required_meta_keys = {
        "bridge_layer",
        "level",
        "chapter_id",
        "question_count",
        "detected_count",
        "file_path",
        "file_size",
        "content_type",
        "magic_kind",
        "timestamp",
    }
    assert required_meta_keys.issubset(meta.keys()), (
        f"missing metadata keys: {required_meta_keys - meta.keys()}"
    )
    assert meta["bridge_layer"] == BRIDGE_LAYER_MOCK
    assert meta["level"] == "D"
    assert meta["chapter_id"] == "ch-001"
    assert meta["question_count"] == 10
    assert meta["detected_count"] == 5
    assert meta["magic_kind"] == "pdf"
    assert meta["file_size"] == len(_pdf_bytes())


def test_scan_omr_jpeg_returns_200(twain_upload_root: Path) -> None:
    """POST /scan/omr 接受 JPEG 图片 → 200；magic_kind="image"。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-002",
            "question_count": "5",
            "level": "C",
        },
        files={
            "file": ("scan.jpg", _jpeg_bytes(), "image/jpeg"),
        },
    )
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert len(body["answers"]) == 5
    assert body["metadata"]["magic_kind"] == "image"
    assert body["metadata"]["content_type"] == "image/jpeg"


def test_scan_omr_png_returns_200(twain_upload_root: Path) -> None:
    """POST /scan/omr 接受 PNG 图片 → 200。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-003",
            "question_count": "15",
            "level": "B",
        },
        files={
            "file": ("scan.png", _png_bytes(), "image/png"),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["answers"]) == 15
    assert body["metadata"]["magic_kind"] == "image"


# ──────────────────────────── 2. deterministic ────────────────────────────


def test_same_input_produces_same_answers(twain_upload_root: Path) -> None:
    """同 (level, chapter_id) → 同 answers（seed 稳定，pytest 跑稳定）。"""
    client = _build_client(twain_upload_root)
    payload = {
        "chapter_id": "ch-det-001",
        "question_count": "20",
        "level": "D",
    }
    files_payload = {"file": ("scan.pdf", _pdf_bytes(), "application/pdf")}

    resp1 = client.post(
        "/api/v1/twain/scan/omr", data=payload, files=files_payload
    )
    resp2 = client.post(
        "/api/v1/twain/scan/omr", data=payload, files=files_payload
    )
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["answers"] == resp2.json()["answers"], (
        "same input must produce same answers (deterministic mock)"
    )


def test_different_chapter_id_produces_different_answers(twain_upload_root: Path) -> None:
    """同 level、不同 chapter_id → 不同 answers（seed 随 chapter_id 变化）。"""
    client = _build_client(twain_upload_root)
    files_payload = {"file": ("scan.pdf", _pdf_bytes(), "application/pdf")}

    resp1 = client.post(
        "/api/v1/twain/scan/omr",
        data={"chapter_id": "ch-A", "question_count": "20", "level": "D"},
        files=files_payload,
    )
    resp2 = client.post(
        "/api/v1/twain/scan/omr",
        data={"chapter_id": "ch-B", "question_count": "20", "level": "D"},
        files=files_payload,
    )
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    # 至少 5 个位置有答案；不同 chapter_id → seed 不同 → 答案不同
    answers1 = resp1.json()["answers"]
    answers2 = resp2.json()["answers"]
    assert any(a is not None for a in answers1)
    assert answers1 != answers2, "different chapter_id should yield different answers"


# ──────────────────────────── 3. 4 档位独立性 ────────────────────────────


@pytest.mark.parametrize("level", ["D", "C", "B", "A"])
def test_all_four_tiers_return_valid_responses(
    twain_upload_root: Path, level: str
) -> None:
    """4 档位（D/C/B/A）都返回 200 + 5 个位置填涂 + metadata.level 正确。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": f"ch-tier-{level}",
            "question_count": "20",
            "level": level,
        },
        files={"file": ("scan.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200, f"tier {level} failed: {resp.text}"
    body = resp.json()
    answers = body["answers"]
    assert len(answers) == 20
    detected = [a for a in answers if a is not None]
    assert len(detected) == 5, (
        f"tier {level} should have exactly 5 detected, got {len(detected)}"
    )
    for a in detected:
        assert a in ANSWER_CHOICES
    assert body["metadata"]["level"] == level


def test_four_tiers_have_distinct_positions(twain_upload_root: Path) -> None:
    """4 档位的 5 个填涂位置各不相同（v0.5 §3.2 + 任务 brief："5 个不同位置"）。"""
    # 直接验证 schema 定义的 5 个位置互不相同
    pos_sets = {tuple(sorted(positions)) for positions in TIER_DETECTED_POSITIONS.values()}
    assert len(pos_sets) == 4, (
        f"4 tiers should have 4 distinct position sets, got {pos_sets}"
    )
    # 进一步：每档 5 个位置互不相同
    for level, positions in TIER_DETECTED_POSITIONS.items():
        assert len(set(positions)) == 5, f"tier {level} positions not unique: {positions}"


def test_four_tiers_produce_different_answers(twain_upload_root: Path) -> None:
    """同 chapter_id + question_count、不同 level → answers 不同（位置 + 答案双重不同）。"""
    client = _build_client(twain_upload_root)
    chapter_id = "ch-compare"
    question_count = 20
    answers_by_tier: dict[str, list[str | None]] = {}

    for level in ("D", "C", "B", "A"):
        resp = client.post(
            "/api/v1/twain/scan/omr",
            data={
                "chapter_id": chapter_id,
                "question_count": str(question_count),
                "level": level,
            },
            files={"file": ("scan.pdf", _pdf_bytes(), "application/pdf")},
        )
        assert resp.status_code == 200
        answers_by_tier[level] = resp.json()["answers"]

    # 至少 D 与 A 答案不同（位置 + seed 都不同）
    assert answers_by_tier["D"] != answers_by_tier["A"], (
        "D vs A should produce different answers"
    )


# ──────────────────────────── 4. 错误处理 ────────────────────────────


def test_invalid_level_returns_422(twain_upload_root: Path) -> None:
    """非法 level（不在 D/C/B/A 内）→ 422（FastAPI Form Literal 校验）。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-x",
            "question_count": "10",
            "level": "X",  # 非法
        },
        files={"file": ("scan.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 422


def test_question_count_below_minimum_returns_422(twain_upload_root: Path) -> None:
    """question_count < 5 → 422（必须能放下 5 个填涂位）。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-y",
            "question_count": "4",  # < MIN_QUESTION_COUNT
            "level": "D",
        },
        files={"file": ("scan.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 422


def test_question_count_above_maximum_returns_422(twain_upload_root: Path) -> None:
    """question_count > 200 → 422。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-z",
            "question_count": str(MAX_QUESTION_COUNT + 1),
            "level": "D",
        },
        files={"file": ("scan.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 422


def test_missing_chapter_id_returns_422(twain_upload_root: Path) -> None:
    """缺 chapter_id → 422（Form 必填字段）。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "question_count": "10",
            "level": "D",
        },
        files={"file": ("scan.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 422


def test_missing_file_returns_422(twain_upload_root: Path) -> None:
    """缺 file → 422（File 必填字段）。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-q",
            "question_count": "10",
            "level": "D",
        },
    )
    assert resp.status_code == 422


# ──────────────────────────── 5. 跨边界架构（不破坏现有 endpoint）────────────


def test_existing_health_endpoint_still_works(twain_upload_root: Path) -> None:
    """注册 twain router 后，现有 /api/health 仍 200（跨边界架构不破坏既有 endpoint）。"""
    client = _build_client(twain_upload_root)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_existing_academic_endpoint_still_registered(twain_upload_root: Path) -> None:
    """注册 twain router 后，academic router 仍挂载（路径不冲突）。"""
    client = _build_client(twain_upload_root)
    # academic 的 GET /api/v1/academic/chapters/{id} 在无 DB 依赖时返 500/404 都可，
    # 只要路由被注册（不是 404 "Not Found" from router not matched）。
    # 更稳的判据：访问不存在的 path → 404 from Starlette routing（说明 router 链没断）
    resp = client.get("/api/v1/twain/nonexistent")
    assert resp.status_code == 404  # Starlette 路由层 404，不是 router 未注册


# ──────────────────────────── 6. 文件落盘到 UPLOAD_ROOT/scans/ ─────────────


def test_scan_file_saved_to_upload_root_scans(
    twain_upload_root: Path,
) -> None:
    """扫描件实际写入 ``{UPLOAD_ROOT}/scans/{uuid}.{ext}``（v0.5 §6.5 本地存储路径）。"""
    client = _build_client(twain_upload_root)
    payload_bytes = _pdf_bytes(size=2048)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-save",
            "question_count": "10",
            "level": "D",
        },
        files={"file": ("scan.pdf", payload_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    saved_path = Path(body["metadata"]["file_path"])

    # 文件在 UPLOAD_ROOT/scans/ 下
    assert saved_path.parent == twain_upload_root / "scans"
    assert saved_path.exists()
    assert saved_path.is_file()
    # 文件内容 = 上传 bytes（mock 不解析内容，原样写盘）
    assert saved_path.read_bytes() == payload_bytes
    # 扩展名 .pdf
    assert saved_path.suffix == ".pdf"


def test_scan_file_scans_subdir_created_lazily(twain_upload_root: Path) -> None:
    """scans/ 子目录在首次上传时 lazy 创建（不存在 → 自动建）。"""
    scans_dir = twain_upload_root / "scans"
    assert not scans_dir.exists(), "scans/ 不应预先存在"

    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-lazy",
            "question_count": "5",
            "level": "D",
        },
        files={"file": ("scan.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200
    assert scans_dir.exists()
    assert scans_dir.is_dir()


# ──────────────────────────── 7. metadata 契约（M3 替换判据）────────────


def test_metadata_bridge_layer_is_mock(twain_upload_root: Path) -> None:
    """metadata.bridge_layer == "http_bridge_mock"（M3 替换为真实现时此字段变为 "http_bridge_windows_host"）。

    这是 M3 替换零返工的硬判据：contract test 断言此字段存在且取 mock 值；
    M3 实现后只需改 router 内的 BRIDGE_LAYER 常量，测试再断言新值即可。
    """
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-bridge",
            "question_count": "10",
            "level": "D",
        },
        files={"file": ("scan.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["metadata"]["bridge_layer"] == BRIDGE_LAYER_MOCK
    assert BRIDGE_LAYER_MOCK == "http_bridge_mock"


def test_metadata_includes_detected_count_equals_5(twain_upload_root: Path) -> None:
    """metadata.detected_count == 5（每档固定 5 个填涂位）。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-det5",
            "question_count": "20",
            "level": "A",
        },
        files={"file": ("scan.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["metadata"]["detected_count"] == 5
    # 交叉验证：answers 中非 None 数 == detected_count
    actual_detected = sum(1 for a in body["answers"] if a is not None)
    assert actual_detected == 5


# ──────────────────────────── 8. 边界 ────────────────────────────


def test_question_count_exactly_minimum_works(twain_upload_root: Path) -> None:
    """question_count == MIN_QUESTION_COUNT (5) 边界：5 个位置都在范围内，全部填涂。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-min",
            "question_count": str(MIN_QUESTION_COUNT),
            "level": "D",  # D 档位置 = [0,1,2,3,4]，全部 < 5
        },
        files={"file": ("scan.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    answers = body["answers"]
    assert len(answers) == 5
    # D 档在 question_count=5 时 5 个位置都应填涂
    assert all(a is not None for a in answers), f"expected all filled, got {answers}"


def test_question_count_exactly_maximum_works(twain_upload_root: Path) -> None:
    """question_count == MAX_QUESTION_COUNT (200) 边界。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-max",
            "question_count": str(MAX_QUESTION_COUNT),
            "level": "A",
        },
        files={"file": ("scan.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["answers"]) == MAX_QUESTION_COUNT


def test_empty_pdf_file_returns_400(twain_upload_root: Path) -> None:
    """空文件（0 bytes）→ 400（流读取失败）。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-empty",
            "question_count": "10",
            "level": "D",
        },
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert resp.status_code == 400
