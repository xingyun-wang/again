# M2-A.0 题库 CRUD 最小切片 工地 brief（决策室派工）

> **工单命名**：`M2-A.0`（v0.5 §10 M2 起步）
> **前置依赖**：review4 通过（fbb7275 + 27515d2）+ CI-1-1 跑通（M2-A 启动基础设施）
> **关联决策**：v0.5 §10.2 M2 / v0.5 §3 差异化作业 / D-29 owner_user_id / D-37 可证伪 / D-44 重定路径
> **工人 ID**：`m2-a0/question-crud`
> **工作目录**：当前 dev box `/home/wsq_1/tiered-homework-platform`
> **预算**：≤ 25 分钟
> **不入主会话**

---

## 1. 目标

完成 **M2-A.0 = Question 数据模型 + CRUD API + 测试**（v0.5 §10.2 M2 范围的第 1 步）。

**为什么只做最小切片**：
- M2 范围很大（题库 CRUD + 4 档差异化引擎 + 反马太 + PDF 导出）—— 一次性做完不可控
- M2-A.0 单独交付 = 题库 CRUD 第 1 步 = Question 模型 + 4 端点（POST / GET / PATCH / DELETE）
- M2-A.1 / M2-A.2 后续切片（差异化引擎 / 反马太 / PDF 导出）由后续工单负责

---

## 2. 必读上下文

1. `docs/产品定义-v0.5.md` §3.1-§3.4（差异化作业范围 + 题库来源 + 类型 + 输出）
2. `docs/产品定义-v0.5.md` §3.2（4 档位字母升序 D/C/B/A + 难度递增）
3. `docs/产品定义-v0.5.md` §3.6（老师审阅流程 4 步）
4. `docs/decisions.md` §D-29（owner_user_id 归属）+ §D-37（可证伪硬门槛）+ §D-44（M2 解封路径）
5. `docs/PROJECT-CHARTER.md` §1.4 + §3.3（题库 = 教师个人资产原则）
6. `docs/reviews/2026-09-21-fbb7275.md`（review3 baseline 跨用户 404 模式参考）
7. `docs/reviews/2026-09-21-27515d2.md`（review4 P1-1-1 fix narrow 模式参考）
8. `backend/app/models/academic.py`（已有 Subject / Textbook / Chapter / KnowledgeReview 模式）
9. `backend/app/api/v1/routers/academic.py`（已有端点模式）
10. `backend/app/api/v1/schemas/academic.py`（已有 Pydantic schema 模式）

---

## 3. v0.5 §3 范围锁定（防止越界）

**M2-A.0 范围内**：
- ✅ Question 数据模型（题库基础）
- ✅ Choice 数据模型（多选项题目）
- ✅ KnowledgePoint 多对多关联（题目 → 知识点，**沿用 M1 已有 KnowledgePoint**）
- ✅ 4 档位标签（D/C/B/A 字母升序=难度升序）
- ✅ 题型标签（choice / fill / subjective 三类）
- ✅ owner_user_id 字段（D-29 跨用户隔离）
- ✅ 4 端点：POST /api/v1/academic/questions + GET /api/v1/academic/questions/{id} + PATCH + DELETE
- ✅ 列表端点：GET /api/v1/academic/questions?chapter_id=&difficulty=&type=
- ✅ D-37 负面测试（跨用户 404）

**M2-A.0 范围外**：
- ❌ 4 档差异化引擎（M2-A.1 工单）
- ❌ 反马太逻辑（M2-A.1 工单）
- ❌ PDF 导出（M2-A.2 工单）
- ❌ 外部题库导入（菁优网 / 学科网 — M2-A.3 工单）
- ❌ AI 出题（v0.5 §3.3 永久禁用）
- ❌ 共建题库 is_public（M2-A.0 不启用，v0.5 §5.4 已 lock MVP 不启用）

---

## 4. 任务清单

### 4.1 数据模型（≤ 5 min）

文件 `backend/app/models/academic.py` 加：

```python
class QuestionDifficulty(str, Enum):
    """D-29 §3.2 4 档位（字母升序=难度升序）。"""
    D = "D"  # 基础
    C = "C"  # 进阶
    B = "B"  # 挑战
    A = "A"  # 扩展


class QuestionType(str, Enum):
    """v0.5 §3.4 题型标签。"""
    CHOICE = "choice"        # 单选 / 多选
    FILL = "fill"            # 填空
    SUBJECTIVE = "subjective"  # 主观题


class Question(Base):
    """题库基础模型（v0.5 §3 差异化作业）。
    
    归属：D-29 §1.4 题库属于教师个人资产 + owner_user_id 字段。
    4 档位：字母升序=难度升序（D-29 §3.2）。
    题型：v0.5 §3.4 按教师需要（不限制）。
    """
    __tablename__ = "questions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # 归属
    owner_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
    )
    
    # 内容
    chapter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[QuestionDifficulty] = mapped_column(
        SQLEnum(QuestionDifficulty, name="question_difficulty_enum"),
        nullable=False,
    )
    type: Mapped[QuestionType] = mapped_column(
        SQLEnum(QuestionType, name="question_type_enum"),
        nullable=False,
    )
    
    # 知识点多对多关联（沿用 M1 已有 KnowledgePoint）
    knowledge_points: Mapped[list["KnowledgePoint"]] = relationship(
        "KnowledgePoint",
        secondary="question_knowledge_points",  # 需要建关联表
        back_populates="questions",
        lazy="selectin",
    )
    
    # 选择项（仅 choice 类型有）
    choices: Mapped[list["Choice"]] = relationship(
        "Choice", back_populates="question", cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )
    
    # 关系
    chapter: Mapped["Chapter"] = relationship("Chapter", back_populates="questions")
    owner: Mapped["User"] = relationship("User", back_populates="questions")
    
    __table_args__ = (
        Index("ix_questions_owner_chapter_difficulty", "owner_user_id", "chapter_id", "difficulty"),
    )


class Choice(Base):
    """选择题选项（仅 choice 类型题目有）。"""
    __tablename__ = "choices"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False,
    )
    label: Mapped[str] = mapped_column(String(8), nullable=False)  # "A" / "B" / "C" / "D"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    question: Mapped["Question"] = relationship("Question", back_populates="choices")
    
    __table_args__ = (
        Index("ix_choices_question_order", "question_id", "order_index"),
    )


# 题目-知识点关联表（多对多）
question_knowledge_points = Table(
    "question_knowledge_points",
    Base.metadata,
    Column("question_id", Integer, ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True),
    Column("knowledge_point_id", Integer, ForeignKey("knowledge_points.id", ondelete="CASCADE"), primary_key=True),
)
```

**修改 Chapter 模型**：加 `questions` 反向关系

```python
class Chapter(Base):
    # ... 现有字段 ...
    questions: Mapped[list["Question"]] = relationship(
        "Question", back_populates="chapter", cascade="all, delete-orphan",
        lazy="selectin",
    )
```

**修改 User 模型**：加 `questions` 反向关系

```python
class User(Base):
    # ... 现有字段 ...
    questions: Mapped[list["Question"]] = relationship(
        "Question", back_populates="owner",
    )
```

**修改 KnowledgePoint 模型**：加 `questions` 反向关系（如已存在则不动）

```python
class KnowledgePoint(Base):
    # ... 现有字段 ...
    questions: Mapped[list["Question"]] = relationship(
        "Question", secondary="question_knowledge_points", back_populates="knowledge_points",
    )
```

**修改 `models/__init__.py`**：导出 `Question / Choice / QuestionDifficulty / QuestionType`

### 4.2 alembic 迁移（≤ 5 min）

新建 `backend/alembic/versions/0008_questions.py`：

```python
"""alembic 迁移：建 questions + choices + question_knowledge_points 表。

触发：M2-A.0 题库 CRUD 最小切片
基础：0005_owner_user_id + 0007_drop_extraction_source_default + fbb7275 P0-N1/P1-5 + 27515d2 P1-1-1
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision: str = "0008_questions"
down_revision: str | None = "0006_owner_user_id"  # 接 0006 链

def upgrade() -> None:
    # 1. 创建 question_difficulty_enum + question_type_enum PG enum
    question_difficulty_enum = sa.Enum("D", "C", "B", "A", name="question_difficulty_enum")
    question_type_enum = sa.Enum("choice", "fill", "subjective", name="question_type_enum")
    question_difficulty_enum.create(op.get_bind(), checkfirst=True)
    question_type_enum.create(op.get_bind(), checkfirst=True)
    
    # 2. 建 questions 表
    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("difficulty", question_difficulty_enum, nullable=False),
        sa.Column("type", question_type_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_questions_owner_chapter_difficulty", "questions", ["owner_user_id", "chapter_id", "difficulty"])
    op.create_index("ix_questions_difficulty", "questions", ["difficulty"])
    op.create_index("ix_questions_type", "questions", ["type"])
    
    # 3. 建 choices 表
    op.create_table(
        "choices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(length=8), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_choices_question_order", "choices", ["question_id", "order_index"])
    
    # 4. 建 question_knowledge_points 关联表
    op.create_table(
        "question_knowledge_points",
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("knowledge_point_id", sa.Integer(), sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"), primary_key=True),
    )

def downgrade() -> None:
    op.drop_table("question_knowledge_points")
    op.drop_index("ix_choices_question_order", table_name="choices")
    op.drop_table("choices")
    op.drop_index("ix_questions_type", table_name="questions")
    op.drop_index("ix_questions_difficulty", table_name="questions")
    op.drop_index("ix_questions_owner_chapter_difficulty", table_name="questions")
    op.drop_table("questions")
    op.execute("DROP TYPE IF EXISTS question_type_enum")
    op.execute("DROP TYPE IF EXISTS question_difficulty_enum")
```

**`down_revision`** 注意：0007 已被 Step 1 段 1 rename 成 0005（0007_drop_extraction_source_default → 0005_drop_extraction_source_default）。所以本迁移接 `0006_owner_user_id`（之前 0005，被让位给改名后的 0005_drop_extraction_source_default）。

### 4.3 Pydantic schema（≤ 5 min）

文件 `backend/app/api/v1/schemas/academic.py` 加：

```python
class QuestionDifficulty(str, Enum):
    D = "D"
    C = "C"
    B = "B"
    A = "A"


class QuestionType(str, Enum):
    CHOICE = "choice"
    FILL = "fill"
    SUBJECTIVE = "subjective"


class ChoiceBase(BaseModel):
    label: str = Field(..., max_length=8)
    content: str = Field(..., min_length=1)
    is_correct: bool = False
    order_index: int = 0


class ChoiceRead(ChoiceBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class QuestionBase(BaseModel):
    chapter_id: int
    content: str = Field(..., min_length=1)
    difficulty: QuestionDifficulty
    type: QuestionType
    knowledge_point_ids: list[int] = []


class QuestionCreate(QuestionBase):
    choices: list[ChoiceBase] = []  # 仅 choice 类型用


class QuestionUpdate(BaseModel):
    content: str | None = None
    difficulty: QuestionDifficulty | None = None
    type: QuestionType | None = None
    knowledge_point_ids: list[int] | None = None
    choices: list[ChoiceBase] | None = None


class QuestionRead(QuestionBase):
    id: int
    owner_user_id: int
    choices: list[ChoiceRead] = []
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class QuestionListResponse(BaseModel):
    items: list[QuestionRead]
    total: int
```

### 4.4 Router 端点（≤ 8 min）

文件 `backend/app/api/v1/routers/academic.py` 加 4 端点（接 P0-N1 既有 _enforce_owner_or_404 模式）：

```python
@router.post("/questions", response_model=QuestionRead)
def create_question(
    body: QuestionCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id),
) -> Question:
    """POST /api/v1/academic/questions — 创建题目（D-29 §1.4 题库个人资产）。
    
    必填：chapter_id / content / difficulty / type
    可选：choices（仅 choice 类型）/ knowledge_point_ids
    """
    # 1. 校验 chapter 归属（D-32 第 3 类）
    chapter = db.get(Chapter, body.chapter_id)
    if chapter is None:
        raise HTTPException(404, f"chapter_id {body.chapter_id} 不存在")
    _enforce_owner_or_404(chapter, user_id)
    
    # 2. 校验 type=choice 必传 choices
    if body.type == QuestionType.CHOICE and not body.choices:
        raise HTTPException(400, "choice 类型题目必须传 choices")
    if body.type != QuestionType.CHOICE and body.choices:
        raise HTTPException(400, f"{body.type} 类型题目不能传 choices")
    
    # 3. 校验 knowledge_point_ids 归属
    if body.knowledge_point_ids:
        kps = db.query(KnowledgePoint).filter(
            KnowledgePoint.id.in_(body.knowledge_point_ids)
        ).all()
        for kp in kps:
            _enforce_owner_or_404(kp, user_id)
    
    # 4. 创建
    q = Question(
        owner_user_id=user_id,
        chapter_id=body.chapter_id,
        content=body.content,
        difficulty=body.difficulty,
        type=body.type,
    )
    for c in body.choices:
        q.choices.append(Choice(**c.model_dump()))
    if body.knowledge_point_ids:
        q.knowledge_points = kps
    db.add(q)
    db.flush()  # 拿 q.id（P1-1-1 fix narrow 模式）
    db.commit()
    db.refresh(q)
    return q


@router.get("/questions/{question_id}", response_model=QuestionRead)
def get_question(
    question_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id),
) -> Question:
    """GET /api/v1/academic/questions/{id} — 获取题目（D-29 §1.4 跨用户 404）。"""
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(404, f"question_id {question_id} 不存在")
    _enforce_owner_or_404(q, user_id)
    return q


@router.get("/questions", response_model=QuestionListResponse)
def list_questions(
    chapter_id: int | None = None,
    difficulty: QuestionDifficulty | None = None,
    type: QuestionType | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id),
) -> QuestionListResponse:
    """GET /api/v1/academic/questions — 列表题目（D-29 §1.4 仅看自己）。"""
    query = db.query(Question).filter(Question.owner_user_id == user_id)
    if chapter_id is not None:
        query = query.filter(Question.chapter_id == chapter_id)
    if difficulty is not None:
        query = query.filter(Question.difficulty == difficulty)
    if type is not None:
        query = query.filter(Question.type == type)
    total = query.count()
    items = query.order_by(Question.id.desc()).offset(offset).limit(limit).all()
    return QuestionListResponse(items=items, total=total)


@router.patch("/questions/{question_id}", response_model=QuestionRead)
def update_question(
    question_id: int,
    body: QuestionUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id),
) -> Question:
    """PATCH /api/v1/academic/questions/{id} — 更新题目（D-29 §1.4 仅自己可改）。"""
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(404, f"question_id {question_id} 不存在")
    _enforce_owner_or_404(q, user_id)
    
    if body.content is not None:
        q.content = body.content
    if body.difficulty is not None:
        q.difficulty = body.difficulty
    if body.type is not None:
        q.type = body.type
    if body.knowledge_point_ids is not None:
        kps = db.query(KnowledgePoint).filter(
            KnowledgePoint.id.in_(body.knowledge_point_ids)
        ).all()
        for kp in kps:
            _enforce_owner_or_404(kp, user_id)
        q.knowledge_points = kps
    if body.choices is not None:
        # 删除旧 choices（cascade 自动）
        q.choices.clear()
        db.flush()
        for c in body.choices:
            q.choices.append(Choice(**c.model_dump()))
    
    db.commit()
    db.refresh(q)
    return q


@router.delete("/questions/{question_id}", status_code=204)
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id),
) -> None:
    """DELETE /api/v1/academic/questions/{id} — 删除题目（D-29 §1.4 仅自己可删）。"""
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(404, f"question_id {question_id} 不存在")
    _enforce_owner_or_404(q, user_id)
    db.delete(q)
    db.commit()
```

### 4.5 D-37 负面测试（≤ 5 min）

新建 `backend/tests/test_question_crud.py`：

```python
"""Question CRUD 端点测试 + D-37 跨用户 404 负面测试。

覆盖（M2-A.0）：
1. POST 创建题目（choice / fill / subjective 三类）
2. GET / PATCH / DELETE 单个题目
3. GET 列表（按 chapter_id / difficulty / type 过滤）
4. D-37 负面测试：user_2 访问 user_1 的题目 → 404（fail-open 实现下 → 200 数据泄漏）

D-32 第 3 类 安全/归属边界：D-35 锁定不可豁免
D-29 §1.4 题库属于教师个人资产
"""
from __future__ import annotations
# 复用 review3 review4 既有 fixture 模式
from tests.test_cross_user_isolation import _build_test_client, _build_minimal_pdf_bytes  # noqa


# TODO: 按 fbb7275 worker 既有测试模式实施
# 关键 case：
# - test_create_choice_question_success
# - test_create_fill_question_no_choices
# - test_create_with_cross_user_chapter_returns_404（D-37 负面测试）
# - test_get_cross_user_question_returns_404
# - test_patch_cross_user_question_returns_404
# - test_delete_cross_user_question_returns_404
# - test_list_only_own_questions
# - test_fail_open_owner_filter_would_leak_data_returns_200（D-37 fail-open 负面测试，复用 review2 worker fixture 模式）
```

### 4.6 dev box 4 闸门

```bash
cd /home/wsq_1/tiered-homework-platform/backend
ruff check app tests 2>&1 | tail -5 ; echo "RUFF=$?"
mypy app 2>&1 | tail -5 ; echo "MYPY=$?"
pytest tests/test_question_crud.py -q 2>&1 | tail -10 ; echo "PYTEST_NEW=$?"
pytest tests --collect-only -q 2>&1 | tail -5 ; echo "COLLECT=$?"
```

### 4.7 commit + push（CI-1-1 跑通后才推）

```bash
cd /home/wsq_1/tiered-homework-platform
git add backend/app/models/academic.py backend/app/models/__init__.py \
        backend/app/api/v1/routers/academic.py backend/app/api/v1/schemas/academic.py \
        backend/alembic/versions/0008_questions.py \
        backend/tests/test_question_crud.py
git commit -m "..."
# CI-1-1 跑通后才推 github master:main
# 否则 ci.yml 路径问题会让 CI 5 命令 run 不了，M2-A.0 修复也无法 CI 验证
```

---

## 5. 不要做

- ❌ 不要 push github（CI-1-1 必须先跑通，否则 M2-A.0 commit 进 main 后 CI 又会因 step 5 FAIL fail-fast）
- ❌ 不要 spawn 第三方 subagent
- ❌ 不要改 §4.1-§4.5 任务清单外文件
- ❌ 不要实施 M2-A.0 范围外功能（差异化引擎 / 反马太 / PDF 导出 / 外部题库 / 共建 / AI 出题）
- ❌ 不要把 chapter_id 改成 Path parameter（保持 query/JSON body 模式与 fbb7275 端点一致）
- ❌ 不要在 router 内直接创建 KnowledgePoint（仅做关联）

---

## 6. 与 CI-1-1 的串行关系

M2-A.0 commit 完成后**不立刻推**——等 CI-1-1 subagent 跑完 + CI run #6 5 命令实跑绿后，**决策室统一推** M2-A.0 + CI-1-1 两个 commit 到 GitHub。

避免顺序：
- 错误：M2-A.0 先推 → CI 5 命令 fail（ci.yml 路径问题）→ 看不到 M2-A.0 测试结果
- 正确：CI-1-1 先推 + CI 绿 → M2-A.0 推 → CI 5 命令全跑（包括 M2-A.0 新测试）

---

## 7. 回报

回报决策室（你的最后一条消息）：
- commit SHA（本地 master 上，**未推**）
- 4 闸门退出码
- git diff --stat
- D-37 负面测试数 + fail-open 验证
- 等决策室派 push 时机

如果 CI-1-1 先跑通 + 决策室推 + CI run #7 验证 M2-A.0 修复：
- 那是决策室的事，不是本工单的事
- 本工单交付 = commit + 4 闸门 + D-37 负面测试数

---

## 8. 失败处理

- 如果 4 闸门失败：停工 + 报回，决策室派 review5 subagent 诊断
- 如果 dev box 无 psycopg 导致 alembic upgrade head 失败：SKIP（CI runner 有 PG service，CI-1-1 跑通后 CI 真跑验证）
- 如果 D-37 负面测试 fail：检查 owner_user_id 是否完整传递，不通过不 commit
