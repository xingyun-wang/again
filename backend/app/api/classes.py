"""Class API — W1-T4。

端点：
- POST /api/classes            创建班级（teacher_id 必须存在，否则 404）
- GET  /api/classes            列出班级
- GET  /api/classes/{id}       班级详情

约束（CHARTER §3 + W1 范围）：
- 单师多班；MVP grade=2
- 不做 update / delete
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Class, Teacher
from ..schemas import ClassCreate, ClassOut

router = APIRouter(prefix="/api/classes", tags=["classes"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("", response_model=ClassOut, status_code=status.HTTP_201_CREATED)
def create_class(payload: ClassCreate, db: Session = Depends(get_db)):
    """创建班级。teacher_id 必须指向已存在老师，否则 404。"""
    teacher = db.query(Teacher).filter(Teacher.id == payload.teacher_id).first()
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"teacher_id={payload.teacher_id} 不存在",
        )

    cls = Class(
        name=payload.name,
        grade=payload.grade,
        teacher_id=payload.teacher_id,
    )
    db.add(cls)
    db.commit()
    db.refresh(cls)
    return cls


@router.get("", response_model=List[ClassOut])
def list_classes(db: Session = Depends(get_db)):
    """列出所有班级（按 id 升序）。"""
    return db.query(Class).order_by(Class.id).all()


@router.get("/{class_id}", response_model=ClassOut)
def get_class(class_id: int, db: Session = Depends(get_db)):
    """班级详情。不存在 → 404。"""
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"class_id={class_id} 不存在",
        )
    return cls