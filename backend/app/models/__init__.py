"""ORM 模型统一出口。

M1-A 阶段 1 引入学情 + 学科知识库数据模型。所有 model 类在此 re-export，
方便 alembic env.py 通过 `Base.metadata` 自动发现（无需显式 import）。
业务层用 `from app.models import Subject` 等显式导入即可。
"""

from __future__ import annotations

from app.models.academic import (
    Chapter,
    Choice,
    Class,
    Difficulty,
    GradeLevel,
    KeyPoint,
    KnowledgePoint,
    KnowledgeReview,
    KnowledgeReviewStatus,
    LessonPlan,
    Question,
    QuestionDifficulty,
    QuestionType,
    Student,
    StudentKnowledgePoint,
    Subject,
    TeachingSuggestion,
    Textbook,
    Tier,
    User,
    question_knowledge_points,
)

__all__ = [
    # enums
    "GradeLevel",
    "Tier",
    "KnowledgeReviewStatus",
    # M2-A.0：题库 4 档位 + 题型
    "QuestionDifficulty",
    "QuestionType",
    # M1-B retro 工单 B（D-29 B 项）：归属
    "User",
    # academic (§4.1 + §4.2)
    "Subject",
    "Class",
    "Student",
    "StudentKnowledgePoint",
    "Textbook",
    "Chapter",
    "KnowledgePoint",
    "KeyPoint",
    "Difficulty",
    "TeachingSuggestion",
    "KnowledgeReview",
    # M1-B B.2 §7.5 lesson-plan
    "LessonPlan",
    # M2-A.0：题库基础模型 + 选项 + 关联表
    "Question",
    "Choice",
    "question_knowledge_points",
]