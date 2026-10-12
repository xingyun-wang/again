"""Students API router（M2-S2 档位管理）。

端点（per M2-S2 brief §四）：
- GET    /api/v1/students         本班学生列表（Subject.owner = current_user）
- GET    /api/v1/students/{id}    单学生详情
- PATCH  /api/v1/students/{id}    改 current_tier（manual override）

设计要点：
- 鉴权：X-User-Id header（同 assignments / academic router 模式）
- 跨用户隔离：复用 _enforce_owner_or_404（D-29 B 项 / D-37 fail-open 可证伪）
  - 列表端点：靠 Subject.owner_user_id 链式过滤（间接通过 .class_ .subject）
  - 详情 / 改档端点：调 service override_student_tier，内部已做链式校验
- 反马太：S2 brief 范围不含反马太逻辑（反马太是出题引擎职责 / S1-A 已实现）
- Q1 K/M/N 算法：延后 M3（per 2026-10-11 角色边界拍板）
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import _enforce_owner_or_404
from app.api.v1.schemas.students import (
    StudentListResponse,
    StudentRead,
    StudentTierUpdateRequest,
    StudentTierUpdateResponse,
)
from app.db.session import get_db
from app.models import Class, Student, Subject, Tier
from app.services.student_tier import override_student_tier

logger = logging.getLogger(__name__)

router = APIRouter()


def get_current_user_id(
    x_user_id: Annotated[int | None, Header(alias="X-User-Id")] = None,
) -> int:
    """从 X-User-Id header 取 user_id（同 assignments router 模式）。"""
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


# ────────────────────────── 1. GET /students ──────────────────────────


@router.get(
    "",
    response_model=StudentListResponse,
    summary="本班学生列表",
    tags=["students"],
)
def list_students(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> StudentListResponse:
    """老师本班学生列表（学生归属的 Class → Subject 属本老师）。

    链路：本老师所有 Subject → 这些 Subject 下的所有 Class → 这些 Class 下的所有 Student。
    """
    subjects: list[Subject] = (
        db.query(Subject).filter(Subject.owner_user_id == user_id).all()
    )
    if not subjects:
        return StudentListResponse(students=[])

    subject_ids = [s.id for s in subjects]
    classes: list[Class] = (
        db.query(Class).filter(Class.subject_id.in_(subject_ids)).all()
    )
    if not classes:
        return StudentListResponse(students=[])

    class_ids = [c.id for c in classes]
    students: list[Student] = (
        db.query(Student).filter(Student.class_id.in_(class_ids)).all()
    )

    return StudentListResponse(
        students=[
            StudentRead.model_validate(s) for s in students
        ]
    )


# ────────────────────────── 2. GET /students/{id} ──────────────────────


@router.get(
    "/{student_id}",
    response_model=StudentRead,
    summary="单学生详情",
    tags=["students"],
)
def get_student(
    student_id: int,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> StudentRead:
    """单学生详情（链式校验：Student → Class → Subject → owner）。"""
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(
            status_code=404, detail=f"student {student_id} 不存在"
        )

    # 链式校验：Student.class_.subject.owner_user_id
    subject: Subject = student.class_.subject
    _enforce_owner_or_404(subject, user_id)

    return StudentRead.model_validate(student)


# ────────────────────────── 3. PATCH /students/{id} ────────────────────


@router.patch(
    "/{student_id}",
    response_model=StudentTierUpdateResponse,
    summary="改学生档位（手动覆盖 + 写 audit）",
    tags=["students"],
)
def patch_student_tier(
    student_id: int,
    body: StudentTierUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> StudentTierUpdateResponse:
    """手动覆盖学生档位 + 写 audit 字段（tier_changed_by_user_id / at）。

    业务规则：boundary 防御由 service 层负责（A 不升 / D 不降）= M3 算法落地的
    前置约束；MVP (S2) 仅手动覆盖 + audit 写。Q1 K/M/N 动态调整延后 M3。
    """
    try:
        new_tier = Tier(body.current_tier)
    except ValueError as e:
        # Pydantic pattern 已拦 422；这里兜底（service 也会再校验）
        raise HTTPException(
            status_code=422,
            detail=f"current_tier 必须是 D/C/B/A；got {body.current_tier}",
        ) from e

    result = override_student_tier(
        session=db,
        current_user_id=user_id,
        student_id=student_id,
        new_tier=new_tier,
    )

    return StudentTierUpdateResponse(
        old=result["old"].value if hasattr(result["old"], "value") else str(result["old"]),
        new=result["new"].value if hasattr(result["new"], "value") else str(result["new"]),
        student_id=result["student_id"],
        tier_changed_by_user_id=result["tier_changed_by_user_id"],
        tier_changed_at=result["tier_changed_at"],
    )
