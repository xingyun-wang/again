"""P0-N1 subject_id 归属校验测试（M1-B retro 第二轮审查发现）。

D-32 第 3 类 安全/归属边界：D-35 不可豁免。
D-37 硬规则（可证伪性）：测试在 fail-open 实现下必须 FAIL，证明正确实现必要性。

测试矩阵：
1. test_p0n1_correct_subject_ownership_returns_404_for_cross_user
   — 正确实现：user_2 挂 user_1 subject 上传 → 404
2. test_p0n1_full_fail_open_would_leak_data_returns_201
   — D-37 fail-open：router + service 双层都被 monkeypatch 为 fail-open
     → user_2 挂 user_1 subject → 201 + 数据泄漏（证明旧实现是灾难性的）

fixture 复用：
- mock_db_session / mock_llm_provider 来自 conftest.py
- 本文件内本地 mock_user_1 / mock_user_2 / user_1_subject（避免跨文件 fixture 耦合）

Python 3.8 兼容（dev box）：
- 模块顶部 patch typing.Annotated + enum.StrEnum（与 test_cross_user_isolation.py 对齐）
- 所有 app.* import 延迟到 fixture / test 函数体（避免 collect 阶段重复加载）
"""

from __future__ import annotations

import enum
import sys
import typing

if not hasattr(typing, "Annotated"):
    # Python 3.8 兼容：typing.Annotated 在 py3.9+ 才存在
    import typing_extensions

    typing.Annotated = typing_extensions.Annotated  # type: ignore[attr-defined]

if not hasattr(enum, "StrEnum"):
    # Python 3.8 兼容：enum.StrEnum 在 py3.11+ 才存在
    class _StrEnumShim(str, enum.Enum):  # noqa: UP042
        """Dev box shim for enum.StrEnum（py3.11+ 的原生类型）。"""

    enum.StrEnum = _StrEnumShim  # type: ignore[attr-defined]


from io import BytesIO
from typing import Any

import pytest

# ─────────────────────── helpers ─────────────────────────────────────────────


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
    """测试用 user_1（id=1；与 system-seed 区分，is_system_owned=False）。"""
    from app.models import User

    user = User(id=1, name="user-1", is_system_owned=False)
    mock_db_session.add(user)
    mock_db_session.commit()
    mock_db_session.refresh(user)
    return user


@pytest.fixture()
def mock_user_2(mock_db_session):
    """测试用 user_2（id=2）。"""
    from app.models import User

    user = User(id=2, name="user-2", is_system_owned=False)
    mock_db_session.add(user)
    mock_db_session.commit()
    mock_db_session.refresh(user)
    return user


@pytest.fixture()
def user_1_subject(mock_db_session, mock_user_1):
    """user_1 拥有的 Subject（owner_user_id = 1）。

    P0-N1 修复目标资源：user_2 试图上传挂此 subject 应当被拒绝（404）。
    """
    from app.models import GradeLevel, Subject

    sub = Subject(
        name="user_1's subject (高中地理)",
        grade_level=GradeLevel.SENIOR_HIGH,
        owner_user_id=mock_user_1.id,
    )
    mock_db_session.add(sub)
    mock_db_session.commit()
    mock_db_session.refresh(sub)
    return sub


# ─────────────────────── 1. 正确实现：D-32/D-35 硬规则 ─────────────────────────


@pytest.mark.skipif(
    sys.version_info < (3, 9),
    reason="B2 baseline: py3.9+ required for Mapped[list[Class]] (PEP 585) — "
    "本测试依赖 app.models 导入，dev box (py3.8) 跑不动；CI (py3.11) 真跑",
)
def test_p0n1_correct_subject_ownership_returns_404_for_cross_user(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_user_2: Any,
    user_1_subject: Any,
) -> None:
    """正确实现：user_2 上传挂 user_1 的 subject → 404（D-29 / D-32 第 3 类 / D-35）。

    本测试不 monkeypatch 任何东西 — 验证 router + service 双层修复后，
    跨用户归属校验正确触发 404（不是 403，避免 id 存在性泄漏）。
    """
    client = _build_test_client(mock_db_session, mock_llm_provider)
    pdf_bytes = _build_minimal_pdf_bytes()

    response = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        data={
            "name": "user_2 的恶意上传",
            "subject_id": str(user_1_subject.id),
            "grade_level": "senior_high",
        },
        headers={"X-User-Id": str(mock_user_2.id)},
    )

    assert response.status_code == 404, (
        f"P0-N1 正确实现应返 404（user_2 挂 user_1 subject 被拒），"
        f"实际 {response.status_code}：{response.text}"
    )
    # 必须是 404，不是 403（D-29 反 ID 泄漏硬规则）
    assert response.status_code != 403, (
        "P0-N1：返 403 会泄漏 subject_id 存在性（D-29 反 ID 泄漏硬规则）"
    )
    # 响应体不应泄漏 user_1 的 subject 名称
    assert user_1_subject.name not in response.text, (
        "P0-N1：跨用户 404 响应不应包含 user_1 的 subject 名称"
    )


# ─────────────────────── 2. D-37 fail-open 负面测试（核心：可证伪） ─────────


@pytest.mark.skipif(
    sys.version_info < (3, 9),
    reason="B2 baseline: py3.9+ required for Mapped[list[Class]] (PEP 585) — "
    "D-37 fail-open 负面测试，dev box (py3.8) 跑不动；CI (py3.11) 真跑",
)
def test_p0n1_full_fail_open_would_leak_data_returns_201(
    mock_db_session: Any,
    mock_llm_provider: Any,
    mock_user_2: Any,
    user_1_subject: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-37 负面测试：完全 fail-open（router + service 双层都被绕过）→ 数据泄漏。

    本测试模拟 **旧实现** 的完整 fail-open 场景：
    - router._enforce_owner_or_404 被 monkeypatch 为 no-op（不检查 owner）
    - service 层的 defense-in-depth 校验也被 monkeypatch 为 no-op
    （service 是 textbook_upload.upload_textbook_with_extraction 内的 subject
    校验块）

    在此完全 fail-open 场景下：user_2 挂 user_1 subject 上传 → 201 成功，
    教材记录以 owner_user_id=user_2 创建，但挂在 user_1 的 subject 下 —
    数据归属污染（user_1 的 subject 被 user_2 偷挂）。

    可证伪证据：
    - 完全 fail-open 实现（router + service 双层都不过滤 owner）：201 泄漏
    - 正确实现（router + service 任一层过滤 owner）：4xx 拒绝

    本测试断言「完全 fail-open 实现下确实返 201」 — 证明：
    1. 完全 fail-open 是灾难性的（数据泄漏 + 归属污染）
    2. 任何一层正确实现（router 或 service）即可挡住

    注意：单独的 router fail-open 已被 service defense-in-depth 兜底（另
    一个测试覆盖 — service 兜底测试不在本文件，由 service 单元测试覆盖）。
    本测试覆盖「最坏组合」以满足 D-37 可证伪性硬规则。
    """
    # ───── monkeypatch router 层 ─────
    from app.api.v1.routers import academic

    def _router_fail_open(obj: object, user_id: int) -> None:
        """模拟旧实现：完全不检查 owner（no-op）。"""
        return

    monkeypatch.setattr(academic, "_enforce_owner_or_404", _router_fail_open)

    # ───── monkeypatch service 层 defense-in-depth ─────
    # 旧实现没有 service 层 defense-in-depth，所以这里模拟「即使将来加入也
    # 被错误实现成 no-op」的最坏情况。直接 patch 服务函数内的关键校验块
    # 不可行（局部变量）；改为 patch Subject 查询使其返 owner_user_id=2（user_2），
    # 模拟「service 不做 owner 检查只检查存在性」的 fail-open 语义。
    from app.models import Subject as SubjectModel

    real_db_get = mock_db_session.get  # P7：实例级而非 type 级（SQLAlchemy Session.get 是 bound method）

    def _patched_db_get(model: Any, key: Any) -> Any:
        """Patched get：把 Subject 查询改成返 user_2 拥有的「假」subject ——
        模拟 service 层只看存在性、不看 owner 的 fail-open 旧实现。
        """
        if model is SubjectModel and key == user_1_subject.id:
            # 返 user_2 拥有的伪造 subject（模拟 service 只看存在、不看 owner）
            fake = SubjectModel(
                id=user_1_subject.id,
                name=user_1_subject.name,
                grade_level=user_1_subject.grade_level,
                owner_user_id=mock_user_2.id,  # owner 改成 user_2 — 模拟「service 不看 owner」
            )
            # 不 add 到 session（fake 对象，不持久化）
            return fake
        return real_db_get(model, key) if real_db_get else None

    # 使用 monkeypatch.setattr 替换 db.get 方法
    monkeypatch.setattr(mock_db_session, "get", _patched_db_get)

    # ───── 执行上传 ─────
    client = _build_test_client(mock_db_session, mock_llm_provider)
    pdf_bytes = _build_minimal_pdf_bytes()

    response = client.post(
        "/api/v1/academic/textbooks/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        data={
            "name": "user_2 的恶意上传（被 fail-open 放行）",
            "subject_id": str(user_1_subject.id),
            "grade_level": "senior_high",
        },
        headers={"X-User-Id": str(mock_user_2.id)},
    )

    # ───── 断言：D-37 核心 — fail-open 下应返 201（数据泄漏 + 归属污染） ─────
    assert response.status_code == 201, (
        f"D-37 完全 fail-open 实现应返 201（暴露数据），"
        f"实际 {response.status_code}：{response.text}"
        f" — 这意味着 monkeypatch 没生效，或正确实现已挡住了 fail-open"
    )
    # 进一步验证：教材以 user_2 创建（owner=2）但挂在 user_1 subject 下 ——
    # 这是归属污染的实证（D-32 第 3 类核心问题）
    body = response.json()
    assert body["owner_user_id"] == mock_user_2.id, (
        f"完全 fail-open 下教材应以 user_2 创建，实际 owner={body.get('owner_user_id')}"
    )
