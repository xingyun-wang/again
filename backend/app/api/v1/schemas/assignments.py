"""作业单 Pydantic schemas（M2-A.1 · v0.5 §3.6 老师审阅流程 + §3.5 反马太）。

端点：
- POST /api/v1/assignments          → 创建作业单（出题引擎跑 + 落库）
- GET  /api/v1/assignments/{id}     → 查作业单详情（含 items）
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.academic import QuestionDifficulty

TierLiteral = Literal["D", "C", "B", "A"]


class AssignmentCreate(BaseModel):
    """创建作业单请求。"""

    model_config = ConfigDict(extra="forbid")

    chapter_id: int = Field(..., ge=1, description="目标章节 ID")
    tier: TierLiteral = Field(..., description="目标档位 D/C/B/A")
    total_count: int = Field(..., ge=1, le=200, description="作业总题数（1-200）")
    seed: int | None = Field(default=None, description="随机种子（可复现；None=系统时间）")


class AssignmentItemRead(BaseModel):
    """作业题行读。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    question_id: int
    position: int
    tier_origin: QuestionDifficulty


class AssignmentRead(BaseModel):
    """作业单读（含 items + 4 档分布审计字段）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    chapter_id: int
    tier: QuestionDifficulty
    total_count: int
    d_count: int
    c_count: int
    b_count: int
    a_count: int
    seed: int | None
    created_at: datetime
    items: list[AssignmentItemRead] = Field(default_factory=list)
