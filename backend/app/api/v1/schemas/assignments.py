"""作业单 Pydantic schemas（M2-A.1 · v0.5 §3.6 老师审阅流程 + §3.5 反马太 + M2-S3 §7.5）。

端点：
- POST  /api/v1/assignments                  → 创建作业单（出题引擎跑 + 落库）
- GET   /api/v1/assignments/{id}             → 查作业单详情（含 items）
- PATCH /api/v1/assignments/{id}/review      → 老师审阅（M2-S3 §5.2）
- POST  /api/v1/assignments/{id}/export      → PDF stub 闸门（M2-S3 §5.3）

设计要点：
- §7.5 复用：TeacherReviewStatus mixin 从 academic 复用，**不重定义**
  （D-43-X §十三禁动 + brief Q2 拍板：零新 mixin / 零新 enum）。
- 词汇不一致债（DB `approved` vs API `reviewed`）= 既有债，**不动**（§十三禁）。
  本文件 ReviewStatusLiteral 与 API 出口用 `reviewed`；mapping 在
  routers/assignments.py 局部函数里做（不抽到 schemas）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.academic import TeacherReviewStatus
from app.models.academic import QuestionDifficulty

TierLiteral = Literal["D", "C", "B", "A"]

# API 出口 review_status 三态（与 §7.5 TeacherReviewStatus.review_status 同源）
# 单独 type alias 让 routers/assignments.py 的 mapping 收口能精准标注
ReviewStatusLiteral = Literal["pending", "reviewed", "modified"]


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


# ──────────────────── M2-S3 §7.5 老师审阅 + PDF 闸门 schemas ────────────────


class AssignmentReviewRequest(BaseModel):
    """PATCH /api/v1/assignments/{id}/review 请求 body。

    §7.5 流程：status 必为 reviewed / modified（Literal 拒 pending）。
    notes 可选（教师备注）。
    无 ``content`` 字段：Assignment 内容 = items（N 题），不是单字段；
    若需改题应在 S4 改 item 列表，本阶段不开。
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["reviewed", "modified"]
    notes: str | None = Field(default=None, max_length=4000)


class AssignmentReviewResponse(BaseModel):
    """PATCH /api/v1/assignments/{id}/review 响应。

    复用 TeacherReviewStatus mixin（academic.py:49-61，§7.5 字段 4 件套：
    review_status / reviewed_by / reviewed_at / review_notes），与 lesson-plan
    / chapter 端点保持字段一致（防 mixin 漂移）。
    """

    model_config = ConfigDict(extra="forbid")

    id: int
    review: TeacherReviewStatus


class AssignmentExportResponse(BaseModel):
    """POST /api/v1/assignments/{id}/export 响应（PDF stub）。

    M2-S3 范围：仅 stub（§7.5 闸门测试用），不实际生成 PDF；S4 接真 PDF
    生成后扩展此 response schema（filename / size / 下载 URL 等）。
    """

    model_config = ConfigDict(extra="forbid")

    assignment_id: int
    export_id: str
    status: Literal["queued", "processing", "done", "failed"]
    note: str
