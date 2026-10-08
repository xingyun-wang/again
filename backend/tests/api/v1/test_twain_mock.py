"""TWAIN HTTP 桥 mock 端到端测试（M2 S0-4：D-M2-4 拍板 + 3 补丁 A/B/C）。

覆盖：
1. 契约稳定：POST /api/v1/twain/scan/omr 接受 multipart → 返回 ScanOMRResponse
2. 契约不外泄：metadata 不含 file_path / level（出题侧概念不进桥契约）
3. deterministic：同 chapter_id → 同 answers（seed 稳定）
4. 不同 chapter_id → 不同 answers
5. 跨边界架构：注册新 router 后现有 endpoint（/api/health）仍工作
6. 错误处理：缺字段 / 非法 question_count / chapter_id 越界 → 422
7. 文件落盘：UPLOAD_ROOT/scans/{file_id}.{ext} 实际写盘（用 scan_id 定位）
8. metadata 契约：bridge_layer="http_bridge_mock"（M3 替换时零返工判据）
9. scan_id 唯一性：每次请求生成不同 uuid4
10. detected_count 一致性：metadata.detected_count == 实际非 None 数
11. 边界：question_count = 5 (min) / 200 (max) / 空文件
12. 内部 invariant：mock 前 5 位置填涂（与 MOCK_DETECTED_POSITIONS 一致）

设计要点：
- 走 e2e 路径（TestClient + create_app），与 test_health.py 同模式
- UPLOAD_ROOT 重定向到 tmp_path（dev box 上 /app/data/uploads 不存在）
- ruff + mypy 全过
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
    MOCK_DETECTED_POSITIONS,
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
    """生成测试用 JPEG 字节。"""
    header = b"\xff\xd8\xff\xe0" + b"X" * 16
    padding = b"Y" * max(0, size - len(header))
    return header + padding


def _png_bytes(size: int = 1024) -> bytes:
    """生成测试用 PNG 字节。"""
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
    - 请求：multipart/form-data（file + chapter_id + question_count；无 level）
    - 响应：JSON 含 answers（list）+ metadata（dict，含 bridge_layer + scan_id）
    - metadata **不**含 file_path（泄漏内部目录）/ level（出题侧概念）
    """
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-001",
            "question_count": "10",
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
        "chapter_id",
        "question_count",
        "detected_count",
        "scan_id",
        "file_size",
        "content_type",
        "magic_kind",
        "timestamp",
    }
    assert required_meta_keys.issubset(meta.keys()), (
        f"missing metadata keys: {required_meta_keys - meta.keys()}"
    )
    # metadata 严禁暴露内部目录（信息泄漏防护）
    assert "file_path" not in meta, "metadata must not expose internal file_path"
    # metadata 严禁暴露 level（出题侧概念不进桥契约）
    assert "level" not in meta, "metadata must not expose level (out of bridge scope)"

    # 必含字段值
    assert meta["bridge_layer"] == BRIDGE_LAYER_MOCK
    assert meta["chapter_id"] == "ch-001"
    assert meta["question_count"] == 10
    assert meta["detected_count"] == 5
    assert meta["magic_kind"] == "pdf"
    assert meta["file_size"] == len(_pdf_bytes())
    # scan_id 是 32 字符 hex（uuid4）
    assert len(meta["scan_id"]) == 32
    assert all(c in "0123456789abcdef" for c in meta["scan_id"])


def test_scan_omr_jpeg_returns_200(twain_upload_root: Path) -> None:
    """POST /scan/omr 接受 JPEG 图片 → 200；magic_kind="image"。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-002",
            "question_count": "5",
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


def test_same_chapter_id_produces_same_answers(twain_upload_root: Path) -> None:
    """同 chapter_id → 同 answers（seed 稳定，pytest 跑稳定）。"""
    client = _build_client(twain_upload_root)
    payload = {
        "chapter_id": "ch-det-001",
        "question_count": "20",
    }
    files_payload = {"file": ("scan.pdf", _pdf_bytes(), "application/pdf")}

    resp1 = client.post("/api/v1/twain/scan/omr", data=payload, files=files_payload)
    resp2 = client.post("/api/v1/twain/scan/omr", data=payload, files=files_payload)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["answers"] == resp2.json()["answers"], (
        "same chapter_id must produce same answers (deterministic mock)"
    )


def test_different_chapter_id_produces_different_answers(
    twain_upload_root: Path,
) -> None:
    """不同 chapter_id → 不同 answers（seed 随 chapter_id 变化）。"""
    client = _build_client(twain_upload_root)
    files_payload = {"file": ("scan.pdf", _pdf_bytes(), "application/pdf")}

    resp1 = client.post(
        "/api/v1/twain/scan/omr",
        data={"chapter_id": "ch-A", "question_count": "20"},
        files=files_payload,
    )
    resp2 = client.post(
        "/api/v1/twain/scan/omr",
        data={"chapter_id": "ch-B", "question_count": "20"},
        files=files_payload,
    )
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    answers1 = resp1.json()["answers"]
    answers2 = resp2.json()["answers"]
    assert any(a is not None for a in answers1)
    assert answers1 != answers2, "different chapter_id should yield different answers"


# ──────────────────────────── 3. 错误处理 ────────────────────────────


def test_question_count_below_minimum_returns_422(twain_upload_root: Path) -> None:
    """question_count < 5 → 422（必须能放下 5 个填涂位）。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-y",
            "question_count": "4",  # < MIN_QUESTION_COUNT
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
        },
        files={"file": ("scan.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 422


def test_chapter_id_above_max_length_returns_422(twain_upload_root: Path) -> None:
    """chapter_id > 128 字符 → 422。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "x" * 129,  # > 128
            "question_count": "10",
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
        },
    )
    assert resp.status_code == 422


# ──────────────────────────── 4. 跨边界架构（不破坏现有 endpoint）────────────


def test_existing_health_endpoint_still_works(twain_upload_root: Path) -> None:
    """注册 twain router 后，现有 /api/health 仍 200。"""
    client = _build_client(twain_upload_root)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_twain_router_registered(twain_upload_root: Path) -> None:
    """注册 twain router 后，路径可达（不存在的子路径 → 404 from Starlette routing）。"""
    client = _build_client(twain_upload_root)
    resp = client.get("/api/v1/twain/nonexistent")
    assert resp.status_code == 404


# ──────────────────────────── 5. 文件落盘到 UPLOAD_ROOT/scans/ ─────────────


def test_scan_file_saved_to_upload_root_scans(
    twain_upload_root: Path,
) -> None:
    """扫描件实际写入 ``{UPLOAD_ROOT}/scans/{file_id}.{ext}``（用 scan_id 定位文件，不依赖 file_path）。"""
    client = _build_client(twain_upload_root)
    payload_bytes = _pdf_bytes(size=2048)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-save",
            "question_count": "10",
        },
        files={"file": ("scan.pdf", payload_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    scan_id = body["metadata"]["scan_id"]
    # metadata 必须不含 file_path（不泄漏内部目录）
    assert "file_path" not in body["metadata"], "file_path must not leak to client"

    # 用 scan_id 定位文件（glob 而非依赖 metadata file_path）
    saved_files = list((twain_upload_root / "scans").iterdir())
    assert len(saved_files) == 1
    saved = saved_files[0]
    assert saved.stem == scan_id
    assert saved.suffix == ".pdf"
    # 文件内容 = 上传 bytes（mock 不解析内容，原样写盘）
    assert saved.read_bytes() == payload_bytes


def test_scan_file_scans_subdir_created_lazily(twain_upload_root: Path) -> None:
    """scans/ 子目录在首次上传时 lazy 创建。"""
    scans_dir = twain_upload_root / "scans"
    assert not scans_dir.exists()

    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-lazy",
            "question_count": "5",
        },
        files={"file": ("scan.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200
    assert scans_dir.exists()
    assert scans_dir.is_dir()


# ──────────────────────────── 6. metadata 契约（M3 替换判据）────────────


def test_metadata_bridge_layer_is_mock(twain_upload_root: Path) -> None:
    """metadata.bridge_layer == "http_bridge_mock"（M3 替换为真实现时此字段变为 "http_bridge_windows_host"）。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-bridge",
            "question_count": "10",
        },
        files={"file": ("scan.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["metadata"]["bridge_layer"] == BRIDGE_LAYER_MOCK
    assert BRIDGE_LAYER_MOCK == "http_bridge_mock"


def test_metadata_scan_id_is_unique_per_request(twain_upload_root: Path) -> None:
    """每次请求生成不同 scan_id（uuid4 唯一性；客户端可作 idempotency key）。"""
    client = _build_client(twain_upload_root)
    payload = {"chapter_id": "ch-uuid", "question_count": "10"}
    files_payload = {"file": ("scan.pdf", _pdf_bytes(), "application/pdf")}

    resp1 = client.post("/api/v1/twain/scan/omr", data=payload, files=files_payload)
    resp2 = client.post("/api/v1/twain/scan/omr", data=payload, files=files_payload)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    scan_id1 = resp1.json()["metadata"]["scan_id"]
    scan_id2 = resp2.json()["metadata"]["scan_id"]
    assert scan_id1 != scan_id2, "scan_id must be unique per request"


@pytest.mark.parametrize("question_count", [5, 10, 50, 200])
def test_metadata_detected_count_matches_actual_answers(
    twain_upload_root: Path, question_count: int
) -> None:
    """metadata.detected_count == answers 中非 None 的实际数（不是硬编码 5）。

    防 S0-4 dcab4f8 类契约不变量静默破坏（docstring 写 5，实现对 C/B/A 档位实际不是 5）。
    这里测 4 个 question_count 边界值，确认 detected_count 与 answers 一致。
    """
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": f"ch-qc-{question_count}",
            "question_count": str(question_count),
        },
        files={"file": ("scan.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    meta_detected = body["metadata"]["detected_count"]
    actual_detected = sum(1 for a in body["answers"] if a is not None)
    assert meta_detected == actual_detected, (
        f"detected_count mismatch at qc={question_count}: "
        f"meta={meta_detected} actual={actual_detected}"
    )


# ──────────────────────────── 7. 边界 ────────────────────────────


def test_question_count_exactly_minimum_works(twain_upload_root: Path) -> None:
    """question_count == MIN_QUESTION_COUNT (5) 边界：5 个位置都在范围内，全部填涂。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-min",
            "question_count": str(MIN_QUESTION_COUNT),
        },
        files={"file": ("scan.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    answers = body["answers"]
    assert len(answers) == 5
    assert all(a is not None for a in answers), f"expected all filled, got {answers}"
    assert body["metadata"]["detected_count"] == 5


def test_question_count_exactly_maximum_works(twain_upload_root: Path) -> None:
    """question_count == MAX_QUESTION_COUNT (200) 边界。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-max",
            "question_count": str(MAX_QUESTION_COUNT),
        },
        files={"file": ("scan.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["answers"]) == MAX_QUESTION_COUNT
    # 前 5 位置填涂，其余 None
    assert sum(1 for a in body["answers"] if a is not None) == 5


def test_empty_pdf_file_returns_400(twain_upload_root: Path) -> None:
    """空文件（0 bytes）→ 400。"""
    client = _build_client(twain_upload_root)
    resp = client.post(
        "/api/v1/twain/scan/omr",
        data={
            "chapter_id": "ch-empty",
            "question_count": "10",
        },
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert resp.status_code == 400


# ──────────────────────────── 8. 内部 invariant（mock 位置集）────────────


def test_mock_detected_positions_invariant() -> None:
    """mock 内部位置集 = 5 个 0-based 位置（前 5 题；0-4 全包）。"""
    assert len(MOCK_DETECTED_POSITIONS) == 5
    assert MOCK_DETECTED_POSITIONS == (0, 1, 2, 3, 4)
    assert all(isinstance(p, int) and p >= 0 for p in MOCK_DETECTED_POSITIONS)
    assert len(set(MOCK_DETECTED_POSITIONS)) == 5  # 互不重复


def test_mock_detected_positions_within_min_question_count() -> None:
    """所有 mock 位置 < MIN_QUESTION_COUNT（保证 question_count = 5 时全部填涂 = detected_count 恒为 5）。"""
    assert max(MOCK_DETECTED_POSITIONS) < MIN_QUESTION_COUNT
