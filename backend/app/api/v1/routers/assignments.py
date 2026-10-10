"""Assignment API router（M2-A.1 · v0.5 §3.6 老师审阅流程第 1 步产物）。

端点：
- POST /api/v1/assignments              → 创建作业单（出题引擎跑 + 落库）
- GET  /api/v1/assignments/{id}         → 查作业单详情（含 items + 鉴权 owner）

设计要点：
- 鉴权：X-User-Id header（M1-B B.2 简化 auth；与 academic router 一致）
- 跨用户隔离：owner_user_id 必须 = current_user.id（防 cross-user 越权；
  越权返 404 而非 403，避免暴露存在性）
- 反马太：v0.5 §3.5 line 168 verbatim 判据由 question_generator 实现
  （100 题 D 档作业 C 抽 ∈ [15, 25]、B 抽 = 0）
- §7.5 硬约束：作业单 review_status = pending（S3 才有 review 流程）
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.schemas.assignments import (
    AssignmentCreate,
    AssignmentRead,
)
from app.db.session import get_db
from app.models import Chapter, User
from app.services.question_generator import (
    generate_assignment_for_chapter,
)

logger = logging.getLogger(__name__)

router = APIRouter()


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
    return AssignmentRead.model_validate(assignment)


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
    return AssignmentRead.model_validate(assignment)
