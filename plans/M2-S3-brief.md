# M2-S3 brief — 作业生成 + 审阅（v0.5 §3.6 + §7.5 审阅硬约束 + 闸门）

> **承接决策**：决策书 §3 骨架「S3 = §3.6 四步流程 + §7.5 审阅硬约束 + 前端首块 UI」+ v0.5 §3.6 / §7.5
> **本 brief 范围**：S3-backend = Assignment 加 4 审阅字段 + alembic 0010 + PATCH /assignments/{id}/review + POST /assignments/{id}/export（PDF stub）+ 6 用例测试
> **不在范围**：PDF 实际生成（S4）/ 作业生成页 UI（S3-frontend 段，明日）/ K/M/N 动态调整算法（M3）/ 词汇不一致债（DB `approved` vs API `reviewed` = 既有债，留独立工单）
> **最后更新**：2026-10-13 08:45（载曜定稿；待星轨 review）
> **承载体**：本文件 `plans/M2-S3-brief.md`

---

## 一、范围

### 1.1 必交付

- Assignment 模型加 4 字段（`review_status` / `reviewed_by` / `reviewed_at` / `review_notes`）
- 1 个 migration：`0010_assignment_review_fields.py`（复用 `knowledge_review_status_enum`，不重建）
- schemas：`AssignmentReviewRequest` / `AssignmentReviewResponse` / `AssignmentExportResponse`
- 2 端点：`PATCH /api/v1/assignments/{id}/review` + `POST /api/v1/assignments/{id}/export`
- local mapping：`_to_api_review_status` + `_to_orm_review_status`（routers/assignments.py 内）
- 6 个 pytest 用例（5 反向 + 1 正向；容器 PG）

### 1.2 不在范围（延后 S4 / S3-frontend / M3）

- ❌ PDF 实际生成（S4 brief；S3 仅 stub）
- ❌ 作业生成页 / 审阅页 UI（S3-frontend 段）
- ❌ K/M/N 动态调整算法（M3；Assignment ↔ Student 绑定未建模）
- ❌ DB enum `approved` vs API Literal `reviewed` 词汇不一致（既有债；S3 复用既有 enum，不引入第三套）
- ❌ 跨表 audit log（D-37 family；S3 内嵌 reviewed_by/reviewed_at，不引入独立 audit 表）

---

## 二、产品定义硬约束（v0.5 §3.6 + §7.5）

```
差异化作业（功能 1）
- 4 档位：D / C / B / A（字母升序 = 难度升序）
- 反马太：D 档强制 20% 拔高（S1-A 已实现）

学情反馈 + 教师审阅（§3.6 第 3 步 + §7.5 硬约束）
- 老师最终审阅：AI 输出 = 建议，老师必须审阅；PATCH /review 标记 reviewed/modified
- 未审不得导出（§7.5 闸门）：review_status != reviewed 时 POST /export 必须 403
- 默认 review_status = pending（新建后）
```

---

## 三、Q1-Q5 拍板（2026-10-13 08:33 星云拍）

| Q | 拍板 |
|---|---|
| **Q1** 派工粒度 | 拆 2 段：S3-backend（今晚）+ S3-frontend（明日） |
| **Q2** 状态机设计 | **复用** `KnowledgeReviewStatus`（0002）三态 pending/reviewed/modified + `TeacherReviewStatus` mixin + PATCH /review 模式；零新词汇 / 零新 enum / 零新映射 |
| **Q3** PDF 闸门 | S3 stub：`POST /assignments/{id}/export`；判 `review_status != APPROVED`（DB）→ 403；是 → 200 + stub response |
| **Q4** 前端首块 UI | 作业生成页（留 S3-frontend 段，今晚不开；等 CI #85 绿）|
| **Q5** 反向用例 | 5 反向 + 1 正向 = 6 用例；防 D-28 家族恒真 / 恒假门槛 |

---

## 四、复用既有模式（核源 2026-10-13 08:30）

### 4.1 既有 PATCH /review 模式（`routers/academic.py:880-955`）

```python
@router.patch("/lesson-plans/{lesson_plan_id}/review")
def review_lesson_plan(
    lesson_plan_id: int,
    body: LessonPlanReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> LessonPlanReviewResponse:
    lp = db.get(LessonPlan, lesson_plan_id)
    if lp is None:
        raise HTTPException(404, detail=f"lesson_plan {lesson_plan_id} 不存在")

    # LessonPlan: JOIN chapter → _enforce_owner_or_404（M1-B B 项）
    chapter = db.get(Chapter, lp.chapter_id)
    if chapter is None:
        raise HTTPException(500, detail="lesson_plan 关联 chapter 不存在（数据异常）")
    _enforce_owner_or_404(chapter, user_id)

    if body.status == "reviewed":
        lp.review_status = KnowledgeReviewStatus.APPROVED  # C4 词汇不一致
    else:
        lp.review_status = KnowledgeReviewStatus.MODIFIED

    lp.reviewed_by = user_id
    lp.review_at = datetime.now(timezone.utc)
    if body.notes is not None:
        lp.review_notes = body.notes
    if body.status == "modified" and body.content is not None:
        lp.content = body.content

    db.commit()
    db.refresh(lp)

    return LessonPlanReviewResponse(
        id=lp.id,
        review=TeacherReviewStatus(
            review_status=_to_api_review_status(lp.review_status),
            reviewed_by=lp.reviewed_by,
            reviewed_at=lp.reviewed_at,
            review_notes=lp.review_notes,
        ),
    )
```

### 4.2 S3 差异：Assignment owner 路径不同

| 对象 | owner 路径 | S3 处理 |
|---|---|---|
| `LessonPlan` | JOIN chapter → chapter.owner_user_id | `_enforce_owner_or_404(chapter, user_id)`（JOIN） |
| `Assignment` | **直接** `owner_user_id` 字段 | `if assignment.owner_user_id != user_id: raise 404`（不 JOIN；同既有 `get_assignment` 模式） |

### 4.3 既有 mapping functions（`routers/academic.py:193-211`）

```python
ReviewStatusLiteral = Literal["pending", "reviewed", "modified"]

def _to_api_review_status(orm_status: KnowledgeReviewStatus) -> ReviewStatusLiteral:
    """ORM enum value → API schema 用的 string。"""
    if orm_status == KnowledgeReviewStatus.APPROVED:
        return "reviewed"
    if orm_status == KnowledgeReviewStatus.PENDING:
        return "pending"
    return "modified"

def _to_orm_review_status(api_status: str) -> KnowledgeReviewStatus:
    """API schema string → ORM enum value。"""
    if api_status == "reviewed":
        return KnowledgeReviewStatus.APPROVED
    return KnowledgeReviewStatus(api_status)
```

**S3 决策**：local copy in `routers/assignments.py`（与 `routers/academic.py` 隔离；不重构 `app/api/deps.py` 因为不在 S3 范围）。C4 词汇不一致 = 既有债，照搬不改。

### 4.4 既有 `TeacherReviewStatus` mixin（`schemas/academic.py:49-61`）

```python
class TeacherReviewStatus(BaseModel):
    """§7.5 教师审阅状态 — 每个 AI 生成的业务实体必带。"""
    model_config = ConfigDict(extra="forbid")
    review_status: Literal["pending", "reviewed", "modified"] = "pending"
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None
```

**S3 决策**：复用（从 `schemas/academic.py` import，不重定义；防止 mixin 漂移）。

### 4.5 既有 `LessonPlanReviewRequest`（`schemas/academic.py:337-348`）

```python
class LessonPlanReviewRequest(BaseModel):
    """§7.5 流程：status 必为 reviewed / modified（不允许跳 pending）。"""
    model_config = ConfigDict(extra="forbid")
    status: Literal["reviewed", "modified"]  # §7.5 硬约束：Literal 拒 pending
    notes: str | None = Field(default=None, max_length=4000)
    content: str | None = Field(default=None, min_length=1)  # modified 时使用
```

**S3 AssignmentReviewRequest**：同结构（`status` + `notes`），**无 `content`**（Assignment 内容 = items，不是单字段）。

---

## 五、API 设计（S3-backend）

| 方法 | 路径 | 用途 | 期望状态码 |
|---|---|---|---|
| `PATCH` | `/api/v1/assignments/{id}/review` | 老师审阅（status: reviewed/modified + notes）| 200 / 404 / 401 / 422 |
| `POST` | `/api/v1/assignments/{id}/export` | 触发 PDF 导出（闸门：review_status=APPROVED 才放行）| 200 / 403 / 404 / 401 |

### 5.1 鉴权

- 复用 `get_current_user_id`（`routers/assignments.py:40-58`，inline 定义）
- `X-User-Id` header 必填；缺失/非正整数 → 401
- 跨用户：`assignment.owner_user_id != user_id` → 404（D-29 硬规则，不暴露存在性）

### 5.2 `PATCH /review` 行为

- 404：assignment 不存在 / 不属于当前 user
- 200：成功
  - `reviewed` → `review_status = APPROVED`
  - `modified` → `review_status = MODIFIED`
  - `reviewed_by` / `reviewed_at` 落当前 user + UTC
  - `notes` 落 `review_notes`
  - 响应：`{"id": id, "review": TeacherReviewStatus}`
- 422：`status=pending`（Pydantic Literal 拒）+ 缺字段

### 5.3 `POST /export` 行为（PDF stub）

- 404：assignment 不存在 / 不属于当前 user
- 403：`review_status != APPROVED`（含 pending + modified）
- 200：`review_status == APPROVED`
  - 响应：
    ```json
    {
      "assignment_id": id,
      "export_id": "stub-{id}",
      "status": "queued",
      "note": "S3 stub; S4 接真 PDF 生成"
    }
    ```
  - **不实际生成 PDF**（S4 范围）

---

## 六、模型修改 + migration

### 6.1 Assignment 加 4 字段（`backend/app/models/assignment.py:60-80` 区间插入）

```python
# §7.5 字段（复用 KnowledgeReviewStatus 三态；模式同 LessonPlan.review_status @ academic.py:621-637）
review_status: Mapped[KnowledgeReviewStatus] = mapped_column(
    SAEnum(
        KnowledgeReviewStatus,
        name="knowledge_review_status_enum",
        native_enum=True,
        create_type=False,  # 复用 0002 创建的 enum，不重建
        values_callable=lambda enum_cls: [e.value for e in enum_cls],
    ),
    nullable=False,
    default=KnowledgeReviewStatus.PENDING,
    server_default=KnowledgeReviewStatus.PENDING.value,
    index=True,
)
reviewed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### 6.2 `migration 0010_assignment_review_fields.py`

- `revision: str = "0010_assignment_review_fields"`
- `down_revision: str | None = "0009_student_tier_audit_fields"`
- `upgrade()`：4 个 `op.add_column`（pattern 参照 0009）
- `downgrade()`：倒序 4 个 `op.drop_column`
- **不重建 enum**（`knowledge_review_status_enum` 由 0002 拥有，create_type 默认 False）

### 6.3 注意：KnowledgeReviewStatus import

- 当前在 `app.models.academic` line 72 局部定义
- S3 在 `assignment.py` 顶部 `from app.models.academic import KnowledgeReviewStatus`
- 已存在：`assignment.py` 顶部 `from app.models.academic import Chapter, Question, QuestionDifficulty, User`
- 验证：`app.models.academic` 模块可被循环引用（既有 import 链 OK）

---

## 七、测试设计（6 用例 = 5 反向 + 1 正向；防 D-28 家族）

### 7.1 反向 5 用例（防恒真门槛）

| # | 用例 | 期望 | 备注 |
|---|---|---|---|
| **R1** | 新建 assignment（review_status=pending）→ `POST /export` | **403** | 核心 §7.5 反向：未审不得导出 |
| **R2** | review_status=pending → `PATCH /review status=pending` | **422** | §7.5：Literal 拒 pending |
| **R3** | review_status=APPROVED → `PATCH /review status=pending` | **422** | 不允许降级（Literal 拒） |
| **R4** | assignment 属 user1 → user2 `PATCH /review` | **404** | D-29 跨用户隔离 |
| **R5** | assignment 属 user1 → user2 `POST /export` | **404** | D-29 跨用户隔离 |

### 7.2 正向 1 用例（防恒假门槛；金玉良言）

| # | 用例 | 期望 | 备注 |
|---|---|---|---|
| **F1** | review_status=pending → `PATCH /review status=reviewed + notes` → `POST /export` | **200 + 200** | 完整闭环：审阅后放行导出；DB 直查 `review_status.value == "approved"` / `reviewed_by == user_id` / `review_notes == "..."` |

### 7.3 测试结构

- 文件：`backend/tests/api/v1/test_assignment_review.py`（新增）
- 复用 fixtures：`mock_db_session` + `mock_user_system_seed` + `mock_textbook` + `mock_chapter`（conftest 既有）
- 6 个 test function：`test_R1_export_pending_403` ~ `test_R5_export_cross_user_404` + `test_F1_full_review_export_flow_200`
- 模式（参考 `test_b33_review_flow_e2e.py:38-94`）：
  - FastAPI TestClient + `dependency_overrides[get_db]`（hermetic）
  - headers `X-User-Id`
  - 断言 response status_code + JSON 内容
  - **DB 直查** 验证持久化（`mock_db_session.get(Assignment, id)` 查 `review_status.value` / `reviewed_by` / `review_notes`）

---

## 八、Commit 划分（5 commit；守 §5 教训 #9 不并片）

| # | 文件 | 范围 | 预检 |
|---|---|---|---|
| **C1** | `backend/app/models/assignment.py` + `backend/alembic/versions/0010_assignment_review_fields.py` | Assignment 加 4 字段 + alembic 0010 | `alembic upgrade head` exit 0 + `alembic downgrade -1 && alembic upgrade head` 幂等 |
| **C2** | `backend/app/api/v1/schemas/assignments.py` + local mapping functions in `routers/assignments.py` | schemas + local `_to_api_review_status` + `_to_orm_review_status` | `mypy app/api/v1/schemas/assignments.py` 0 + `mypy app/api/v1/routers/assignments.py` 0 |
| **C3** | `backend/app/api/v1/routers/assignments.py` | `PATCH /api/v1/assignments/{id}/review` endpoint（复用 `review_lesson_plan` 模式 + owner 直查）| `mypy app/api/v1/routers/assignments.py` 0 |
| **C4** | `backend/app/api/v1/routers/assignments.py` | `POST /api/v1/assignments/{id}/export` endpoint（PDF stub，§7.5 闸门）| `mypy app/api/v1/routers/assignments.py` 0 |
| **C5** | `backend/tests/api/v1/test_assignment_review.py` | 6 用例（5 反向 + 1 正向；容器 PG）| `pytest tests/api/v1/test_assignment_review.py` 6/6 PASSED（容器）|

---

## 九、入场闸（星云 2026-10-13 08:06 拍）

- `cd backend && ruff check app tests` → 0 errors
- `cd backend && mypy app` → 0 errors
- **pytest 必须容器 PG**（dev box SQLite 会假红/假绿；10-10 §三 实证）
  - 容器跑：`docker compose exec backend pytest -q tests/api/v1/test_assignment_review.py`
  - 本地 SQLite 跑结果**不算**（违反入场闸）

---

## 十、修正规则 #1 派工纪律（D-43-X §5；2026-10-12 留痕）

1. **1 次 subagent 派工（试）**：brief 完成后派 1 次 hidden subagent
2. **silent failure → 再派 1 次**：报回不完整 / 越界 / 未跑 pytest / commit 缺 4 字段 → 立即重派
3. **仍失败 → 父会话干**：2 次都失败才允许父会话自实施；必须留痕（§治理.13 系列 + memory/YYYY-MM-DD.md §X）

---

## 十一、完成定义

5 刀全部 commit + 报回 = subagent 完成：

- `ruff check app tests` exit 0
- `mypy app` exit 0
- `pytest tests/api/v1/test_assignment_review.py` 6/6 passed（容器 PG）
- 5 commit message 各含 4 字段（依赖 / 下游 / 预检 / 范围）+ `[origin-push]`
- `git diff dba448d..HEAD` 仅含 backend 范围（frontend / docs / .github / 项目根 meta 不动）
- `git status --porcelain` empty
- 未 push（push 归收工 8 步 §7）

---

## 十二、报回格式（每刀必带）

```
## C{N} 完成
- commit: <hash>
- message: <完整>
- 验收: <ruff / mypy / pytest 输出原文 + 容器 PG pytest 退出码>
- 范围: git diff --stat HEAD~1..HEAD
- 状态: ✅ / ⚠️ / ❌

## 6-line handshake
- pwd: <output>
- toplevel: <output>
- git-dir: <output>
- HEAD: <output>
- log -3: <output>
- remote: <output>
- status: <output>
```

---

## 十三、严禁

- 跳过 commit / 合并 commit / reword 已 commit 之外的 message
- push 远端（push 归收工 8 步 §7）
- 改禁动文件清单（docs/ / 项目根 meta / frontend/ / .github/ / STATE.md / memory/ / WAKEUP.md / AGENTS.md / README.md / .env.example / docker-compose.yml / pyproject.toml / requirements*.txt / alembic 既有 0001-0009 / frontend/ 全部）
- 改测试期望当修根因（D-43-X #14：把 assert 200 改 assert 404 当修 bug）
- 跑非容器 PG pytest（SQLite 会假红/假绿，违反入场闸）
- "差不多" 的 commit message（4 字段必齐 + [origin-push]）
- 报回不诚实（漏报修改文件 / 跳过验收原文）
- "已 ruff/mypy 通过" ≠ "代码能工作" —— 必须列 6 用例容器 pytest 输出
- 改既有 _enforce_owner_or_404 / _to_api_review_status / _to_orm_review_status / TeacherReviewStatus / KnowledgeReviewStatus（既有债不属 S3 范围）
- 引入新 enum / 新 mixin / 新 mapping 函数（违反 Q2 复用）
- 改 C4 词汇不一致（DB `approved` vs API `reviewed`）= 既有债，留独立工单


## 修订追记（2026-10-13 09:35 父会话收口 / 审核员转载曜 round 2 反馈）

**触发**：审核员转载曜 2026-10-13 09:32 round 2 A1 反馈 — brief 是唯一真值源但落地与描述逐条互斥；建议加"修订追记"（不改正文，便宜且保历史定稿完整）。

**brief 描述 vs 落地差异表**（落地 = 668fddd..6caf9b0 9 笔收工）：

| # | 维度 | brief 描述 | 落地 | 收口路径 |
|---|---|---|---|---|
| 1 | 用例数 | 6 用例（5 反向 + 1 正向）| **7 用例**（6 反向 + 1 正向；R6 modified → 403 闸门补） | A1 修法 = 补用例 C6 |
| 2 | commit 数 | 5 commit | **9 笔**（5 S3-backend + C6 R6 + C7 brief 入库 + commit 8 §治理.14 + commit 9 收工 amend）| A2 修法 = brief 入库 C7 + A3 修法 = commit 8 §治理.14 + 收工 amend |
| 3 | mypy 入场闸 | mypy app → 0 errors | mypy app → **2 errors in question_generator.py:213,262**（pre-existing base 债）| A3 修法 = §治理.14 落字豁免（决策不是默认）|
| 4 | 基线 SHA | dba448d | **668fddd**（frontend 3 commit landed via CI #85）| 父会话 21:55 merge m2-prep/frontend-skeleton 后推进 |
| 5 | working tree | status empty | status non-empty: 9 files +1239/-10 | 9 笔落地数字真值 |

**修法说明**：

- **不改正文**（brief 是决策室历史定稿；保留 2026-10-13 08:45 初版完整记录）
- **加追记**（保历史 + 当前真值双轨；下游读者既可看 brief 原意又可看落地差异）
- **不重 commit brief**（不重写文件，brief 在 C7 已 tracked）

**法源依据**：
- 审核员转载曜 2026-10-13 09:32 round 2 A1 反馈（brief 是唯一真值源，定稿需追记差异）
- D-43-X §5 修正规则 #1（自报字段必 fresh read 核源 = commit 8 + memory/STATE 失实 5 处的同源教训）
- D-43-X §5 round 1 收口规则（豁免是决策不是默认；brief 是决策室记录不是工程代码 = 修法不同）

**来源**：
- 本笔 commit 10 + reflog 证 c3486d3 → 854af47 → 6caf9b0（同一笔收工 amend 二次）
- `git diff --shortstat 668fddd..6caf9b0` 实测 = 9 files +1239/-10
- 9 笔 SHA 真值（按时间倒序）：6caf9b0 / ee2f528 / 958cb69 / 2b98662 / d8efe8b / 825e442 / 8c222c4 / b8d507d / 340280d
- 取数时刻 2026-10-13 09:35 +0800（按 D-75 §2）
