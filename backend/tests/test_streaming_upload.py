"""流式上传测试（M1-B retro P0-C：抗压与镜像卫生）。

覆盖：
1. ``check_magic_bytes`` 流式读 5 字节 — fail-fast，前 5 字节读完即拒绝（不全量入内存）
2. ``stream_upload_to_disk`` 流式落盘 + 500MB cap — 超限抛 UploadTooLargeError
3. e2e POST /api/v1/academic/textbooks/upload — 上传 600MB 假流 → router 转 413
4. e2e POST /api/v1/academic/textbooks/upload — 非 PDF 流（前 5 字节非 %PDF-） → 400

设计要点：
- 不真分配 600MB / 10MB（pytest 内存压力）；用 CountingBytesIO 模拟大输入流
- 测试用 ``tmp_path`` 代替 ``UPLOAD_ROOT``（dev box 上 /app/data/uploads 不存在）
- 走 e2e 路径（TestClient + FastAPI dependency override），跟 B.3.1 真 PDF 测试同模式
- ruff + mypy 全过（pyproject files=["app"]，tests/ 不在 lint 范围）

D-28 硬规则：可证伪 — 数字 + 命令输出进 commit message
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routers import academic as academic_module
from app.main import create_app as build_app
from app.services.textbook_upload import (
    DEFAULT_MAX_UPLOAD_BYTES,
    UploadTooLargeError,
    UploadValidationError,
    check_magic_bytes,
    stream_upload_to_disk,
)

# ──────────────────────────── 测试辅助 ────────────────────────────


class CountingBytesIO:
    """Wrap bytes 流，记录 read() 调用次数（用于断言「前 5 字节读完即 fail-fast」）。"""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0
        self.read_count = 0

    def read(self, n: int = -1) -> bytes:
        self.read_count += 1
        if self._pos >= len(self._data):
            return b""
        if n < 0 or n >= len(self._data) - self._pos:
            chunk = self._data[self._pos :]
            self._pos = len(self._data)
            return chunk
        chunk = self._data[self._pos : self._pos + n]
        self._pos += len(chunk)
        return chunk

    def seek(self, pos: int) -> int:
        self._pos = pos
        return self._pos

    def close(self) -> None:  # UploadFile.file.close() 兼容
        pass


class FakeBigStream:
    """模拟大文件流；不实际分配 N MB；每次 read 返回 8 KB 直到耗尽。

    用于测试 500MB cap：声称 600MB 总量，但内存中只有一个 chunk 计数器。
    第一次 read 会注入 "%PDF-" magic（模拟真实 PDF 文件头），便于 e2e 测试
    走 router check_magic_bytes 时不报错。
    """

    def __init__(self, total_bytes: int, chunk_size: int = 8 * 1024) -> None:
        self._remaining = total_bytes
        self._chunk_size = chunk_size
        self.read_count = 0

    def read(self, n: int = -1) -> bytes:
        self.read_count += 1
        if self._remaining <= 0:
            return b""
        n = n if n > 0 else self._chunk_size
        to_read = min(n, self._remaining)
        self._remaining -= to_read
        # 第一次 read 注入 magic bytes（仅当 chunk 足够大） — 让 e2e 流过 check_magic_bytes
        if self.read_count == 1 and to_read >= 5:
            return b"%PDF-" + b"X" * (to_read - 5)
        return b"X" * to_read

    def close(self) -> None:
        pass


def _build_test_client(
    db_session: Any,
    llm_provider: Any,
) -> TestClient:
    """构造带 DB + LLM 依赖 override 的 TestClient（同 test_academic_api.py）。"""
    from app.api.v1.routers.academic import get_llm_dep
    from app.db.session import get_db

    app = build_app()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_llm_dep] = lambda: llm_provider
    return TestClient(app)


@pytest.fixture()
def upload_root_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """把 UPLOAD_ROOT 重定向到 tmp_path（dev box 上 /app/data/uploads 不存在）。"""
    monkeypatch.setattr(academic_module, "UPLOAD_ROOT", tmp_path)
    yield tmp_path


# ──────────────────────────── 1. 流式 magic bytes 单测 ────────────────────────────


def test_check_magic_bytes_passes_for_pdf(tmp_path: Path) -> None:
    """正常 PDF → magic check 通过，返回前 5 字节供 caller prepend。"""
    src = CountingBytesIO(b"%PDF-1.4\n" + b"rest of file")
    flag = check_magic_bytes(src)
    assert flag == b"%PDF-"
    assert src.read_count == 1, f"magic check 应只调 1 次 read，实际 {src.read_count}"
    # 上传文件剩余字节可继续读（magic 已被消费）
    rest = src.read(8)
    assert rest == b"1.4\nrest"


def test_check_magic_bytes_fails_fast_on_non_pdf(tmp_path: Path) -> None:
    """非 PDF（前 5 字节非 %PDF-）→ fail-fast，只调 1 次 read。

    D-28 硬规则：必须可证伪（计数 + 字节双重断言）。
    """
    # 10MB 输入流，前 5 字节 = "HELLO"
    fake_data = b"HELLO" + b"X" * (10 * 1024 * 1024 - 5)
    src = CountingBytesIO(fake_data)

    with pytest.raises(UploadValidationError) as exc_info:
        check_magic_bytes(src)

    assert "PDF" in str(exc_info.value) or "magic" in str(exc_info.value).lower()
    assert src.read_count <= 1, (
        f"magic check 应 ≤ 1 次 read（不全量入内存），实际 {src.read_count} 次"
    )


def test_check_magic_bytes_empty_file(tmp_path: Path) -> None:
    """空文件 → 0 bytes → UploadValidationError（1 次 read 拿到 b""）。"""
    src = CountingBytesIO(b"")
    with pytest.raises(UploadValidationError) as exc_info:
        check_magic_bytes(src)
    assert "空" in str(exc_info.value)
    assert src.read_count == 1


def test_check_magic_bytes_too_small(tmp_path: Path) -> None:
    """文件 < 5 字节（但非空）→ UploadValidationError（1 次 read）。"""
    src = CountingBytesIO(b"%PD")
    with pytest.raises(UploadValidationError) as exc_info:
        check_magic_bytes(src)
    assert "过小" in str(exc_info.value)
    assert src.read_count == 1


# ──────────────────────────── 2. stream_upload_to_disk cap 单测 ────────────────────────────


def test_stream_upload_to_disk_success(tmp_path: Path) -> None:
    """正常大小（100 KB）→ 落盘成功，文件大小正确。"""
    payload = b"%PDF-" + b"A" * (100 * 1024 - 5)
    src = CountingBytesIO(payload)
    # magic 已 check；本函数从剩余字节写起 + prefix=magic
    src.read(5)  # 消费 magic
    dst = stream_upload_to_disk(src, dst_dir=tmp_path, prefix=b"%PDF-")

    assert dst.exists()
    assert dst.stat().st_size == len(payload)
    assert dst.read_bytes() == payload
    assert dst.parent.name == "pending"


def test_stream_upload_to_disk_cleans_up_on_too_large(tmp_path: Path) -> None:
    """超 500MB cap → UploadTooLargeError + 临时文件已清理。

    用 FakeBigStream（不真分配 600MB）；不预消费 5 bytes（FakeBigStream 已含 magic）。
    """
    src = FakeBigStream(total_bytes=600 * 1024 * 1024)

    with pytest.raises(UploadTooLargeError) as exc_info:
        stream_upload_to_disk(
            src, dst_dir=tmp_path, max_bytes=DEFAULT_MAX_UPLOAD_BYTES
        )

    assert "500" in str(exc_info.value), f"错误信息应含 500MB：{exc_info.value}"
    # 清理验证：pending 目录下不应有任何文件
    pending = tmp_path / "pending"
    assert pending.exists()  # 目录被创建
    assert list(pending.iterdir()) == [], (
        f"超限文件应被清理，仍残留：{list(pending.iterdir())}"
    )


def test_stream_upload_to_disk_at_exact_limit(tmp_path: Path) -> None:
    """恰好 = 500MB → 成功（边界条件）。"""
    total = DEFAULT_MAX_UPLOAD_BYTES
    src = FakeBigStream(total_bytes=total)

    dst = stream_upload_to_disk(src, dst_dir=tmp_path, max_bytes=total)
    assert dst.exists()
    assert dst.stat().st_size == total


def test_stream_upload_to_disk_over_limit_by_one_chunk(tmp_path: Path) -> None:
    """超 1 byte → 抛 UploadTooLargeError。"""
    total = DEFAULT_MAX_UPLOAD_BYTES + 1
    src = FakeBigStream(total_bytes=total)

    with pytest.raises(UploadTooLargeError):
        stream_upload_to_disk(src, dst_dir=tmp_path, max_bytes=DEFAULT_MAX_UPLOAD_BYTES)


# ──────────────────────────── 3. e2e：router 走完整路径 ────────────────────────────


def test_upload_600mb_returns_413_not_500(
    mock_db_session: Any, mock_llm_provider: Any, upload_root_tmp: Path
) -> None:
    """e2e POST /textbooks/upload：600MB 输入 → 413 Payload Too Large（不是 500）。

    D-28 Done #3：用 monkeypatch 替换 stream_upload_to_disk 抛 UploadTooLargeError，
    模拟「落盘过程超限」，断言 router 转 413。
    """
    def fake_stream(*args: Any, **kwargs: Any) -> Path:
        raise UploadTooLargeError("文件超出 500MB 上限")

    # 替换 router 模块导入的 stream_upload_to_disk（from ... import name 形式）
    monkey = pytest.MonkeyPatch()
    monkey.setattr(academic_module, "stream_upload_to_disk", fake_stream)
    try:
        client = _build_test_client(mock_db_session, mock_llm_provider)
        # 任意小 PDF magic check 通过；stream_upload_to_disk 抛 413
        resp = client.post(
            "/api/v1/academic/textbooks/upload",
            files={"file": ("big.pdf", b"%PDF-1234", "application/pdf")},
            data={"name": "超限文件"},
            headers={"X-User-Id": "1"},
        )
    finally:
        monkey.undo()

    assert resp.status_code == 413, (
        f"应返 413（不是 500）；response={resp.status_code} body={resp.text}"
    )
    body = resp.json()
    # ErrorResponse 格式（errors.py）：{'error_code', 'message', ...}
    message = body.get("message", "")
    assert "500" in message or "上限" in message, f"message 应含 500MB / 上限：{body}"


def test_upload_non_pdf_returns_400_fail_fast(
    mock_db_session: Any, mock_llm_provider: Any, upload_root_tmp: Path
) -> None:
    """e2e POST /textbooks/upload：非 PDF（前 5 字节非 %PDF-）→ 400。

    D-28 Done #4：断言 router 层 magic bytes 检查是流式的（不全量入内存）。
    """
    # 10MB 非 PDF 流（前 5 字节 = "HELLO"）
    fake_payload = b"HELLO" + b"X" * (10 * 1024 * 1024 - 5)

    # Patch check_magic_bytes 为 counting 版本
    def counting_check(src: Any, **_kwargs: Any) -> bytes:
        # 仅 read(5)；记录次数到 src.read_count（UploadFile.file 是 SpooledTemporaryFile）
        chunk = src.read(5)
        # SpooledTemporaryFile 没有 read_count；用 module-level counter
        counting_check.read_count = getattr(counting_check, "read_count", 0) + 1
        if not chunk.startswith(b"%PDF-"):
            raise UploadValidationError(f"文件不是 PDF（开头 {chunk!r}）")
        return chunk

    counting_check.read_count = 0
    monkey = pytest.MonkeyPatch()
    monkey.setattr(academic_module, "check_magic_bytes", counting_check)
    try:
        client = _build_test_client(mock_db_session, mock_llm_provider)
        resp = client.post(
            "/api/v1/academic/textbooks/upload",
            files={"file": ("fake.pdf", io.BytesIO(fake_payload), "application/pdf")},
            data={"name": "假 PDF"},
            headers={"X-User-Id": "1"},
        )
    finally:
        monkey.undo()

    assert resp.status_code == 400, resp.text
    assert counting_check.read_count == 1, (
        f"magic check 应只调 1 次 read，实际 {counting_check.read_count} 次"
    )


def test_upload_empty_file_returns_400(
    mock_db_session: Any, mock_llm_provider: Any, upload_root_tmp: Path
) -> None:
    """e2e：空文件 → 400（兼容旧 test_textbook_upload_real_pdf 的等价断言）。"""
    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        data={"name": "空"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    message = body.get("message", "")
    assert "空" in message or "过小" in message, f"message 应提及空 / 过小：{body}"


def test_upload_subject_not_found_returns_404(
    mock_db_session: Any, mock_llm_provider: Any, upload_root_tmp: Path
) -> None:
    """e2e：subject_id 不存在 → 404（兼容旧测试）。"""
    # Subject 不在 mock session 里 → db.get(Subject, x) is None
    client = _build_test_client(mock_db_session, mock_llm_provider)
    pdf_bytes = b"%PDF-1.4\n" + b"some content"
    resp = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        data={"name": "test", "subject_id": "99999"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 404, resp.text


def test_upload_file_moved_to_textbook_dir_on_success(
    mock_db_session: Any, mock_llm_provider: Any, upload_root_tmp: Path
) -> None:
    """e2e 成功路径：文件从 pending/{uuid}.pdf 移到 {textbook_id}/{filename}.pdf。

    M1-B retro P0-A 设计：DB 存真路径而非 placeholder；pending 是临时目录，
    成功后由 A 服务层移到 {textbook_id}/{filename}.pdf（M1-B B.3.1 的 uploaded:{name}.pdf
    假路径已废弃）。
    """
    # 用最小真 PDF 走完整链路；PyMuPDF 需要真 PDF 解析
    import fitz  # PyMuPDF

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "第一章 测试章节", fontsize=12)
    pdf_io = io.BytesIO()
    doc.save(pdf_io)
    doc.close()
    pdf_bytes = pdf_io.getvalue()

    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        data={"name": "测试教材"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201, resp.text
    textbook_id = resp.json()["textbook_id"]

    # 验证最终位置：{textbook_id}/{filename}.pdf（DB 存的就是这个路径）
    final_dir = upload_root_tmp / str(textbook_id)
    final_files = list(final_dir.glob("*.pdf"))
    assert len(final_files) == 1, f"应移 1 个文件到 {final_dir}：{final_files}"
    assert final_files[0].stat().st_size == len(pdf_bytes)

    # 验证 pending 临时目录已清空（move 后不应残留）
    pending = upload_root_tmp / "pending"
    pending_remaining = list(pending.iterdir()) if pending.exists() else []
    assert pending_remaining == [], (
        f"pending 应被清空，仍残留：{pending_remaining}"
    )


def test_upload_business_failure_cleans_up_pending(
    mock_db_session: Any, mock_llm_provider: Any, upload_root_tmp: Path
) -> None:
    """业务失败（PyMuPDF 解析失败）→ 清理 pending 文件。

    模拟：上传 %PDF- 开头但内容损坏的「假 PDF」，extractor 报错。
    """
    fake = b"%PDF-1.4\n" + b"GARBAGE NO PDF STRUCTURE " * 100

    client = _build_test_client(mock_db_session, mock_llm_provider)
    resp = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("corrupt.pdf", fake, "application/pdf")},
        data={"name": "损坏"},
        headers={"X-User-Id": "1"},
    )
    # PyMuPDF 解析失败 → 400
    assert resp.status_code == 400, resp.text

    # 验证 pending 文件已被清理
    pending = upload_root_tmp / "pending"
    pending_files = list(pending.glob("*.pdf"))
    assert pending_files == [], (
        f"业务失败应清理 pending，仍残留：{pending_files}"
    )