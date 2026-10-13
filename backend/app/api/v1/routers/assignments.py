"""Assignment API router（M2-A.1 · v0.5 §3.6 老师审阅流程 + M2-S3 §7.5 闸门）。

端点：
- POST  /api/v1/assignments              → 创建作业单（出题引擎跑 + 落库）
- GET   /api/v1/assignments/{id}         → 查作业单详情（含 items + 鉴权 owner）
- PATCH /api/v1/assignments/{id}/review  → 老师审阅（M2-S3 §5.2）
- POST  /api/v1/assignments/{id}/export  → PDF stub 闸门（M2-S3 §5.3）

设计要点：
- 鉴权：X-User-Id header（M1-B B.2 简化 auth；与 academic router 一致）
- 跨用户隔离：owner_user_id 必须 = current_user.id（防 cross-user 越权；
  越权返 404 而非 403，避免暴露存在性）
- 反马太：v0.5 §3.5 line 168 verbatim 判据由 question_generator 实现
  （100 题 D 档作业 C 抽 ∈ [15, 25]、B 抽 = 0）
- §7.5 硬约束：作业单 review_status = pending → reviewed/modified；
  C4 export 闸门 = review_status != APPROVED → 403
- Q2 复用：TeacherReviewStatus mixin 从 academic 复用，不重定义；
  mapping 函数 local copy 在本文件（不抽到 app/api/deps.py — §十三禁
  动既有债；C4 词汇不一致 = 既有债，照搬不改）
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import _enforce_owner_or_404
from app.api.v1.schemas.academic import TeacherReviewStatus
from app.api.v1.schemas.assignments import (
    AssignmentCreate,
    AssignmentExportResponse,
    AssignmentItemRead,
    AssignmentRead,
    AssignmentReviewRequest,
    AssignmentReviewResponse,
    ReviewStatusLiteral,
)
from app.db.session import get_db
from app.models import (
    Chapter,
    KnowledgeReviewStatus,
    User,
)
from app.services.question_generator import (
    generate_assignment_for_chapter,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ────────────────── §7.5 enum 映射（local copy；与 academic 隔离） ────────────
#
# ORM KnowledgeReviewStatus 三态：pending / approved / modified
# API spec §7.5 三态：           pending / reviewed / modified
# 两者仅 APPROVED 命名不一致（"approved" vs "reviewed"）；语义一致。
# 映射：API "reviewed" ↔ ORM APPROVED；其余名字一致。
#
# §十三 严禁：
# - 不动 routers/academic.py 既有 _to_api_review_status / _to_orm_review_status
#   （既有债不属 S3 范围；照搬逻辑即满足"不修"原则）
# - 不抽到 app/api/deps.py（不在 S3 范围；保持 inline 模式）
# - C4 词汇不一致（DB `approved` vs API `reviewed`）照搬不改（既有债）


def _to_api_review_status(orm_status: KnowledgeReviewStatus) -> ReviewStatusLiteral:
    """ORM enum value → API schema 用的 string（local copy；routers/academic.py:193-211 对齐）。"""
    if orm_status == KnowledgeReviewStatus.APPROVED:
        return "reviewed"
    if orm_status == KnowledgeReviewStatus.PENDING:
        return "pending"
    return "modified"


def _to_orm_review_status(api_status: str) -> KnowledgeReviewStatus:
    """API schema string → ORM enum value（local copy；routers/academic.py:193-211 对齐）。"""
    if api_status == "reviewed":
        return KnowledgeReviewStatus.APPROVED
    return KnowledgeReviewStatus(api_status)


def get_current_user_id(
    x_user_id: Annotated[int | None, Header(alias="X-User-Id")] = None,
) -> int:
    """从 X-User-Id header 取 user_id（B.2 简化 auth）。

    Raises:
        HTTPException 401: 缺失或非正整数
    """
    if x_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id header 必填",
        )
    if not isinstance(x_user_id, int) or x_user_id < 1:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id 必须为正整数",
        )
    return x_user_id


@router.post(
    "/assignments",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    payload: AssignmentCreate,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> object:
    """创建作业单（出题引擎跑 + 落库）。

    Raises:
        HTTPException 401: 缺失 X-User-Id
        HTTPException 404: chapter 不存在 或 user 不存在
        HTTPException 422: 章节题库不足 / 字段非法
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"user {user_id} 不存在",
        )
    chapter = db.get(Chapter, payload.chapter_id)
    if chapter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"chapter {payload.chapter_id} 不存在",
        )
    # A1 fix: 跨用户 chapter 引用污染（v0.5 §3.6 第 1 步 + D-29 B 项）。
    # 存在性预言机防护：别人的 chapter 也返 404，不泄漏存在性。
    _enforce_owner_or_404(chapter, user_id)
    try:
        assignment = generate_assignment_for_chapter(
            db,
            owner=user,
            chapter=chapter,
            tier=payload.tier,
            total_count=payload.total_count,
            seed=payload.seed,
        )
    except ValueError as e:
        # 题库不足 / 字段非法
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    # M2-S3-frontend B4：手动构造（含 review 字段；仿 PATCH /review 模式，
    # brief §4.1）。原因：TeacherReviewStatus schema 无 from_attributes=True，
    # model_validate(assignment) 不会从 ORM 4 字段构造 review 子对象。
    return AssignmentRead(
        id=assignment.id,
        owner_user_id=assignment.owner_user_id,
        chapter_id=assignment.chapter_id,
        tier=assignment.tier,
        total_count=assignment.total_count,
        d_count=assignment.d_count,
        c_count=assignment.c_count,
        b_count=assignment.b_count,
        a_count=assignment.a_count,
        seed=assignment.seed,
        created_at=assignment.created_at,
        items=[AssignmentItemRead.model_validate(item) for item in assignment.items],
        review=TeacherReviewStatus(
            review_status=_to_api_review_status(assignment.review_status),
            reviewed_by=assignment.reviewed_by,
            reviewed_at=assignment.reviewed_at,
            review_notes=assignment.review_notes,
        ),
    )


@router.get("/assignments/{assignment_id}", response_model=AssignmentRead)
def get_assignment(
    assignment_id: int,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> object:
    """查作业单详情（含 items + 鉴权 owner）。

    Raises:
        HTTPException 401: 缺失 X-User-Id
        HTTPException 404: assignment 不存在 / 不属于当前 user
    """
    from app.models import Assignment

    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"assignment {assignment_id} 不存在",
        )
    if assignment.owner_user_id != user_id:
        # 防 cross-user 越权；不暴露存在性（404 而非 403）
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"assignment {assignment_id} 不存在",
        )
    # M2-S3-frontend B4：手动构造（含 review 字段；仿 PATCH /review 模式，
    # brief §4.1）。原因：TeacherReviewStatus schema 无 from_attributes=True，
    # model_validate(assignment) 不会从 ORM 4 字段构造 review 子对象。
    return AssignmentRead(
        id=assignment.id,
        owner_user_id=assignment.owner_user_id,
        chapter_id=assignment.chapter_id,
        tier=assignment.tier,
        total_count=assignment.total_count,
        d_count=assignment.d_count,
        c_count=assignment.c_count,
        b_count=assignment.b_count,
        a_count=assignment.a_count,
        seed=assignment.seed,
        created_at=assignment.created_at,
        items=[AssignmentItemRead.model_validate(item) for item in assignment.items],
        review=TeacherReviewStatus(
            review_status=_to_api_review_status(assignment.review_status),
            reviewed_by=assignment.reviewed_by,
            reviewed_at=assignment.reviewed_at,
            review_notes=assignment.review_notes,
        ),
    )


# ────────────────── 3. PATCH /assignments/{id}/review（M2-S3 §5.2） ────────────
#
# 模式：复用 review_lesson_plan（routers/academic.py:880-955）+ Assignment
# owner 直查模式（brief §4.2 差异：assignment.owner_user_id 直接查；不 JOIN
# chapter）。同既有 get_assignment (routers/assignments.py:111-130) 模式。
#
# §7.5 硬约束：review_status 只允许 pending → reviewed / modified（Literal
# 拒 pending）。DB `approved` vs API `reviewed` 词汇不一致债 = 既有债，照搬
# 不改（§十三 严禁）。
#
# 错误码：
# - 401：缺失 X-User-Id（get_current_user_id 扌）
# - 404：assignment 不存在 / 不属于当前 user（D-29 不暴露存在性）
# - 422：body.status = "pending"（Pydantic Literal 扌）或缺字段
# - 500：DB write failed


@router.patch(
    "/assignments/{assignment_id}/review",
    response_model=AssignmentReviewResponse,
    summary="作业单审阅标记（§7.5 流程硬约束：reviewed / modified）",
)
def review_assignment(
    assignment_id: int,
    body: AssignmentReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> AssignmentReviewResponse:
    """§7.5 流程：assignment 创建后 = pending；PATCH /review 标记 reviewed/modified。

    Brief §5.2：
    - reviewed → review_status = APPROVED
    - modified → review_status = MODIFIED
    - reviewed_by / reviewed_at 落当前 user + UTC
    - notes 落 review_notes
    """
    from app.models import Assignment

    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"assignment {assignment_id} 不存在",
        )
    # M1-B retro 工单 B（D-29 B 项）：跨用户访问返 404，不暴露存在性。
    # Assignment owner 直查（不同于 lesson-plan 的 JOIN chapter）— 同既有
    # get_assignment 模式（routers/assignments.py:111-130）。
    if assignment.owner_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"assignment {assignment_id} 不存在",
        )

    # §7.5 流程硬约束：status 必为 reviewed / modified（Literal 扌 pending）
    target = _to_orm_review_status(body.status)
    assignment.review_status = target
    assignment.reviewed_by = user_id
    assignment.reviewed_at = datetime.now(timezone.utc)  # noqa: UP017 (3.8 兼容)
    if body.notes is not None:
        assignment.review_notes = body.notes

    try:
        db.commit()
        db.refresh(assignment)
    except Exception as e:
        db.rollback()
        logger.exception(
            "assignment review DB write failed: assignment_id=%s", assignment_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"DB write failed: {e}",
        ) from e

    return AssignmentReviewResponse(
        id=assignment.id,
        review=TeacherReviewStatus(
            review_status=_to_api_review_status(assignment.review_status),
            reviewed_by=assignment.reviewed_by,
            reviewed_at=assignment.reviewed_at,
            review_notes=assignment.review_notes,
        ),
    )


# ────────────────── 4. POST /assignments/{id}/export（M2-S3 §5.3） ──────────────
#
# PDF stub 闸门（§7.5 硬约束：未审不得导出）。
# - 闸门判 review_status == APPROVED（DB 层 ORM enum；不判 API Literal）
# - != APPROVED → 403（含 pending + modified；同 DB 侧判断）
# - == APPROVED → 200 + stub response（不实际生成 PDF；S4 接真生成）
#
# 词汇不一致债（DB `approved` vs API `reviewed`）= 既有债，**不动**
# （§十三 严禁）。DB 侧直接判 ORM enum APPROVED 是唯一以「与既有
# routers/academic.py 一致」为理由的决策。
#
# 错误码：
# - 401：缺失 X-User-Id（get_current_user_id 扌）
# - 403：review_status != APPROVED（闸门）
# - 404：assignment 不存在 / 不属于当前 user
# - 500：DB / 其他意外失败


@router.post(
    "/assignments/{assignment_id}/export",
    response_model=AssignmentExportResponse,
    summary="作业单 PDF 导出闸门（S3 stub；S4 接真 PDF）",
)
def export_assignment(
    assignment_id: int,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> AssignmentExportResponse:
    """§7.5 闸门：review_status == APPROVED 才放行；S3 仅 stub。

    Brief §5.3：
    - 404：assignment 不存在 / 不属于当前 user（D-29 不暴露存在性）
    - 403：review_status != APPROVED（DB 侧判 ORM enum）
    - 200：返 stub response（不实际生成 PDF）
    """
    from app.models import Assignment

    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"assignment {assignment_id} 不存在",
        )
    # M1-B retro 工单 B（D-29 B 项）：跨用户访问返 404（owner 直查）。
    if assignment.owner_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"assignment {assignment_id} 不存在",
        )

    # §7.5 闸门：DB 侧判 ORM enum APPROVED（不用 API Literal；brief §7.5 拍板）
    if assignment.review_status != KnowledgeReviewStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"assignment {assignment_id} 未通过教师审阅（review_status="
                f"{assignment.review_status.value}），不能导出"
            ),
        )

    # 闸门通过 → 返 stub response（S3 不实际生成 PDF；S4 接真 PDF）
    return AssignmentExportResponse(
        assignment_id=assignment.id,
        export_id=f"stub-{assignment.id}",
        status="queued",
        note="S3 stub; S4 接真 PDF 生成",
    )
