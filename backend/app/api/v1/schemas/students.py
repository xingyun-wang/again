"""Students API schemas（M2-S2 档位管理）。

端点：
- GET    /api/v1/students        → 本班学生列表
- GET    /api/v1/students/{id}   → 单学生详情
- PATCH  /api/v1/students/{id}   → 改学生档位（手动覆盖；写 audit 字段）
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# TierLiteral 复用 assignments schemas 的语义（v0.5 §3.2 4 档 D < C < B < A）
TierLiteral = str  # Literal["D","C","B","A"]  # 避开 Literal 旧版 type 注释兼容问题


class StudentRead(BaseModel):
    """学生读 schema（含 2 audit 字段；nullable 表示历史未追踪）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    class_id: int
    grade_level: str
    current_tier: str
    created_at: datetime
    updated_at: datetime
    tier_changed_by_user_id: int | None
    tier_changed_at: datetime | None


class StudentListResponse(BaseModel):
    """学生列表响应。"""

    model_config = ConfigDict(extra="forbid")

    students: list[StudentRead] = Field(default_factory=list)


class StudentTierUpdateRequest(BaseModel):
    """改学生档位请求 body。

    字段：
    - current_tier: 新档位（D/C/B/A；非合法值由 Pydantic 422 拦截）
    """

    model_config = ConfigDict(extra="forbid")

    current_tier: str = Field(..., min_length=1, max_length=1, pattern=r"^[DCBA]$")


class StudentTierUpdateResponse(BaseModel):
    """改学生档位响应（manual override service 返回）。"""

    model_config = ConfigDict(extra="forbid")

    old: str
    new: str
    student_id: int
    tier_changed_by_user_id: int
    tier_changed_at: datetime
