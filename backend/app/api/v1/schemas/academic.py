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
from typing import Any, Literal

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


# extraction_source 字面量取值（与 alembic 0004 + extractor/ChapterStructureResult 对齐）
ExtractionSourceLiteral = Literal[
    "detected",
    "pdfplumber_fallback",
    "equal_split_placeholder",
    "scanned_pdf_empty",
]


class ChapterSummary(BaseModel):
    """教材下的章节摘要（用于 TextbookUploadResponse / ListChaptersResponse）。

    M2 工单 A：新增 ``extraction_source`` 字段，标记该章节的章节骨架 +
    content_summary 来源（snake_case）：
    - detected                — PyMuPDF/pdfplumber 主路径正常识别 + 抽到正文
    - pdfplumber_fallback     — PyMuPDF 失败，pdfplumber 接管
    - equal_split_placeholder — 主路径 + fallback 都识别不足，等分造章节（**真实造假，必须标记**）
    - scanned_pdf_empty       — 文本为空（扫描型 PDF，需 OCR，§6.4 TWAIN 实测 blocker）
    """

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
    extraction_source: ExtractionSourceLiteral = Field(
        ...,
        description="M2 工单 A：链路真源标记（详见 model.Chapter.extraction_source 注释）",
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


class TextbookSummary(BaseModel):
    """GET /textbooks 列表响应（M3-1a brief §1.2）。

    用途：教师查看自己上传的所有教材（题库属教师个人资产 — CHARTER §3）。
    字段：id / title / grade / subject（subject 可空，未归类教材也允许）。
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    title: str = Field(..., description="教材名（=Textbook.name）")
    grade: str | None = Field(
        default=None, description="学段（junior_high / senior_high）"
    )
    subject: str | None = Field(
        default=None, description="学科名（Subject.name；subject_id 为空时 None）"
    )


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

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    name: str
    concept: str
    teaching_order: int


class KnowledgePointCreate(BaseModel):
    """POST /chapters/{chapter_id}/knowledge-points 请求 body（M3-1a brief §1.3）。

    字段：
    - name: 知识点名（必填）
    - concept: 概念说明（可空）
    - teaching_order: 教学顺序（数字；不传 = None → 服务端自增 = 本章现有 max+1，
      首条为 0；见 routers/academic.py::create_knowledge_point）
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=256)
    concept: str | None = Field(default=None, max_length=4000)
    # P2-1（星轨复核 814a334）：default 0 → None，让端点区分「显式传 0」
    # 与「未传」两种语义；未传时服务端按本章现有 max + 1 自增。
    teaching_order: int | None = Field(default=None, ge=0)


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
    # M2 工单 A：链路真源标记（详见 ChapterSummary.extraction_source）
    extraction_source: ExtractionSourceLiteral
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


# ─────────────────────────── M2-A.0 题库 CRUD（v0.5 §3） ────────────────
#
# 范围锁定（brief §3）：
# - Question 数据模型 + 5 端点（POST / GET / GET list / PATCH / DELETE）
# - Choice 仅 choice 类型题目用
# - KnowledgePoint 多对多通过 knowledge_point_ids 传
# - 4 档位 D/C/B/A（字母升序=难度升序，v0.5 §3.2）
# - 题型 choice / fill / subjective（v0.5 §3.4）
#
# 范围外（brief §3 锁）：
# - 4 档差异化引擎（M2-A.1）
# - 反马太逻辑（M2-A.1）
# - PDF 导出（M2-A.2）
# - 外部题库导入（M2-A.3）
# - AI 出题（v0.5 §3.3 永久禁用）
# - 共建题库 is_public（M2-A.0 不启用）


from enum import Enum as _PyEnum  # noqa: E402  # 避让上面原生 Enum 别名


class QuestionDifficulty(str, _PyEnum):  # noqa: UP042
    """v0.5 §3.2 4 档位（字母升序 = 难度升序）。"""

    D = "D"
    C = "C"
    B = "B"
    A = "A"


class QuestionType(str, _PyEnum):  # noqa: UP042
    """v0.5 §3.4 题型标签。"""

    CHOICE = "choice"
    FILL = "fill"
    SUBJECTIVE = "subjective"


class ChoiceBase(BaseModel):
    """Choice 通用字段。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    label: str = Field(..., min_length=1, max_length=8)
    content: str = Field(..., min_length=1)
    is_correct: bool = False
    order_index: int = 0


class ChoiceRead(ChoiceBase):
    """Choice 响应：加 id。"""

    id: int


class QuestionBase(BaseModel):
    """Question 通用字段（POST / PATCH 共用基础）。

    chapter_id：题目所属章节。
    content：题目正文。
    difficulty：4 档位（v0.5 §3.2）。
    type：题型（v0.5 §3.4）。
    points：分值（M3-1a brief §1.1 — Numeric(5,1) 默认 2.0）。
    answer_text：答案正文（M3-1a brief §1.1 — Text nullable；choice 答案走 Choice.is_correct）。
    knowledge_point_ids：题目关联的知识点 id 列表（可空）。
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    chapter_id: int = Field(..., ge=1)
    content: str = Field(..., min_length=1)
    difficulty: QuestionDifficulty
    type: QuestionType
    points: float = Field(default=2.0, ge=0, le=999.9, description="分值（默认 2.0）")
    answer_text: str | None = Field(default=None, description="答案正文（fill / subjective 用）")
    knowledge_point_ids: list[int] = Field(default_factory=list)


class QuestionCreate(QuestionBase):
    """POST /questions 请求 body。

    choices：仅 choice 类型题目使用；fill / subjective 题目不传。
    """

    choices: list[ChoiceBase] = Field(default_factory=list)


class QuestionUpdate(BaseModel):
    """PATCH /questions/{id} 请求 body（所有字段可选）。

    PATCH 语义：仅修改传 in body 的字段；未传字段不动。
    choices 列表：若传则完全替换原 choices（删除原 + 添加新，cascade）。
    """

    model_config = ConfigDict(extra="forbid")

    content: str | None = Field(default=None, min_length=1)
    difficulty: QuestionDifficulty | None = None
    type: QuestionType | None = None
    points: float | None = Field(default=None, ge=0, le=999.9)
    answer_text: str | None = None
    knowledge_point_ids: list[int] | None = None
    choices: list[ChoiceBase] | None = None


class QuestionRead(QuestionBase):
    """GET /questions/{id} 响应（也用于 POST /questions 返回）。

    字段说明：
    - id: 题目 id
    - owner_user_id: 归属 user（D-29 §1.4 跨用户隔离）
    - choices: 该题目的所有选项（仅 choice 类型有）
    - created_at / updated_at: 时间戳
    """

    id: int
    owner_user_id: int
    choices: list[ChoiceRead] = Field(default_factory=list)
    # M3-1b brief §1 改动 3：两个只读展示字段（源 = Question 上的 property，
    # 关系均 lazy="selectin" ⇒ 无 N+1；from_attributes 自动取值）
    knowledge_point_names: list[str] = Field(
        default_factory=list, description="知识点名（表格标签列）"
    )
    image_count: int = Field(default=0, description="题目图片数（表格列）")
    created_at: datetime
    updated_at: datetime


class QuestionListResponse(BaseModel):
    """GET /questions 列表响应。"""

    model_config = ConfigDict(extra="forbid")

    items: list[QuestionRead]
    total: int = Field(..., ge=0)


# ─────────────────────────── M2-A.1 题目图片承载（v0.5 §3.4 / brief §3） ─────
#
# 范围锁定（brief §3 + §5）：
# - 题目图片承载 = 独立 ``question_images`` 表（1:N，与 choices 同构）
# - 2 Pydantic：QuestionImageUploadRequest（POST multipart 非文件字段）+ QuestionImageRead（POST/GET 响应）
# - 3 endpoint：POST /questions/{id}/images / GET /questions/{id}/images/{image_id} / DELETE
# - 限制：file_ext ∈ {png, jpg, jpeg, webp}（svg 不收 — brief §5.3）；单图 ≤ 5MB；
#         单题 ≤ 10 张图（brief §5.3；50→10 降一档降落地复杂度）
# - 鉴权：owner check 仿 get_assignment（brief §5.2 + routers/assignments.py:111-130）
#
# 范围外（brief §3 锁 + §6 锁）：
# - 实际 OSS 上传（M3）
# - 脱敏实际处理（M3）
# - 共建 is_public（M2-A.0 lock MVP）


# v0.5 §3.4 + brief §5.3：仅 png/jpg/jpeg/webp（svg 不收；M3 阶段再开）
QuestionImageFileExtLiteral = Literal["png", "jpg", "jpeg", "webp"]

# brief §3.1 QuestionImageSource enum：self_built | external_imported
QuestionImageSourceLiteral = Literal["self_built", "external_imported"]

# brief §3.1 DesensitizationStatus enum：pending | done | skipped
DesensitizationStatusLiteral = Literal["pending", "done", "skipped"]


class QuestionImageUploadRequest(BaseModel):
    """POST /questions/{id}/images 请求 body（multipart form 非文件字段契约）。

    实际文件走 ``UploadFile``（multipart/form-data 接收），本 schema 只承载
    非文件字段，作为 OpenAPI 契约 + 手动校验用。router 端用 ``Form(...)`` 逐
    字段接收（FastAPI 不支持 Pydantic model + UploadFile 混用）。

    字段说明（brief §5.1 + §5.3）：
    - file_ext: 文件扩展名；与上传文件实际内容一致；svg 不收
    - order_index: 排序（与 Choice.order_index 同款；≥ 0）
    - source: 来源（self_built / external_imported）
    - checksum: 可选 SHA256（用于客户端 / 服务端一致性校验；本阶段不强制）
    """

    model_config = ConfigDict(extra="forbid")

    file_ext: QuestionImageFileExtLiteral = Field(
        ...,
        description=(
            "文件扩展名（与上传文件实际内容一致；svg 不收 — 渲染/安全/排版 3 风险，brief §5.3）"
        ),
    )
    order_index: int = Field(
        default=0,
        ge=0,
        description="排序（与 Choice.order_index 同款；渲染时按 order_index 升序）",
    )
    source: QuestionImageSourceLiteral = Field(
        default="self_built",
        description="图片来源（brief §3.1 QuestionImageSource enum）",
    )
    checksum: str | None = Field(
        default=None,
        max_length=128,
        description=(
            "可选文件 SHA256（用于客户端 / 服务端一致性校验；本阶段不强制）"
        ),
    )


class QuestionImageRead(BaseModel):
    """GET /questions/{id}/images/{image_id} 响应（也用于 POST 返回）。

    11 列（model 12 列 - 路径已含的 question_id）：
    - id / order_index / file_ext / storage_path / source /
      desensitization_status / desensitized_at / uploaded_at /
      uploaded_by_user_id / oss_object_key / oss_uploaded_at
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    order_index: int
    file_ext: str
    storage_path: str
    source: QuestionImageSourceLiteral = Field(
        ...,
        description="图片来源（brief §3.1 QuestionImageSource enum 值）",
    )
    desensitization_status: DesensitizationStatusLiteral = Field(
        ...,
        description="脱敏状态（brief §3.1 DesensitizationStatus enum 值；S1/M2 阶段默认 pending）",
    )
    desensitized_at: datetime | None = Field(
        default=None,
        description="脱敏完成时间戳（M3 实际写入；S1/M2 = NULL）",
    )
    uploaded_at: datetime
    uploaded_by_user_id: int = Field(
        ...,
        description="上传者 user_id（与 QuestionImage row 的归属字段对齐；D-29 §1.4 跨用户隔离）",
    )
    oss_object_key: str | None = Field(
        default=None,
        description="OSS object key（M3 预留字段；S1/M2 = NULL）",
    )
    oss_uploaded_at: datetime | None = Field(
        default=None,
        description="OSS 上传完成时间（M3 预留字段；S1/M2 = NULL）",
    )


class QuestionImageSummary(BaseModel):
    """GET /questions/{id}/images 列表项（1c-1c 裁决，2026-10-20 14:48）。

    🔴 **刻意不复用 QuestionImageRead**：后者含 storage_path / oss_object_key /
    desensitization_status / uploaded_by_user_id 等内部字段，对外暴露会泄露
    存储布局与他人上传者身份。列表只出 4 个对外字段。

    - id / order_index / file_ext / uploaded_at
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    order_index: int
    file_ext: str
    uploaded_at: datetime

# ─────────────────── M3-1a-2 题组模型 + 块表（brief + 补遗定稿 2026-10-23） ───────────────────
#
# 范围（brief §1 1a-2-2 + 补遗 §乙）：
# - 题组 CRUD 6 端点 + 组侧图片 4 端点（补遗 §乙-1 的 4 个是 D4(a) 落地必需）
# - schema：题组建/读/详情 + 块读写 + 挂小题请求
#
# 关键定稿口径：
# - 乙-4：难度**只存组上**，小题 difficulty 是派生缓存（schema 层不额外暴露同步语义，
#   同步逻辑在 router 的 _sync_group_difficulty 一处，两个调用点）
# - 丙-1：block_type / owner_type 用 **String(16)** 不建 native enum；
#   取值白名单放 Pydantic Literal 层 + models 模块常量（应用层拒绝、DB 允许脏值）
# - 丙-3：挂小题的 group_order 与 group_id 组成唯一约束


# 丙-1：块类型白名单。**刻意不加 formula / audio** —— 那是"以后加"的情形，
# 不写进 Literal 才能体现"加块类型不改表"。真要用时再加 + 改 DB 无需迁移。
ContentBlockTypeLiteral = Literal["text", "image", "table"]

# 丙-1：块归属类型。'question' 预留（题干将来也能图文混排，1a-2 不做 UI/接口）
ContentBlockOwnerTypeLiteral = Literal["group", "question"]


class QuestionGroupCreate(BaseModel):
    """POST /question-groups 请求 body。

    字段：
    - chapter_id：题组所属章节（建组时校验归属当前 user，D-29 单门）
    - difficulty：题组难度（D2(a) 难度只存组上，小题继承）
    - knowledge_point_ids：题组挂的知识点（**可写**，落 group_knowledge_points 关联表）
    """

    model_config = ConfigDict(extra="forbid")

    chapter_id: int = Field(..., description="题组所属章节 id")
    difficulty: QuestionDifficulty = Field(
        ..., description="题组难度（D2(a)：难度只存组上，小题继承）"
    )
    knowledge_point_ids: list[int] = Field(
        default_factory=list,
        description="题组关联的知识点 id 列表（落 group_knowledge_points；归属校验同题）",
    )


class ContentBlockInput(BaseModel):
    """单个材料块（写入用）。

    - block_type：text / image / table（丙-1 白名单，DB 侧不校验）
    - text_content：text 块正文
    - image_id：image 块引用的 question_images.id（只引用不存文件）
    - table_json：table 块结构（{"header":true,"rows":[[...]]}）
    - meta：图片宽度等扩展位（乙-3：{"image_width":50|75|100} / {"col_widths":[...]}）
    """

    model_config = ConfigDict(extra="forbid")

    block_type: ContentBlockTypeLiteral = Field(..., description="块类型")
    text_content: str | None = Field(default=None, description="text 块正文")
    image_id: int | None = Field(default=None, description="image 块引用的图片 id")
    table_json: dict[str, Any] | None = Field(default=None, description="table 块结构")
    meta: dict[str, Any] | None = Field(
        default=None, description="扩展位（图片宽度 50/75/100 等）"
    )


class ContentBlockRead(BaseModel):
    """材料块读取（响应）。

    - id / block_type / order_index / text_content / image_id / table_json
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    block_type: str
    order_index: int
    text_content: str | None = None
    image_id: int | None = None
    table_json: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None


class QuestionGroupUpdate(BaseModel):
    """PUT /question-groups/{id} 请求 body。

    - difficulty：改组难度 ⇒ **同事务**批量同步组内小题（乙-4）
    - blocks：材料块序列**整体替换**（brief §1：材料是序列，替换比增量安全）
    - knowledge_point_ids：知识点关联**整体替换**（传则先清空原关联再按传序重建；
      **不传 = 不动**，传空列表 = 清空）
    """

    model_config = ConfigDict(extra="forbid")

    difficulty: QuestionDifficulty | None = Field(
        default=None, description="题组难度；改动会同步组内小题 difficulty（乙-4）"
    )
    blocks: list[ContentBlockInput] | None = Field(
        default=None,
        description="材料块序列（整体替换；传则先清空原块再按 order_index 重建）",
    )
    knowledge_point_ids: list[int] | None = Field(
        default=None,
        description="知识点关联（整体替换；传则先清空 group_knowledge_points 再重建；不传=不动）",
    )


class QuestionGroupRead(BaseModel):
    """GET /question-groups 列表项（也用于 POST 返回）。

    - id / owner_user_id / chapter_id / difficulty
    - small_question_count：小题数（D3(a) 题量按小题数累加 —— 这就是计数口径）
    - total_points：题组总分 = 小题 points 之和（材料不计分）
    - knowledge_point_ids：题组关联的知识点 id（**可写可读** —— 落
      group_knowledge_points 关联表；没有它，GET ?knowledge_point_id= 永远筛不出组）
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    owner_user_id: int
    chapter_id: int
    difficulty: QuestionDifficulty
    small_question_count: int = Field(default=0, description="小题数（D3(a) 计数口径）")
    total_points: float = Field(default=0.0, description="题组总分 = 小题之和")
    knowledge_point_ids: list[int] = Field(
        default_factory=list, description="题组关联的知识点 id 列表"
    )
    created_at: datetime
    updated_at: datetime


class QuestionGroupDetail(QuestionGroupRead):
    """GET /question-groups/{id} 详情。

    D1(a)：详情一次返回材料 + 全部小题。
    - blocks：材料块（按 order_index 升序）
    - questions：组内小题（按 group_order 升序）
    """

    blocks: list[ContentBlockRead] = Field(default_factory=list)
    questions: list[QuestionRead] = Field(default_factory=list)


class QuestionGroupQuestionCreate(BaseModel):
    """POST /question-groups/{id}/questions 请求 body（**组内新建小题**）。

    ⭐ **语义已改**（1c-2 commit2 · 2026-10-24 星轨 15:50 裁决 · brief §10.2 勘误）：
    1a-2 的「挂一道**已存在**的题」被废除 —— 小题与题库无关，
    「挂已有题」是误用入口（调一次，题库里一道题就变成组内小题、从题库消失）。
    ⇒ 现在是**在组内新建**一道小题：章节/难度**从组继承**，
      题序 `group_order` 由**后端 `max+1`** 分配，建题 + 挂组**同一事务**。

    - content：题干（min_length=1）
    - type：题型（choice 必传 choices；非 choice 不能传 choices）
    - points：分值（默认 2.0）
    - answer_text：答案正文（可空）
    - choices：选项（仅 choice 类型）
    - knowledge_point_ids：知识点（可空；必须属于**本题组章节**）

    ⚠️ **没有 `group_order`**：后端 `max+1` 分配（前端不传）。
    ⚠️ **没有 `chapter_id` / `difficulty`**：从题组继承
      （`extra="forbid"` ⇒ 前端传了直接 **422**）。
    """

    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., min_length=1, description="题干")
    type: QuestionType = Field(..., description="题型")
    points: float = Field(default=2.0, ge=0, le=999.9, description="分值（默认 2.0）")
    answer_text: str | None = Field(default=None, description="答案正文（fill / subjective 用）")
    choices: list[ChoiceBase] = Field(default_factory=list, description="选项（仅 choice 类型）")
    knowledge_point_ids: list[int] = Field(
        default_factory=list, description="知识点 id 列表（可空；须属本题组章节）"
    )
