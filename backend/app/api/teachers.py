"""Teacher API — W1-T4。

端点：
- POST /api/teachers          创建老师
- GET  /api/teachers          列出老师

约束（CHARTER §3 + W1 范围）：
- MVP 范围内：不做 update / delete（外派任务越界禁止）
- 老师无 unique 约束：同名老师允许（W1 范围）
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Teacher
from ..schemas import TeacherCreate, TeacherOut

router = APIRouter(prefix="/api/teachers", tags=["teachers"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("", response_model=TeacherOut, status_code=status.HTTP_201_CREATED)
def create_teacher(payload: TeacherCreate, db: Session = Depends(get_db)):
    """创建老师。MVP：无 unique 约束，同名允许。"""
    teacher = Teacher(name=payload.name)
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


@router.get("", response_model=List[TeacherOut])
def list_teachers(db: Session = Depends(get_db)):
    """列出所有老师（按 id 升序）。"""
    return db.query(Teacher).order_by(Teacher.id).all()