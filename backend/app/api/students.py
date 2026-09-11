"""Student API — W1-T4。

端点：
- POST /api/classes/{class_id}/students/bulk-import     CSV 批量导入
- GET  /api/classes/{class_id}/students                班级学生列表
- POST /api/students/{student_id}/change-password      单个改密
- POST /api/classes/{class_id}/students/reset-passwords  批量改密（默认密码）

MVP 妥协（王星云 2026-09-11 09:59 拍板）：
- initial_password 明文存储 + 明文返回
- W3+ 改 passlib + bcrypt
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Class, Student
from ..schemas import (
    BulkImportResponse,
    ChangePasswordRequest,
    ResetPasswordsRequest,
    StudentOut,
)
from ..services.csv_import import bulk_import_students


# 路由分组：4 个端点路径前缀不同（class-scoped vs student-scoped），
# 不强制统一 prefix；用 tags=["students"] 让 OpenUI 折叠。
router = APIRouter(tags=["students"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============ Bulk import ============

@router.post(
    "/api/classes/{class_id}/students/bulk-import",
    response_model=BulkImportResponse,
)
async def bulk_import_students_endpoint(
    class_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """通过 multipart 上传 CSV 批量导入学生。

    CSV 字段：name, student_no, [optional initial_password]
    行为：
        - 班级不存在 → 404
        - 单行失败 → failed 列表记录，不中断批量
        - 学号重复（UniqueConstraint）→ failed 记录
    响应：{"inserted": N, "failed": [{row, name, reason}, ...]}
    """
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"class_id={class_id} 不存在",
        )

    raw = await file.read()
    # 服务层签名：db + class_id + raw bytes → dict
    result = bulk_import_students(db, class_id=class_id, raw=raw)
    return BulkImportResponse(**result)


# ============ List students in class ============

@router.get(
    "/api/classes/{class_id}/students",
    response_model=List[StudentOut],
)
def list_class_students(class_id: int, db: Session = Depends(get_db)):
    """列出班级所有学生。班级不存在 → 404。

    注：StudentOut.initial_password 明文返回（MVP 妥协）。
    """
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"class_id={class_id} 不存在",
        )
    return (
        db.query(Student)
        .filter(Student.class_id == class_id)
        .order_by(Student.id)
        .all()
    )


# ============ Single password change ============

@router.post("/api/students/{student_id}/change-password")
def change_student_password(
    student_id: int,
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
):
    """单个学生改密。

    MVP：明文写入 initial_password（W3+ 改 hash）。
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"student_id={student_id} 不存在",
        )

    # TODO(W3+): 改用 passlib + bcrypt；这里仅做 MVP 明文写入
    student.initial_password = payload.new_password
    db.commit()
    db.refresh(student)
    return {
        "id": student.id,
        "name": student.name,
        "initial_password": student.initial_password,
    }


# ============ Batch password reset ============

@router.post("/api/classes/{class_id}/students/reset-passwords")
def reset_class_passwords(
    class_id: int,
    payload: ResetPasswordsRequest,
    db: Session = Depends(get_db),
):
    """批量改密：把班级所有学生 initial_password 重置为 default_password。

    MVP：明文（W3+ 改 hash）。班级不存在 → 404。
    """
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"class_id={class_id} 不存在",
        )

    students = (
        db.query(Student)
        .filter(Student.class_id == class_id)
        .order_by(Student.id)
        .all()
    )

    # TODO(W3+): 改用 passlib + bcrypt hash 存储
    for s in students:
        s.initial_password = payload.default_password
    db.commit()

    return {
        "class_id": class_id,
        "reset_count": len(students),
        "default_password": payload.default_password,
    }