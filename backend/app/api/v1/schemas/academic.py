"""业务 API schemas（M1-B B.2：v0.5 §7.4 AI 声明 + §7.5 教师审阅硬约束）。

约束来源：
- §7.4 AI 生成内容声明（UI 标签）
    每个 LLM 生成的响应都必带：ai_generated / model / generated_at /
    requires_teacher_review / annotation。
- §7.5 教师最终审阅流程（流程节点硬约束）
    AI 输出 = 建议，老师必须审阅：review_status 默认 pending；
    PATCH /review 标记 reviewed / modified 才能用于下次备课。

拆分原则：Request / Response 拆开，便于：
- 测试单测 request schema 校验（不需要跑 API）
- response schema 可组合 §7.4/§7.5 字段（mixin 思路）
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ───────────────────────────── §7.4 AI 声明字段 ──────────────────────────────


class AIAnnotation(BaseModel):
    """§7.4 AI 生成内容声明 — 每个 LLM 响应必带。

    字段说明（v0.5 §7.4）：
    - ai_generated: 必为 True（LLM 响应）
    - model: 哪个模型生成的（如 "deepseek-chat"）
    - generated_at: 生成时间
    - requires_teacher_review: 必为 True（§7.5 联动）
    - annotation: UI 显示的标签值（MVP 默认文案）
    """

    model_config = ConfigDict(extra="forbid")

    ai_generated: Literal[True] = True
    model: str = Field(..., min_length=1, max_length=128)
    generated_at: datetime
    requires_teacher_review: Literal[True] = True
    annotation: str = "本建议由 AI 生成，需教师审阅"


# ───────────────────────────── §7.5 教师审阅字段 ─────────────────────────────


class TeacherReviewStatus(BaseModel):
    """§7.5 教师审阅状态 — 每个 AI 生成的业务实体必带。

    字段说明（v0.5 §7.5）：
    - review_status: pending / reviewed / modified；新建 = pending
    - reviewed_by: 审阅者 user_id（B.2 从 X-User-Id 取）
    - reviewed_at: 审阅时间
    - review_notes: 审阅备注（可追溯；B.2 推荐字段）
    """

    model_config = ConfigDict(extra="forbid")

    review_status: Literal["pending", "reviewed", "modified"] = "pending"
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None


# ──────────────────────────────── 教材 / 章节 ─────────────────────────────────


class ChapterInput(BaseModel):
    """教材上传时附带的章节草稿（B.2 mock；B.3 由 extractor 从 PDF 解析）。"""

    model_config = ConfigDict(extra="forbid")

    chapter_number: int = Field(..., ge=1, le=999)
    title: str = Field(..., min_length=1, max_length=256)
    content_summary: str | None = None
    page_range_start: int | None = Field(default=None, ge=1)
    page_range_end: int | None = Field(default=None, ge=1)


class TextbookUploadRequest(BaseModel):
    """POST /textbooks/upload 请求 body。

    B.2 阶段：mock 上传（不接真 PDF；B.3 改为 PDF 文件 + multipart/form-data + extractor）。
    B.2 入参 = 教材元数据 + 章节草稿列表；handler 创建 Textbook + Chapter 行。
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=256)
    file_path: str = Field(..., min_length=1, max_length=1024)
    subject_id: int | None = None
    grade_level: Literal["junior_high", "senior_high"] | None = None
    chapters: list[ChapterInput] = Field(..., min_length=1)


class ChapterSummary(BaseModel):
    """教材下的章节摘要（用于 TextbookUploadResponse / ListChaptersResponse）。"""

    model_config = ConfigDict(extra="forbid")

    id: int
    chapter_number: int
    title: str
    page_range_start: int | None = None
    page_range_end: int | None = None
    has_extracted: bool = Field(
        default=False,
        description="是否存在 AI 抽取的内容（KeyPoint/Difficulty/TeachingSuggestion source='ai'）",
    )


class TextbookUploadResponse(BaseModel):
    """POST /textbooks/upload 响应。"""

    model_config = ConfigDict(extra="forbid")

    textbook_id: int
    name: str
    file_path: str
    subject_id: int | None = None
    grade_level: str | None = None
    chapters: list[ChapterSummary]
    created_at: datetime


class ChapterListResponse(BaseModel):
    """GET /textbooks/{id}/chapters 响应。"""

    model_config = ConfigDict(extra="forbid")

    textbook_id: int
    chapters: list[ChapterSummary]


# ──────────────────────────────── Chapter Extract ─────────────────────────────


class ChapterExtractRequest(BaseModel):
    """POST /chapters/{id}/extract 请求 body（B.2 阶段 chapter_id 走 URL path）。

    预留字段：model / temperature（M1+ 调参；MVP 默认 deepseek-chat + 系统默认温度）。
    """

    model_config = ConfigDict(extra="forbid")

    force_reextract: bool = Field(
        default=False,
        description="强制重新抽取（覆盖已有 ai-extracted 内容；B.2 默认 False = 已有则跳过）",
    )


class ChapterExtractResponse(BaseModel):
    """POST /chapters/{id}/extract 响应。

    §7.4: ai 字段必带。
    §7.5: review 字段必带（新建 review = pending）。
    """

    model_config = ConfigDict(extra="forbid")

    chapter_id: int
    chapter_title: str
    key_points: list[str] = Field(..., description="AI 抽取的'重点'（每条短句）")
    difficulties: list[str] = Field(..., description="AI 抽取的'难点'（每条短句）")
    teaching_suggestions: list[str] = Field(..., description="AI 抽取的'授课建议'（每条短句）")
    review_id: int = Field(..., description="新建的 KnowledgeReview 行 id（pending 状态）")
    ai: AIAnnotation
    review: TeacherReviewStatus


# ──────────────────────────────── Chapter Detail ──────────────────────────────


class KPDetail(BaseModel):
    """章节下的知识点子项通用 detail（KeyPoint / Difficulty / TeachingSuggestion 三表同构）。"""

    model_config = ConfigDict(extra="forbid")

    id: int
    content: str
    source: str | None = None


class KnowledgePointDetail(BaseModel):
    """知识点 detail（与 KPDetail 结构差异：name + concept，没有 source）。"""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    concept: str
    teaching_order: int


class ChapterReviewDetail(BaseModel):
    """章节级审阅记录 detail。"""

    model_config = ConfigDict(extra="forbid")

    id: int
    status: str
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    notes: str | None = None


class ChapterAISummary(BaseModel):
    """§7.4 章节级 AI 标注聚合（最近一次 extract 的状态）。"""

    model_config = ConfigDict(extra="forbid")

    has_extracted: bool
    last_extracted_at: datetime | None = None
    model: str | None = None
    latest_review_id: int | None = None
    latest_review_status: str | None = None
    ai: AIAnnotation | None = None  # has_extracted=True 时填充
    review: TeacherReviewStatus | None = None  # 最新一条 review 的状态


class ChapterDetailResponse(BaseModel):
    """GET /chapters/{id} 响应（章节全量 detail）。"""

    model_config = ConfigDict(extra="forbid")

    id: int
    textbook_id: int
    chapter_number: int
    title: str
    content_summary: str | None = None
    page_range_start: int | None = None
    page_range_end: int | None = None
    knowledge_points: list[KnowledgePointDetail] = Field(default_factory=list)
    key_points: list[KPDetail] = Field(default_factory=list)
    difficulties: list[KPDetail] = Field(default_factory=list)
    teaching_suggestions: list[KPDetail] = Field(default_factory=list)
    reviews: list[ChapterReviewDetail] = Field(default_factory=list)
    ai_summary: ChapterAISummary


# ──────────────────────────────── Chapter Review PATCH ────────────────────────


class ChapterReviewRequest(BaseModel):
    """PATCH /chapters/{id}/review 请求 body。

    §7.5 流程：status 必为 reviewed / modified（不允许直接跳 pending）。
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["reviewed", "modified"]
    notes: str | None = Field(default=None, max_length=4000)
    # modified 时可改（覆盖 AI 抽取的内容）。reviewed 时这些字段忽略。
    modified_key_points: list[str] | None = None
    modified_difficulties: list[str] | None = None
    modified_teaching_suggestions: list[str] | None = None


class ChapterReviewResponse(BaseModel):
    """PATCH /chapters/{id}/review 响应。"""

    model_config = ConfigDict(extra="forbid")

    review_id: int
    chapter_id: int
    review: TeacherReviewStatus


# ──────────────────────────────── Lesson Plan ─────────────────────────────────


class LessonPlanGenerateRequest(BaseModel):
    """POST /lesson-plans/generate 请求 body。

    学情输入（M1-B B.2 阶段简化）：
    - chapter_id 必填（基于哪个章节）
    - class_id / student_count 可选（M1+ 接入三维度画像）
    - duration_minutes 可选（默认 45 = 1 课时）
    - focus 可选（教师指定的重点方向，自由文本 hint）
    """

    model_config = ConfigDict(extra="forbid")

    chapter_id: int = Field(..., ge=1)
    class_id: int | None = None
    student_count: int | None = Field(default=None, ge=1, le=200)
    duration_minutes: int | None = Field(default=45, ge=10, le=240)
    focus: str | None = Field(default=None, max_length=1000)


class LessonPlanResponse(BaseModel):
    """Lesson-plan 通用响应（POST generate + GET /lesson-plans/{id} 共用）。

    §7.4: ai 字段必带。
    §7.5: review 字段必带（新建 = pending）。
    """

    model_config = ConfigDict(extra="forbid")

    id: int
    chapter_id: int
    chapter_title: str
    content: str = Field(..., description="LLM 生成的授课建议正文")
    duration_minutes: int
    ai: AIAnnotation
    review: TeacherReviewStatus
    created_at: datetime


class LessonPlanReviewRequest(BaseModel):
    """PATCH /lesson-plans/{id}/review 请求 body。

    §7.5 流程：status 必为 reviewed / modified。
    content 可选（modified 时可改）。
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["reviewed", "modified"]
    notes: str | None = Field(default=None, max_length=4000)
    content: str | None = Field(default=None, min_length=1)  # modified 时使用


class LessonPlanReviewResponse(BaseModel):
    """PATCH /lesson-plans/{id}/review 响应。"""

    model_config = ConfigDict(extra="forbid")

    id: int
    review: TeacherReviewStatus