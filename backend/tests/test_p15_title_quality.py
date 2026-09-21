"""P1-5 Chapter.title 质量门槛测试（M1-B retro 第二轮审查 D-29 第 3 条子项）。

D-29 第 3 条：Chapter.title 质量门槛
- 模板化判定（第N章占位）
- extraction_source='equal_split_placeholder' 时必须触发人工审阅（§7.5）
- 不靠 reject 阻断（避免同 fail-open）

测试矩阵：
1. test_is_template_title_detects_chapter_n_pattern
   — 单元测试：判定「第N章」模板化标题
2. test_is_template_title_passes_real_titles
   — 单元测试：真实标题不被误判
3. test_p15_equal_split_placeholder_marks_review_pending
   — 集成测试：等分 fallback 退化为模板时，service 创建 KnowledgeReview 行

Python 3.8 兼容（dev box）：
- 模块顶部 patch typing.Annotated + enum.StrEnum
- 所有 app.* import 延迟到 fixture / test 函数体
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


from typing import Any

import pytest

# ─────────────────────── 1. 单元测试：is_template_title 判定 ───────────────────


def test_is_template_title_detects_chapter_n_pattern() -> None:
    """判定「第N章」模板化标题 → True。"""
    from app.pdf.extractor import is_template_title

    # 标准模式（命中）
    assert is_template_title("第一章")
    assert is_template_title("第二章")
    assert is_template_title("第三章")
    # 含空格（命中 — 正则允许 \s*）
    assert is_template_title("第 1 章")
    assert is_template_title("第 3 章")
    # 中文数字（命中 — 正则覆盖一到十百千）
    assert is_template_title("第十二章")
    # 占位 N（命中 — 正则覆盖 [一二三四五六七八九十百千0-9]+ 中的 0-9，字母 N 不在）
    # → 「第N章」实际不命中（字母 N 不在字符集）。改测试期望：
    assert not is_template_title("第N章"), (
        "占位 N（字母）不被判定为模板（regex 只匹配中文数字 + 0-9）"
    )
    # 纯数字（命中）
    assert is_template_title("第9章")


def test_is_template_title_passes_real_titles() -> None:
    """真实标题不被误判 → False。"""
    from app.pdf.extractor import is_template_title

    # 中文章节标题（不命中）
    assert not is_template_title("地球运动")
    assert not is_template_title("大气受热过程")
    assert not is_template_title("水循环")
    # 含「第N章」前缀的真实标题（不命中 — 因为 regex 要求 ^第...章$ 完全匹配）
    assert not is_template_title("第一章 地球运动")
    assert not is_template_title("第三章 大气受热过程")
    # 英文标题（不命中）
    assert not is_template_title("Chapter 1: Earth")
    assert not is_template_title("Atmosphere Heating")
    # 边界：空字符串 / None → True（防御性判定）
    assert is_template_title("") is True
    assert is_template_title(None) is True  # type: ignore[arg-type]


# ─────────────────────── 2. 集成测试：service 层 KnowledgeReview 标记 ─────────


@pytest.mark.skipif(
    sys.version_info < (3, 9),
    reason="B2 baseline: py3.9+ required for Mapped[list[Class]] (PEP 585) — "
    "本测试 stub service.upload_textbook_with_extraction，依赖 app.models，"
    "dev box (py3.8) 跑不动；CI (py3.11) 真跑",
)
def test_p15_equal_split_placeholder_marks_review_pending(
    mock_db_session: Any,
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """等分 fallback 退化为模板标题时，service 创建 KnowledgeReview(PENDING) 行。

    D-29 第 3 条 + §7.5：教师审阅状态标记。

    测试策略：
    - stub PDFExtractor.extract_chapter_structure_with_source：返 5 个「第N章」
      + extraction_source='equal_split_placeholder'
    - stub PDFExtractor.extract_pages：返非空文本（确保 source 不被改为
      'scanned_pdf_empty'）
    - 调 service.upload_textbook_with_extraction
    - 断言：5 个 Chapter 创建 + 5 个 KnowledgeReview 行（status=PENDING +
      notes 含「title 退化为模板」字样）
    """
    from app.models import (
        GradeLevel,
        KnowledgeReview,
        KnowledgeReviewStatus,
        Subject,
        User,
    )
    from app.pdf.extractor import ChapterStructure, ChapterStructureResult
    from app.services import textbook_upload as svc

    # ───── 准备数据：mock_user (owner=1) + subject ─────
    user = User(id=1, name="user-1", is_system_owned=False)
    mock_db_session.add(user)
    mock_db_session.commit()
    mock_db_session.refresh(user)

    subject = Subject(
        name="测试学科",
        grade_level=GradeLevel.SENIOR_HIGH,
        owner_user_id=user.id,
    )
    mock_db_session.add(subject)
    mock_db_session.commit()
    mock_db_session.refresh(subject)

    # ───── stub PDFExtractor ─────
    real_extractor_cls = svc.PDFExtractor

    def _fake_extract_chapter_structure_with_source(
        self: Any, file_path: str
    ) -> ChapterStructureResult:
        """stub：返 5 个「第N章」 + extraction_source='equal_split_placeholder'。"""
        chapters = [
            ChapterStructure(
                chapter_number=n,
                title=f"第{n}章",  # 模板化标题 — 触发 is_template_title True
                page_range=((n - 1) * 10 + 1, n * 10),
                sections=[],
            )
            for n in range(1, 6)
        ]
        return ChapterStructureResult(
            chapters=chapters,
            extraction_source="equal_split_placeholder",
        )

    def _fake_extract_pages(
        self: Any, file_path: str, page_range: tuple[int, int]
    ) -> list[Any]:
        """stub：返非空文本，确保 extraction_source 不被改为 'scanned_pdf_empty'。"""
        from app.pdf.extractor import PDFPage

        return [
            PDFPage(
                page_no=page_range[0],
                text=f"第{page_range[0]}页内容（mock）",
                tables=[],
                images=[],
                metadata={},
            )
        ]

    monkeypatch.setattr(
        real_extractor_cls,
        "extract_chapter_structure_with_source",
        _fake_extract_chapter_structure_with_source,
    )
    monkeypatch.setattr(
        real_extractor_cls, "extract_pages", _fake_extract_pages
    )

    # ───── 准备 PDF 文件（magic bytes 校验需要 %PDF- 前缀） ─────
    pdf_path = tmp_path / "mock.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock pdf for P1-5 test\n")

    # ───── 调 service ─────
    textbook, chapters = svc.upload_textbook_with_extraction(
        mock_db_session,
        file_path=str(pdf_path),
        name="P1-5 测试教材",
        subject_id=subject.id,
        grade_level="senior_high",
        owner_user_id=user.id,
    )

    # ───── 断言 1：5 个 Chapter 都创建，extraction_source=equal_split_placeholder ─────
    assert len(chapters) == 5, f"应创建 5 个 Chapter，实际 {len(chapters)}"
    for ch in chapters:
        assert ch.extraction_source == "equal_split_placeholder", (
            f"chapter {ch.chapter_number} extraction_source 应为 "
            f"'equal_split_placeholder'，实际 '{ch.extraction_source}'"
        )
        # title 必须是「第N章」模板
        assert ch.title in {f"第{n}章" for n in range(1, 6)}, (
            f"chapter {ch.chapter_number} title 期望「第N章」模板，实际 '{ch.title}'"
        )

    # ───── 断言 2：每个 Chapter 都关联了 KnowledgeReview(PENDING) 行 ─────
    # 用 db 直接查（service.add 后已 commit）
    reviews = (
        mock_db_session.query(KnowledgeReview)
        .filter(KnowledgeReview.chapter_id.in_([ch.id for ch in chapters]))
        .all()
    )
    assert len(reviews) == 5, (
        f"P1-5：每个 equal_split_placeholder 章节应有 1 个 KnowledgeReview(PENDING) 行，"
        f"实际 {len(reviews)} 行"
    )
    for review in reviews:
        assert review.status == KnowledgeReviewStatus.PENDING, (
            f"KnowledgeReview status 应为 PENDING，实际 '{review.status}'"
        )
        assert review.notes is not None and "title 退化为模板" in review.notes, (
            f"KnowledgeReview notes 应说明「title 退化为模板」触发原因，"
            f"实际 notes='{review.notes}'"
        )


@pytest.mark.skipif(
    sys.version_info < (3, 9),
    reason="B2 baseline: py3.9+ required for Mapped[list[Class]] (PEP 585) — "
    "本测试对照验证（detected 路径不创建 KnowledgeReview），依赖 app.models，"
    "dev box (py3.8) 跑不动；CI (py3.11) 真跑",
)
def test_p15_detected_source_does_not_create_review(
    mock_db_session: Any,
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """对照测试：extraction_source='detected'（非 fallback）时，不创建 KnowledgeReview。

    验证 P1-5 只在 equal_split_placeholder 时触发，不影响正常路径。
    """
    from app.models import (
        GradeLevel,
        KnowledgeReview,
        Subject,
        User,
    )
    from app.pdf.extractor import ChapterStructure, ChapterStructureResult
    from app.services import textbook_upload as svc

    user = User(id=1, name="user-1", is_system_owned=False)
    mock_db_session.add(user)
    mock_db_session.commit()
    mock_db_session.refresh(user)

    subject = Subject(
        name="测试学科",
        grade_level=GradeLevel.SENIOR_HIGH,
        owner_user_id=user.id,
    )
    mock_db_session.add(subject)
    mock_db_session.commit()
    mock_db_session.refresh(subject)

    # stub：返真实标题 + extraction_source='detected'
    def _fake_extract_chapter_structure_with_source(
        self: Any, file_path: str
    ) -> ChapterStructureResult:
        chapters = [
            ChapterStructure(
                chapter_number=1,
                title="地球运动",
                page_range=(1, 10),
                sections=[],
            ),
            ChapterStructure(
                chapter_number=2,
                title="大气受热过程",
                page_range=(11, 20),
                sections=[],
            ),
        ]
        return ChapterStructureResult(
            chapters=chapters,
            extraction_source="detected",
        )

    def _fake_extract_pages(
        self: Any, file_path: str, page_range: tuple[int, int]
    ) -> list[Any]:
        from app.pdf.extractor import PDFPage

        return [
            PDFPage(
                page_no=page_range[0],
                text="真实内容",
                tables=[],
                images=[],
                metadata={},
            )
        ]

    monkeypatch.setattr(
        svc.PDFExtractor,
        "extract_chapter_structure_with_source",
        _fake_extract_chapter_structure_with_source,
    )
    monkeypatch.setattr(svc.PDFExtractor, "extract_pages", _fake_extract_pages)

    pdf_path = tmp_path / "mock.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")

    textbook, chapters = svc.upload_textbook_with_extraction(
        mock_db_session,
        file_path=str(pdf_path),
        name="正常路径教材",
        subject_id=subject.id,
        grade_level="senior_high",
        owner_user_id=user.id,
    )

    # 正常路径：detected source → 不创建 KnowledgeReview
    assert len(chapters) == 2
    for ch in chapters:
        assert ch.extraction_source == "detected"

    reviews = (
        mock_db_session.query(KnowledgeReview)
        .filter(KnowledgeReview.chapter_id.in_([ch.id for ch in chapters]))
        .all()
    )
    assert len(reviews) == 0, (
        f"detected 路径不应创建 KnowledgeReview，实际 {len(reviews)} 行"
    )
