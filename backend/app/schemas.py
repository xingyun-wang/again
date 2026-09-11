"""Pydantic schemas — W1-T4 API 层 I/O 模型。

约定：
- 写请求用 Create / Request 后缀
- 读响应用 Out 后缀，from_attributes=True 直接接 ORM 实例
- 密码字段 min_length=6（与 MVP 学生密码策略对齐）

MVP 妥协（王星云 2026-09-11 09:59 拍板）：
- StudentOut.initial_password 直接返回明文
- W3+ auth 阶段统一改 passlib + bcrypt
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .models import Chapter, Level, QuestionType


# ============ Teacher ============

class TeacherCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class TeacherOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


# ============ Class ============

class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    grade: int = 2  # MVP 默认 2（高二）
    teacher_id: int


class ClassOut(BaseModel):
    id: int
    name: str
    grade: int
    teacher_id: int

    class Config:
        from_attributes = True


# ============ Student ============

class StudentOut(BaseModel):
    id: int
    name: str
    student_no: str
    class_id: int
    # MVP 妥协：明文返回（W3+ 改 hash）
    initial_password: str

    class Config:
        from_attributes = True


class ChangePasswordRequest(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)


class ResetPasswordsRequest(BaseModel):
    default_password: str = Field(min_length=6, max_length=128)


class BulkImportResponse(BaseModel):
    inserted: int
    failed: List[dict]  # [{"row": int, "name": str, "reason": str}]


# ============ Question（W3-T1 落地） ============


class QuestionCreate(BaseModel):
    """创建题目请求体。

    校验策略：
    - content: 必填非空，长度上限 2000（覆盖大题干 + 多选选项描述）
    - options: 至少 2 个；判断题固定 2 个（业务层校验见 W3-T2）
    - answer: 长度上限 255（多选用 JSON 字符串如 '["A","C"]'，也在 255 内）
    - question_type / level / chapter: Pydantic 自动用 Enum 值校验，非法值 422
    - teacher_id: 由路由层从 session 注入，不接受客户端 body 传入（见 W3-T2）
    """

    content: str = Field(min_length=1, max_length=2000)
    options: List[str] = Field(min_length=2)
    answer: str = Field(min_length=1, max_length=255)
    question_type: QuestionType
    level: Level
    chapter: Chapter
    teacher_id: int


class QuestionOut(BaseModel):
    """题目详情出参（read）。

    选项和答案原样返回（answer 是字符串，多选也以 JSON 字符串形式返回）。
    上层按 question_type 决定是否需要 JSON 反序列化。
    """

    id: int
    content: str
    options: List[str]
    answer: str
    question_type: QuestionType
    level: Level
    chapter: Chapter
    teacher_id: int

    class Config:
        from_attributes = True