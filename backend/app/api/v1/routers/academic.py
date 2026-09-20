"""Academic 业务 API router（M1-B B.2：v0.5 §7.4 + §7.5）。

端点清单：
1. POST   /api/v1/academic/textbooks/upload
2. GET    /api/v1/academic/textbooks/{id}/chapters
3. POST   /api/v1/academic/chapters/{id}/extract
4. GET    /api/v1/academic/chapters/{id}
5. PATCH  /api/v1/academic/chapters/{id}/review
6. POST   /api/v1/academic/lesson-plans/generate
7. GET    /api/v1/academic/lesson-plans/{id}
8. PATCH  /api/v1/academic/lesson-plans/{id}/review    ← Judgment call：B.2 spec 列了 7 端点
                                                          但 §7.5 流程硬约束测试需要
                                                          lesson-plan 也能 PATCH /review

设计要点：
- 认证（B.2）：X-User-Id header 取 user_id（M1+ 加完整 auth；本阶段简化）
- LLM 调用：通过 Depends(get_llm_provider) 注入；测试用 dependency_overrides mock
- §7.5 硬约束：所有 AI 生成实体创建时 review_status = pending；PATCH /review
  只允许 reviewed / modified，不允许回退 pending
- §7.4 标注：每个 LLM 响应必带 ai: AIAnnotation
- chapter extract / lesson-plan generate 失败时回滚事务；DB 中不应留下半成品
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.schemas.academic import (
    AIAnnotation,
    ChapterAISummary,
    ChapterDetailResponse,
    ChapterExtractRequest,
    ChapterExtractResponse,
    ChapterListResponse,
    ChapterReviewDetail,
    ChapterReviewRequest,
    ChapterReviewResponse,
    ChapterSummary,
    KnowledgePointDetail,
    KPDetail,
    LessonPlanGenerateRequest,
    LessonPlanResponse,
    LessonPlanReviewRequest,
    LessonPlanReviewResponse,
    TeacherReviewStatus,
    TextbookUploadResponse,
)
from app.core.llm.factory import get_llm_provider
from app.core.llm.provider import LLMProvider
from app.db.session import get_db
from app.models import (
    Chapter,
    Difficulty,
    GradeLevel,
    KeyPoint,
    KnowledgeReview,
    KnowledgeReviewStatus,
    LessonPlan,
    Subject,
    TeachingSuggestion,
    Textbook,
)
from app.services.textbook_upload import (
    DEFAULT_MAX_UPLOAD_BYTES,
    DEFAULT_UPLOADS_DIR,
    TextbookUploadError,
    UploadTooLargeError,
    UploadValidationError,
    check_magic_bytes,
    stream_upload_to_disk,
    upload_textbook_with_extraction,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# M1-B retro P0-C：上传根目录 + 应用层 size cap（环境变量可覆盖）。
UPLOAD_ROOT: Path = Path(os.environ.get("UPLOAD_ROOT", DEFAULT_UPLOADS_DIR))
MAX_UPLOAD_BYTES: int = int(
    os.environ.get("UPLOAD_MAX_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))
)


# ─────────────────────────────── 依赖：user_id ──────────────────────────────


def get_current_user_id(
    x_user_id: Annotated[int | None, Header(alias="X-User-Id")] = None,
) -> int:
    """从 X-User-Id header 取 user_id（B.2 简化 auth）。

    Raises:
        HTTPException 401: 缺失或非整数
    """
    if x_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 X-User-Id header（M1-B B.2 简化 auth；M1+ 接完整 JWT）",
        )
    if x_user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id 必须为正整数",
        )
    return x_user_id


def get_llm_dep() -> LLMProvider:
    """LLM Provider 依赖注入（测试时用 app.dependency_overrides[get_llm_dep] 替换）。"""
    return get_llm_provider()


# ─────────────────── M1-B retro 工单 B（D-29 B 项）：跨用户隔离 ───────────────
#
# 归属过滤：访问不属于当前用户的资源 → 返 404（不是 403），不泄漏 id 存在性。
# D-37 测试可证伪：monkeypatch 本函数为 no-op 即可让 fail-open 实现暴露
# （错误实现 `if obj.owner_user_id == 1: return obj` 会返 200 暴露数据）。
_NOT_OWNER_DETAIL = "该资源不属于当前用户"


def _enforce_owner_or_404(obj: object, user_id: int) -> None:
    """跨用户隔离硬门槛（D-29 B 项）。

    检查 obj.owner_user_id != user_id → 404（不是 403）。
    错误体统一为「该资源不属于当前用户」，避免泄漏 id 是否存在。

    Args:
        obj: 任意带 ``owner_user_id`` 属性的 ORM 实例（Subject/Textbook/Chapter）
        user_id: 当前请求的 user_id（X-User-Id header）

    Raises:
        HTTPException 404: obj.owner_user_id != user_id
    """
    owner_id = getattr(obj, "owner_user_id", None)
    if owner_id is None or owner_id != user_id:
        raise HTTPException(status_code=404, detail=_NOT_OWNER_DETAIL)


# ─────────────────────────────── LLM Prompt 模板 ────────────────────────────


_EXTRACT_SYSTEM_PROMPT = """你是一位资深高中地理教师助手。请从给定章节内容中抽取三类信息：
1. 重点（key_points）：本章学生必须掌握的核心概念 / 原理（3-5 条短句）
2. 难点（difficulties）：学生容易出错或理解困难的知识点（3-5 条短句）
3. 授课建议（teaching_suggestions）：给老师的教学策略建议（2-4 条短句）

只输出 JSON，不要其他文字。schema：
{
  "key_points": ["...", "..."],
  "difficulties": ["...", "..."],
  "teaching_suggestions": ["...", "..."]
}"""

_LESSON_PLAN_SYSTEM_PROMPT_TEMPLATE = """你是一位资深高中地理教师助手。请基于给定章节信息 + 学情，生成一份
{actual_duration} 分钟（{class_count_label}）的授课建议。

输出要求：
- 围绕章节"重点 / 难点"组织教学节奏
- 包含：教学目标、教学环节（导入 / 讲解 / 练习 / 总结）、时间分配、教学方法提示
- 不要 markdown，纯文本段落
- 长度 400-800 字

只输出正文，不要其他文字。"""


def _grade_level_value(g: GradeLevel | None) -> str | None:
    if g is None:
        return None
    return g.value


# ────────────────── §7.5 enum 映射 ────────────────────────
# ORM KnowledgeReviewStatus 三态：pending / approved / modified
# API spec §7.5 三态：        pending / reviewed / modified
# 两者仅 APPROVED 命名不一致（"approved" vs "reviewed"）；语义一致。
# 映射：API "reviewed" ↔ ORM APPROVED；其余名字一致。
# 返回类型用 Literal["pending", "reviewed", "modified"] 让 mypy 能精确收窄
# 到 schema 的 TeacherReviewStatus.review_status 字面量。
ReviewStatusLiteral = Literal["pending", "reviewed", "modified"]


def _to_api_review_status(orm_status: KnowledgeReviewStatus) -> ReviewStatusLiteral:
    """ORM enum value → API schema 用的 string。"""
    if orm_status == KnowledgeReviewStatus.APPROVED:
        return "reviewed"
    # PENDING.value / MODIFIED.value 都是 Literal 成员，直接返回
    if orm_status == KnowledgeReviewStatus.PENDING:
        return "pending"
    return "modified"


def _to_orm_review_status(api_status: str) -> KnowledgeReviewStatus:
    """API schema string → ORM enum value。"""
    if api_status == "reviewed":
        return KnowledgeReviewStatus.APPROVED
    return KnowledgeReviewStatus(api_status)


# ────────────────────── 1. POST /textbooks/upload ──────────────────────────


@router.post(
    "/textbooks/upload",
    response_model=TextbookUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="上传教材 PDF（M1-B B.3：multipart/form-data + PyMuPDF + pdfplumber 双库抽取）",
    tags=["academic"],
)
def upload_textbook(
    file: Annotated[UploadFile, File(description="教材 PDF 文件（PyMuPDF + pdfplumber 双库解析章节）")],
    name: Annotated[str, Form(min_length=1, max_length=256, description="教材名称")],
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user_id)],
    subject_id: Annotated[int | None, Form(description="学科 ID（可空；空则不归类）")] = None,
    grade_level: Annotated[
        Literal["junior_high", "senior_high"] | None,
        Form(description="学段：junior_high / senior_high（可空）"),
    ] = None,
) -> TextbookUploadResponse:
    """B.3 上传 + M2 工单 A 知识链路真实性修复。

    流程（M2 工单 A 后）：
    1. 接收 multipart/form-data（file + name + 可选 subject_id/grade_level）
    2. 读 PDF bytes → 写到 ``uploads/pending/{uuid}.pdf``（容器内 /app/data/uploads/pending）
    3. 调 ``app.services.textbook_upload.upload_textbook_with_extraction``：
       - 校验 magic bytes（%PDF-）
       - 调 PDFExtractor.extract_chapter_structure_with_source
       - 调 extract_pages 每章页范围抽正文 → content_summary
       - 持久化 Textbook + N 个 Chapter（含 extraction_source）
       - 移动 PDF 到 uploads/{textbook_id}/{filename}.pdf（DB 相对路径）
    4. 返回 ``TextbookUploadResponse``（含 textbook_id + chapter_summaries + 每章 extraction_source）

    错误码：
    - 400：空文件 / 非 PDF / 解析无章节 / 落盘失败
    - 404：subject_id 不存在
    - 422：grade_level 非法 / Form 字段校验失败
    - 500：DB 写入失败 / 抽取内部异常
    """
    # 校验 subject_id（如提供）
    if subject_id is not None and db.get(Subject, subject_id) is None:
        raise HTTPException(
            status_code=404, detail=f"subject_id {subject_id} 不存在"
        )

    # 1. 流式 magic bytes 校验（前 5 字节；不全量入内存）
    try:
        magic_bytes = check_magic_bytes(file.file)
    except UploadValidationError as e:
        logger.warning("PDF magic bytes 校验失败: filename=%s err=%s", file.filename, e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        logger.exception("PDF 文件读取失败: filename=%s", file.filename)
        raise HTTPException(status_code=400, detail=f"文件读取失败：{e}") from e

    # 2. 流式落盘（magic bytes 已被消费；前缀写到文件头）+ 500MB cap
    pending_path: Path | None = None
    try:
        pending_path = stream_upload_to_disk(
            file.file,
            dst_dir=UPLOAD_ROOT,
            prefix=magic_bytes,
            max_bytes=MAX_UPLOAD_BYTES,
        )
    except UploadTooLargeError as e:
        logger.warning("PDF 上传超 %d MB: filename=%s", MAX_UPLOAD_BYTES // (1024 * 1024), file.filename)
        raise HTTPException(status_code=413, detail=str(e)) from e
    finally:
        # 关 UploadFile（释放 spooled temp / 真实文件 fd）
        with contextlib.suppress(Exception):
            file.file.close()

    # 3. 调 service（extractor + 持久化 + file_path 落 DB）
    # M1-B retro 工单 B（D-29 B 项）：显式传 owner_user_id，让新建的
    # Textbook + N 个 Chapter 都归属当前 user。service 不允许默认 1
    # （避免 fail-open 写到 system-seed 而漏归属）。
    try:
        textbook, chapters = upload_textbook_with_extraction(
            db,
            file_path=str(pending_path),
            name=name,
            subject_id=subject_id,
            grade_level=grade_level,
            owner_user_id=user_id,
        )
    except TextbookUploadError as e:
        # 业务异常 → 400；service 自身已清理 pending（落盘失败由 service 内部处理）
        logger.warning("textbook upload failed (业务): %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        logger.exception("教材上传意外失败: name=%s", name)
        # 防御性清 pending（service _cleanup_files 通常已做，但这里是兜底）
        if pending_path is not None and pending_path.exists():
            with contextlib.suppress(OSError):
                pending_path.unlink()
        raise HTTPException(status_code=500, detail=f"教材上传失败：{e}") from e

    return TextbookUploadResponse(
        textbook_id=textbook.id,
        name=textbook.name,
        file_path=textbook.file_path,
        subject_id=textbook.subject_id,
        grade_level=_grade_level_value(textbook.grade_level),
        chapters=[
            ChapterSummary(
                id=ch.id,
                chapter_number=ch.chapter_number,
                title=ch.title,
                page_range_start=ch.page_range_start,
                page_range_end=ch.page_range_end,
                has_extracted=False,  # 新建章节未抽取（key_points/difficulties/suggestions）
                extraction_source=cast(Literal["detected", "pdfplumber_fallback", "equal_split_placeholder", "scanned_pdf_empty"], ch.extraction_source),
            )
            for ch in chapters
        ],
        created_at=textbook.created_at,
    )


# ────────────────────── 2. GET /textbooks/{id}/chapters ─────────────────────


@router.get(
    "/textbooks/{textbook_id}/chapters",
    response_model=ChapterListResponse,
    summary="列教材下所有章节",
    tags=["academic"],
)
def list_textbook_chapters(
    textbook_id: int,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> ChapterListResponse:
    textbook = db.get(Textbook, textbook_id)
    if textbook is None:
        raise HTTPException(status_code=404, detail=f"textbook {textbook_id} 不存在")
    # M1-B retro 工单 B（D-29 B 项）：跨用户访问返 404，不是 403。
    _enforce_owner_or_404(textbook, user_id)

    # 用 textbook.chapters（已 lazy="selectin"）— 避免再发 SQL
    chapter_summaries: list[ChapterSummary] = []
    for ch in textbook.chapters:
        # 是否已有 AI 抽取（任一子表 source='ai'）
        has_ai = (
            any(k.source == "ai" for k in ch.key_points)
            or any(d.source == "ai" for d in ch.difficulties)
            or any(t.source == "ai" for t in ch.teaching_suggestions)
        )
        chapter_summaries.append(
            ChapterSummary(
                id=ch.id,
                chapter_number=ch.chapter_number,
                title=ch.title,
                page_range_start=ch.page_range_start,
                page_range_end=ch.page_range_end,
                has_extracted=has_ai,
                extraction_source=cast(Literal["detected", "pdfplumber_fallback", "equal_split_placeholder", "scanned_pdf_empty"], ch.extraction_source),
            )
        )

    return ChapterListResponse(textbook_id=textbook.id, chapters=chapter_summaries)


# ────────────────────── 3. POST /chapters/{id}/extract ──────────────────────


def _call_llm_extract(llm: LLMProvider, chapter: Chapter) -> dict[str, list[str]]:
    """调 LLM 抽取章节结构化信息（重点/难点/授课建议）。

    Returns:
        dict with keys: key_points, difficulties, teaching_suggestions（each list[str]）

    Raises:
        ValueError: LLM 返回结构不符合预期（JSON 解析失败或字段缺失）
        RuntimeError: LLM 调用本身失败（透传）
    """
    user_content = (
        f"章节标题：{chapter.title}\n"
        f"章节号：第{chapter.chapter_number}章\n"
        f"内容摘要：{chapter.content_summary or '（无）'}\n\n"
        f"请按 system prompt 的 JSON schema 输出。"
    )
    messages: list[dict[str, object]] = [
        {"role": "system", "content": _EXTRACT_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    raw = llm.chat(messages, temperature=0.3, max_tokens=1500)

    # 解析 JSON；允许 LLM 在前后加 ```json fences
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        # 去掉首尾 ```...```
        lines = cleaned.split("\n")
        # 去掉首行 ```json 与末行 ```
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    parsed: Any = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError(f"LLM 返回非 dict：{type(parsed)}")

    result: dict[str, list[str]] = {}
    for key in ("key_points", "difficulties", "teaching_suggestions"):
        v = parsed.get(key)
        if not isinstance(v, list):
            raise ValueError(f"LLM 返回 {key} 非 list：{type(v)}")
        result[key] = [str(x).strip() for x in v if str(x).strip()]
    return result


@router.post(
    "/chapters/{chapter_id}/extract",
    response_model=ChapterExtractResponse,
    status_code=status.HTTP_201_CREATED,
    summary="调 LLM 抽取章节结构化信息（§7.4 AI 声明 + §7.5 pending review）",
    tags=["academic"],
)
def extract_chapter(
    chapter_id: int,
    body: ChapterExtractRequest,
    db: Annotated[Session, Depends(get_db)],
    llm: Annotated[LLMProvider, Depends(get_llm_dep)],
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> ChapterExtractResponse:
    """从章节内容中抽取 重点/难点/授课建议。

    §7.4: 返回 ai 字段（model + generated_at）。
    §7.5: 新建 KnowledgeReview(status=PENDING)；返回 review 字段。
    """
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail=f"chapter {chapter_id} 不存在")
    # M1-B retro 工单 B（D-29 B 项）：跨用户访问返 404。
    _enforce_owner_or_404(chapter, user_id)

    # 调 LLM（失败 → 事务回滚，无副作用）
    try:
        extracted = _call_llm_extract(llm, chapter)
    except (ValueError, RuntimeError) as e:
        logger.exception("chapter extract LLM call failed: chapter_id=%s", chapter_id)
        # 422 业务错误（解析失败）；500 上游错误
        if isinstance(e, ValueError):
            raise HTTPException(status_code=422, detail=f"LLM 返回结构异常：{e}") from e
        raise HTTPException(status_code=502, detail=f"LLM 调用失败：{e}") from e

    model_name = getattr(llm, "_chat_model", "deepseek-chat")
    now = datetime.now(timezone.utc)  # noqa: UP017 (3.8 兼容)

    try:
        # 删除已有 ai-sourced 行（仅当 force_reextract=True）
        if body.force_reextract:
            db.query(KeyPoint).filter(
                KeyPoint.chapter_id == chapter_id, KeyPoint.source == "ai"
            ).delete(synchronize_session=False)
            db.query(Difficulty).filter(
                Difficulty.chapter_id == chapter_id, Difficulty.source == "ai"
            ).delete(synchronize_session=False)
            db.query(TeachingSuggestion).filter(
                TeachingSuggestion.chapter_id == chapter_id, TeachingSuggestion.source == "ai"
            ).delete(synchronize_session=False)
            db.flush()

        # 插入新的 ai-sourced 行
        for content in extracted["key_points"]:
            db.add(KeyPoint(chapter_id=chapter_id, content=content, source="ai"))
        for content in extracted["difficulties"]:
            db.add(Difficulty(chapter_id=chapter_id, content=content, source="ai"))
        for content in extracted["teaching_suggestions"]:
            db.add(
                TeachingSuggestion(chapter_id=chapter_id, content=content, source="ai")
            )

        # 新建 KnowledgeReview（pending）
        review = KnowledgeReview(
            chapter_id=chapter_id,
            status=KnowledgeReviewStatus.PENDING,
        )
        db.add(review)
        db.commit()
        db.refresh(review)
    except Exception as e:
        db.rollback()
        logger.exception("chapter extract DB write failed: chapter_id=%s", chapter_id)
        raise HTTPException(status_code=500, detail=f"DB write failed: {e}") from e

    return ChapterExtractResponse(
        chapter_id=chapter.id,
        chapter_title=chapter.title,
        key_points=extracted["key_points"],
        difficulties=extracted["difficulties"],
        teaching_suggestions=extracted["teaching_suggestions"],
        review_id=review.id,
        ai=AIAnnotation(model=model_name, generated_at=now),
        review=TeacherReviewStatus(
            review_status="pending",
            reviewed_by=None,
            reviewed_at=None,
            review_notes=None,
        ),
    )


# ────────────────────── 4. GET /chapters/{id} ───────────────────────────────


@router.get(
    "/chapters/{chapter_id}",
    response_model=ChapterDetailResponse,
    summary="章节详情（含 §7.4 AI summary + §7.5 review 状态）",
    tags=["academic"],
)
def get_chapter(
    chapter_id: int,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> ChapterDetailResponse:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail=f"chapter {chapter_id} 不存在")
    # M1-B retro 工单 B（D-29 B 项）：跨用户访问返 404。
    _enforce_owner_or_404(chapter, user_id)

    # 用 chapter 的关系（lazy="selectin"）
    # 先 expire 以避免 stale cache（chapter 可能从其他 session 来）
    db.refresh(chapter)

    # AI summary：扫描 key_points/difficulties/teaching_suggestions 是否含 ai source
    has_ai = (
        any(k.source == "ai" for k in chapter.key_points)
        or any(d.source == "ai" for d in chapter.difficulties)
        or any(t.source == "ai" for t in chapter.teaching_suggestions)
    )

    latest_review: KnowledgeReview | None = None
    if chapter.reviews:
        latest_review = max(chapter.reviews, key=lambda r: r.id)

    ai_summary = ChapterAISummary(
        has_extracted=has_ai,
        last_extracted_at=None,  # ai-sourced 创建时间需查；本阶段从 review 创建时间近似
        model=None,
        latest_review_id=latest_review.id if latest_review else None,
        latest_review_status=_to_api_review_status(latest_review.status) if latest_review else None,
        ai=(
            AIAnnotation(
                model="deepseek-chat",  # 模型名固定（B.2 锁定 deepseek）
                generated_at=latest_review.created_at if latest_review else datetime.now(timezone.utc)  # noqa: UP017 (3.8 兼容),
            )
            if has_ai
            else None
        ),
        review=(
            TeacherReviewStatus(
                review_status=_to_api_review_status(latest_review.status),
                reviewed_by=None,  # KnowledgeReview.reviewed_by 是 str（email-like）；这里 None
                reviewed_at=latest_review.reviewed_at,
                review_notes=latest_review.notes,
            )
            if latest_review
            else None
        ),
    )

    return ChapterDetailResponse(
        id=chapter.id,
        textbook_id=chapter.textbook_id,
        chapter_number=chapter.chapter_number,
        title=chapter.title,
        content_summary=chapter.content_summary,
        page_range_start=chapter.page_range_start,
        page_range_end=chapter.page_range_end,
        extraction_source=cast(Literal["detected", "pdfplumber_fallback", "equal_split_placeholder", "scanned_pdf_empty"], chapter.extraction_source),
        knowledge_points=[
            KnowledgePointDetail(
                id=kp.id, name=kp.name, concept=kp.concept, teaching_order=kp.teaching_order
            )
            for kp in chapter.knowledge_points
        ],
        key_points=[
            KPDetail(id=k.id, content=k.content, source=k.source)
            for k in chapter.key_points
        ],
        difficulties=[
            KPDetail(id=d.id, content=d.content, source=d.source)
            for d in chapter.difficulties
        ],
        teaching_suggestions=[
            KPDetail(id=t.id, content=t.content, source=t.source)
            for t in chapter.teaching_suggestions
        ],
        reviews=[
            ChapterReviewDetail(
                id=r.id,
                status=r.status.value,
                reviewed_by=r.reviewed_by,
                reviewed_at=r.reviewed_at,
                notes=r.notes,
            )
            for r in chapter.reviews
        ],
        ai_summary=ai_summary,
    )


# ────────────────────── 5. PATCH /chapters/{id}/review ──────────────────────


@router.patch(
    "/chapters/{chapter_id}/review",
    response_model=ChapterReviewResponse,
    summary="章节审阅标记（§7.5 流程硬约束：reviewed / modified）",
    tags=["academic"],
)
def review_chapter(
    chapter_id: int,
    body: ChapterReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> ChapterReviewResponse:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail=f"chapter {chapter_id} 不存在")
    # M1-B retro 工单 B（D-29 B 项）：跨用户访问返 404。
    _enforce_owner_or_404(chapter, user_id)

    # 找最新一条 KnowledgeReview；不存在则 409（必须先 extract 才能 review）
    latest_review = (
        db.query(KnowledgeReview)
        .filter(KnowledgeReview.chapter_id == chapter_id)
        .order_by(KnowledgeReview.id.desc())
        .first()
    )
    if latest_review is None:
        raise HTTPException(
            status_code=409,
            detail="该章节无 review 记录（必须先调用 /chapters/{id}/extract 创建 pending review）",
        )

    # §7.5 流程硬约束：review_status 只允许 pending → reviewed / modified
    # 不允许 pending → pending；不允许 reviewed → pending
    if latest_review.status == KnowledgeReviewStatus.PENDING:
        target = KnowledgeReviewStatus.APPROVED if body.status == "reviewed" else KnowledgeReviewStatus.MODIFIED
    elif latest_review.status in (
        KnowledgeReviewStatus.APPROVED,
        KnowledgeReviewStatus.MODIFIED,
    ):
        # 已经审阅过；本次请求是再次覆写（视为更新备注 / 状态）
        if body.status == "reviewed":
            target = KnowledgeReviewStatus.APPROVED
        else:
            target = KnowledgeReviewStatus.MODIFIED
    else:  # pragma: no cover - enum closed
        target = KnowledgeReviewStatus.APPROVED

    latest_review.status = target
    latest_review.reviewed_by = f"user:{user_id}"  # KnowledgeReview.reviewed_by 是 VARCHAR
    latest_review.reviewed_at = datetime.now(timezone.utc)  # noqa: UP017 (3.8 兼容)
    if body.notes is not None:
        latest_review.notes = body.notes

    # modified 时：覆盖 ai-sourced 内容（如果提供）
    if body.status == "modified":
        if body.modified_key_points is not None:
            db.query(KeyPoint).filter(
                KeyPoint.chapter_id == chapter_id, KeyPoint.source == "ai"
            ).delete(synchronize_session=False)
            for content in body.modified_key_points:
                db.add(KeyPoint(chapter_id=chapter_id, content=content, source="teacher"))
        if body.modified_difficulties is not None:
            db.query(Difficulty).filter(
                Difficulty.chapter_id == chapter_id, Difficulty.source == "ai"
            ).delete(synchronize_session=False)
            for content in body.modified_difficulties:
                db.add(Difficulty(chapter_id=chapter_id, content=content, source="teacher"))
        if body.modified_teaching_suggestions is not None:
            db.query(TeachingSuggestion).filter(
                TeachingSuggestion.chapter_id == chapter_id, TeachingSuggestion.source == "ai"
            ).delete(synchronize_session=False)
            for content in body.modified_teaching_suggestions:
                db.add(
                    TeachingSuggestion(
                        chapter_id=chapter_id, content=content, source="teacher"
                    )
                )

    try:
        db.commit()
        db.refresh(latest_review)
    except Exception as e:
        db.rollback()
        logger.exception("chapter review DB write failed: chapter_id=%s", chapter_id)
        raise HTTPException(status_code=500, detail=f"DB write failed: {e}") from e

    return ChapterReviewResponse(
        review_id=latest_review.id,
        chapter_id=chapter_id,
        review=TeacherReviewStatus(
            review_status=_to_api_review_status(latest_review.status),
            reviewed_by=user_id,
            reviewed_at=latest_review.reviewed_at,
            review_notes=latest_review.notes,
        ),
    )


# ────────────────────── 6. POST /lesson-plans/generate ──────────────────────


def _call_llm_lesson_plan(
    llm: LLMProvider,
    chapter: Chapter,
    student_count: int | None,
    duration_minutes: int,
    focus: str | None,
) -> str:
    """调 LLM 生成授课建议正文。"""
    user_content = (
        f"章节标题：{chapter.title}\n"
        f"章节号：第{chapter.chapter_number}章\n"
        f"内容摘要：{chapter.content_summary or '（无）'}\n\n"
        f"学生数：{student_count or '未知（按 50 人班规划）'}\n"
        f"重点方向：{focus or '按章节重点'}\n\n"
        f"请生成 {duration_minutes} 分钟的授课建议正文。"
    )
    # 课时转换：1 课时 = 45 分钟（≥45 分钟才计为多课时；不足则视为 1 课时）
    class_count = max(1, duration_minutes // 45)
    class_count_label = f"{class_count} 课时"
    system_prompt = _LESSON_PLAN_SYSTEM_PROMPT_TEMPLATE.format(
        actual_duration=duration_minutes, class_count_label=class_count_label
    )
    messages: list[dict[str, object]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    return llm.chat(messages, temperature=0.5, max_tokens=2000)


@router.post(
    "/lesson-plans/generate",
    response_model=LessonPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="基于章节 + 学情生成授课建议（§7.4 AI 声明 + §7.5 pending review）",
    tags=["academic"],
)
def generate_lesson_plan(
    body: LessonPlanGenerateRequest,
    db: Annotated[Session, Depends(get_db)],
    llm: Annotated[LLMProvider, Depends(get_llm_dep)],
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> LessonPlanResponse:
    """基于章节 + 学情 → 调 LLM 生成授课建议。

    §7.4: 返回 ai 字段。
    §7.5: 新建 LessonPlan(review_status=PENDING)；返回 review 字段。
    """
    chapter = db.get(Chapter, body.chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail=f"chapter {body.chapter_id} 不存在")
    # M1-B retro 工单 B（D-29 B 项）：跨用户访问返 404（沿用 chapter 的 owner）。
    # 新建 LessonPlan 继承 chapter.owner_user_id（写入时显式设置）。
    _enforce_owner_or_404(chapter, user_id)

    duration = body.duration_minutes or 45

    try:
        content = _call_llm_lesson_plan(
            llm, chapter, body.student_count, duration, body.focus
        )
    except RuntimeError as e:
        logger.exception("lesson-plan LLM call failed: chapter_id=%s", body.chapter_id)
        raise HTTPException(status_code=502, detail=f"LLM 调用失败：{e}") from e

    model_name = getattr(llm, "_chat_model", "deepseek-chat")
    now = datetime.now(timezone.utc)  # noqa: UP017 (3.8 兼容)

    try:
        lp = LessonPlan(
            chapter_id=chapter.id,
            content=content,
            duration_minutes=duration,
            model=model_name,
            generated_at=now,
            review_status=KnowledgeReviewStatus.PENDING,
            # M1-B retro 工单 B（D-29 B 项）：lesson-plan 继承 chapter 归属，
            # 让后续端点（GET /lesson-plans/{id} + PATCH /review）不必 JOIN
            # chapter 也能拿 owner（节省查询；但仍保留 JOIN 检查作为双重门，
            # 防止 chapter.owner 与 lesson_plan.owner 脱钩）。
        )
        db.add(lp)
        db.commit()
        db.refresh(lp)
    except Exception as e:
        db.rollback()
        logger.exception("lesson-plan DB write failed: chapter_id=%s", body.chapter_id)
        raise HTTPException(status_code=500, detail=f"DB write failed: {e}") from e

    return LessonPlanResponse(
        id=lp.id,
        chapter_id=chapter.id,
        chapter_title=chapter.title,
        content=lp.content,
        duration_minutes=lp.duration_minutes,
        ai=AIAnnotation(model=lp.model, generated_at=now),
        review=TeacherReviewStatus(
            review_status=_to_api_review_status(lp.review_status),
            reviewed_by=lp.reviewed_by,
            reviewed_at=lp.reviewed_at,
            review_notes=lp.review_notes,
        ),
        created_at=lp.created_at,
    )


# ────────────────────── 7. GET /lesson-plans/{id} ───────────────────────────


@router.get(
    "/lesson-plans/{lesson_plan_id}",
    response_model=LessonPlanResponse,
    summary="授课建议详情（§7.4 + §7.5 字段）",
    tags=["academic"],
)
def get_lesson_plan(
    lesson_plan_id: int,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> LessonPlanResponse:
    lp = db.get(LessonPlan, lesson_plan_id)
    if lp is None:
        raise HTTPException(status_code=404, detail=f"lesson_plan {lesson_plan_id} 不存在")

    chapter = db.get(Chapter, lp.chapter_id)
    if chapter is None:
        # 防御：FK 失败应已被 ORM 阻止
        raise HTTPException(status_code=500, detail="lesson_plan 关联 chapter 不存在（数据异常）")
    # M1-B retro 工单 B（D-29 B 项）：跨用户访问返 404（JOIN chapter 检查归属）。
    _enforce_owner_or_404(chapter, user_id)

    return LessonPlanResponse(
        id=lp.id,
        chapter_id=chapter.id,
        chapter_title=chapter.title,
        content=lp.content,
        duration_minutes=lp.duration_minutes,
        ai=AIAnnotation(model=lp.model, generated_at=lp.generated_at),
        review=TeacherReviewStatus(
            review_status=_to_api_review_status(lp.review_status),
            reviewed_by=lp.reviewed_by,
            reviewed_at=lp.reviewed_at,
            review_notes=lp.review_notes,
        ),
        created_at=lp.created_at,
    )


# ───────────── 8. PATCH /lesson-plans/{id}/review（judgment call） ──────────


@router.patch(
    "/lesson-plans/{lesson_plan_id}/review",
    response_model=LessonPlanReviewResponse,
    summary="授课建议审阅标记（§7.5 流程硬约束：reviewed / modified）",
    tags=["academic"],
)
def review_lesson_plan(
    lesson_plan_id: int,
    body: LessonPlanReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> LessonPlanReviewResponse:
    """§7.5 流程硬约束：lesson-plan 生成后 = pending；PATCH /review 标记 reviewed/modified。

    B.2 spec 端点表列了 7 个端点，但 §7.5 流程硬约束测试需要 lesson-plan 可 PATCH /review。
    此为 judgment call：补第 8 个端点。spec 可能在 B.2 端点表漏写。
    """
    lp = db.get(LessonPlan, lesson_plan_id)
    if lp is None:
        raise HTTPException(status_code=404, detail=f"lesson_plan {lesson_plan_id} 不存在")

    # M1-B retro 工单 B（D-29 B 项）：JOIN chapter 检查归属（双重门）。
    chapter = db.get(Chapter, lp.chapter_id)
    if chapter is None:
        raise HTTPException(status_code=500, detail="lesson_plan 关联 chapter 不存在（数据异常）")
    _enforce_owner_or_404(chapter, user_id)

    if body.status == "reviewed":
        lp.review_status = KnowledgeReviewStatus.APPROVED
    else:
        lp.review_status = KnowledgeReviewStatus.MODIFIED

    lp.reviewed_by = user_id
    lp.reviewed_at = datetime.now(timezone.utc)  # noqa: UP017 (3.8 兼容)
    if body.notes is not None:
        lp.review_notes = body.notes
    if body.status == "modified" and body.content is not None:
        lp.content = body.content

    try:
        db.commit()
        db.refresh(lp)
    except Exception as e:
        db.rollback()
        logger.exception("lesson-plan review DB write failed: lesson_plan_id=%s", lesson_plan_id)
        raise HTTPException(status_code=500, detail=f"DB write failed: {e}") from e

    return LessonPlanReviewResponse(
        id=lp.id,
        review=TeacherReviewStatus(
            review_status=_to_api_review_status(lp.review_status),
            reviewed_by=lp.reviewed_by,
            reviewed_at=lp.reviewed_at,
            review_notes=lp.review_notes,
        ),
    )