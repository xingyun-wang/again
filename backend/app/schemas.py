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

from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field, model_validator

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


class QuestionUpdate(BaseModel):
    """更新题目请求体（PUT）。

    所有字段 optional：前端可局部更新（仅传变更字段）。
    question_type / level / chapter 不允许改动（题干是题目核心身份，W3+ 老师审阅时
    调整档位另起 endpoint /api/questions/{id}/level；MVP 简化）。
    """

    content: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    options: Optional[List[str]] = Field(default=None, min_length=2)
    answer: Optional[str] = Field(default=None, min_length=1, max_length=255)


class QuestionOut(BaseModel):
    """题目详情出参（read）。

    answer 反序列化（坑 #1）：
    - 单选 / 判断 → 保持 str
    - 多选 → 原 DB 存的是 JSON 字符串（如 '["A","C"]' 或 '["褶皱山","火山"]'），
      出参反序列化为 list[str]
    实现：Pydantic v2 model_validator(mode="before") 在构造前拦截 ORM 实例，
    根据 question_type 判断是否需要 json.loads，解析失败 fallback 为原字符串。
    """

    id: int
    content: str
    options: List[str]
    answer: Union[str, List[str]]
    question_type: QuestionType
    level: Level
    chapter: Chapter
    teacher_id: int

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def _deserialize_answer(cls, data: Any) -> Any:
        """在 Pydantic 构造实例前，把多选题的 answer 字符串反序列化为 list。

        接收 ORM 实例（from_attributes）或 dict。
        """
        if data is None:
            return data
        # ORM 实例 → 转 dict
        if not isinstance(data, dict):
            if hasattr(data, "__dict__"):
                # 拿 key 时优先用 SQLAlchemy 列映射；ORM 实例可直接 .answer
                try:
                    data = {
                        "id": data.id,
                        "content": data.content,
                        "options": data.options,
                        "answer": data.answer,
                        "question_type": data.question_type,
                        "level": data.level,
                        "chapter": data.chapter,
                        "teacher_id": data.teacher_id,
                    }
                except Exception:
                    return data
            else:
                return data

        qtype = data.get("question_type")
        # 归一化：str-mixin Enum 实例在 ORM 读路径下可能是裸 str（process_result_value 未实现）
        qtype_value = qtype.value if hasattr(qtype, "value") else qtype
        answer = data.get("answer")

        if qtype_value == "multiple_choice" and isinstance(answer, str):
            stripped = answer.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    import json
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        data["answer"] = parsed
                except Exception:
                    # 解析失败 → 保留原字符串（出参拿到 str，下游决定怎么处理）
                    pass
        return data


# ============ Homework（W3-T3 落地） ============


class HomeworkStatusEnum(str, PyEnum):
    """Pydantic 层的 HomeworkStatus 镜像枚举。

    - 与 app.models.HomeworkStatus 同值集合
    - 用 stdlib PyEnum（不是 sqlalchemy.types.Enum）— Pydantic v2 与 sqlalchemy
      Enum 混用在 from_attributes 时校验路径不一致，所以单独定义一份
    - str-mixin → Pydantic 自动把 ORM 返回的裸字符串（"draft" / "generated" /
      "reviewed" / "published"）转成枚举实例
    """

    DRAFT = "draft"
    GENERATED = "generated"
    REVIEWED = "reviewed"
    PUBLISHED = "published"


class HomeworkCreate(BaseModel):
    """创建作业请求体（W3-T3 MVP）。

    MVP 妥协：class_id / teacher_id 由客户端 body 传入（W5+ auth 阶段再收紧）。
    title 非空，长度 ≤ 200（与 DB 列对齐）。
    status 故意不暴露在 Create schema 里 — 新建作业默认 DRAFT（手动建）；
    引擎生成的状态变更走专用 endpoint（W3-T4 落地）。
    """

    class_id: int
    teacher_id: int
    title: str = Field(min_length=1, max_length=200)


class HomeworkQuestionOut(BaseModel):
    """作业-题目关联出参（read）。

    关联表的轻量视图：只暴露 question_id / level / position，
    不嵌 Question 详情 — Question 详情通过 /api/questions/{id} 单独取，避免 N+1。
    """

    id: int
    question_id: int
    level: Level          # 沿用现有 Level 枚举（D/C/B/A）
    position: int

    class Config:
        from_attributes = True


class HomeworkOut(BaseModel):
    """作业详情出参（read）。

    嵌 HomeworkQuestionOut 列表：前端拿到作业后直接拿到题目顺序 + 档位，
    再按需去 QuestionOut 拉题干详情（两步拉取，避免一次响应过大）。
    """

    id: int
    class_id: int
    teacher_id: int
    title: str
    status: HomeworkStatusEnum
    generated_at: Optional[datetime]
    reviewed_at: Optional[datetime]
    published_at: Optional[datetime]
    questions: list[HomeworkQuestionOut] = []   # 关联题目列表（按 position 升序）

    class Config:
        from_attributes = True