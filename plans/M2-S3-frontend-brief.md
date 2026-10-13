# M2-S3-frontend brief — 作业生成 + 审阅 UI 落地（v0.5 §3.6 + §7.5）

> **承接决策**：M2-S3-backend 已收工（master HEAD `f6b564c` / 23 commit）+ M2-S3-brief §三 Q1 拆 2 段 = S3-backend 今晚 + S3-frontend 明日（= 今日下午 2026-10-13）
> **本 brief 范围**：B4 backend 必改（`AssignmentRead` 加 `review` 字段 + GET/POST 手动构造）+ 1 pytest 验证用例 + 作业生成页 UI（`Assignments.tsx` 真 UI）+ 审阅页 UI（`Review.tsx` 真 UI）
> **不在范围**：PDF 实际生成（S4）/ K/M/N 动态调整算法（M3）/ 词汇不一致债（DB `approved` vs API `reviewed` = 既有债，留独立工单）/ 其他 6 个 M2 骨架 placeholder（Home, Questions, Import, Tiering, AntiMatthew, TierOverride = M2 骨架期保留）
> **最后更新**：2026-10-13 14:00（载曜落字；待星轨 review）
> **承载体**：本文件 `plans/M2-S3-frontend-brief.md`

---

## 一、范围

### 1.1 必交付

- **B4 必改 (backend)**: `AssignmentRead` schema 加 `review: TeacherReviewStatus` 字段 + `routers/assignments.py` GET + POST endpoints 手动构造 review（防 Pydantic `from_attributes` 不兼容；详见 §四 复用既有模式）
- **B4 验证 (backend)**: `tests/api/v1/test_assignment_review.py` 加 1 个用例（F2）验证 GET 响应含 `review` 字段
- **作业生成页 UI**: `frontend/src/pages/Assignments.tsx` 21 行 placeholder → 真 UI
- **审阅页 UI**: `frontend/src/pages/Review.tsx` 21 行 placeholder → 真 UI
- 3 commit（守 §5 教训 #9 不并片）

### 1.2 不在范围（延后 S4 / M3 / 其他）

- ❌ PDF 实际生成（S4 brief；S3 仅 stub）
- ❌ K/M/N 动态调整算法（M3；Assignment ↔ Student 绑定未建模）
- ❌ DB enum `approved` vs API Literal `reviewed` 词汇不一致（既有债；S3-frontend 复用既有 enum，不引入第三套）
- ❌ 其他 6 个 M2 骨架 placeholder page（Home / Questions / Import / Tiering / AntiMatthew / TierOverride = M2 骨架期保留，等 S1-S4 各段启动时分别替换）
- ❌ 路由配置改动（路由已就位 `/assignments` + `/review` = 决策书 §7.1 补丁 A）
- ❌ store / auth / API client 架构调整（M1-B B.2 简化 auth 已就位；`X-User-Id` header 写死 `1` 给 demo）
- ❌ 跨表 audit log（D-37 family；既有 `reviewed_by` / `reviewed_at` 字段已够）

---

## 二、§7.5 + §3.6 拍板（重述；M2-S3-backend 已落字）

- §3.6 第 3 步：老师最终审阅 = AI 输出 = 建议，老师必须审阅；`PATCH /review` 标记 `reviewed` / `modified`
- §7.5 硬约束：未审不得导出 = `review_status != APPROVED` → `POST /export` 必须 403
- 默认 `review_status = pending`（新建后）
- 复用 `KnowledgeReviewStatus`（0002）三态 + `TeacherReviewStatus` mixin + `PATCH /review` 模式；**零新词汇 / 零新 enum / 零新 mapping**

---

## 三、严禁（继承 M2-S3-brief §13 + S3-frontend 增）

继承 M2-S3-brief §13 严禁 + 以下：

- 改 `TeacherReviewStatus` 既有 schema（`academic.py:49-65`）= 既有债不属 S3 范围
- 改 `_to_api_review_status` / `_to_orm_review_status` 既有 mapping（`routers/assignments.py:60-78` 局部 copy）= 既有债
- 改 `KnowledgeReviewStatus` ORM enum 既有（`academic.py`）= 既有债
- 改既有 `routers/academic.py` 任何文件
- 改其他 6 个 M2 骨架 placeholder page（Home / Questions / Import / Tiering / AntiMatthew / TierOverride）
- 改 `frontend/src/router/index.tsx`（路由已就位）
- 改 `frontend/src/store/useAppStore.ts`（状态层只 sidebar 状态）
- 改 `frontend/src/main.tsx` / `App.tsx` / `index.css` / `package.json`（框架层；不引新依赖）
- 改 `plans/M2-A.1-brief.md` / `M2-S2-brief.md` / `M2-S3-brief.md`（既有 brief = 决策室历史定稿）
- 改 `docs/` / `notes/` / `memory/` / 项目根 `STATE.md` / `WAKEUP.md` / `AGENTS.md` / `README.md` / `.env.example` / `docker-compose.yml` / `pyproject.toml` / `requirements*.txt`（既有/收工范围）
- 改 `.github/` 全部
- 改 `backend/alembic/versions/0001-0011_*.py`（既有 migration）
- 改 `backend/app/models/assignment.py` 4 review 字段（已有，不动；不增不减）
- 引入新 enum / 新 mixin / 新 mapping 函数（违反 Q2 复用）
- 引入新依赖 / 新包（优先用既有 `antd 5.21` + `zustand` + `react-router` + `axios`）

---

## 四、复用既有模式（核源 2026-10-13 14:00）

### 4.1 关键发现：`TeacherReviewStatus` 无 `from_attributes=True`

```python
# backend/app/api/v1/schemas/academic.py:53-65（实测）
class TeacherReviewStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")  # ← 没有 from_attributes
    review_status: Literal["pending", "reviewed", "modified"] = "pending"
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None
```

**含义**：`AssignmentRead` 加 `review: TeacherReviewStatus` 字段后，单纯 `AssignmentRead.model_validate(assignment)` **不会**自动从 ORM `assignment.review_status` / `reviewed_by` / `reviewed_at` / `review_notes` 构造 `review` 子对象。

**修法（§三 严禁下唯一可行）**：`routers/assignments.py` 的 GET + POST endpoints 改成**手动构造 review**（仿 PATCH /review 模式）：

```python
# GET /api/v1/assignments/{id}  (routers/assignments.py:111-130)
@router.get("/assignments/{assignment_id}", response_model=AssignmentRead)
def get_assignment(assignment_id: int, db, user_id) -> object:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(404, detail=f"assignment {assignment_id} 不存在")
    if assignment.owner_user_id != user_id:
        raise HTTPException(404, detail=f"assignment {assignment_id} 不存在")
    # B4 修法：手动构造（含 review 字段，仿 PATCH /review 模式）
    return AssignmentRead(
        id=assignment.id,
        owner_user_id=assignment.owner_user_id,
        chapter_id=assignment.chapter_id,
        tier=assignment.tier,
        total_count=assignment.total_count,
        d_count=assignment.d_count,
        c_count=assignment.c_count,
        b_count=assignment.b_count,
        a_count=assignment.a_count,
        seed=assignment.seed,
        created_at=assignment.created_at,
        items=[AssignmentItemRead.model_validate(item) for item in assignment.items],
        review=TeacherReviewStatus(
            review_status=_to_api_review_status(assignment.review_status),
            reviewed_by=assignment.reviewed_by,
            reviewed_at=assignment.reviewed_at,
            review_notes=assignment.review_notes,
        ),
    )
```

POST /assignments (`routers/assignments.py:67-104`) 同理（`return AssignmentRead.model_validate(assignment)` → 手动构造）。

### 4.2 §7.5 闸门（已实现，S3-frontend 仅 UI 集成）

- `POST /api/v1/assignments/{id}/export`:
  - `review_status == APPROVED` → 200 + stub response
  - `review_status != APPROVED` → 403 + 未审提示
  - 现有代码：`routers/assignments.py:317-355`（已收工，不动）

### 4.3 现有 API 客户端（`frontend/src/api/client.ts`）

```typescript
import axios from 'axios'
const apiPrefix = import.meta.env.VITE_API_PREFIX || '/api'
export const apiClient = axios.create({
  baseURL: apiPrefix,
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})
```

**用法**：`apiClient.post('/assignments', body, { headers: { 'X-User-Id': '1' } })`。Demo 阶段 `X-User-Id` 写死 `1`（M1-B B.2 简化 auth）。

### 4.4 现有 antd 组件（`frontend/package.json`）

- `antd: ^5.21.6` + `@ant-design/icons: ^5.5.1` + `@ant-design/pro-components: ^2.8.10`
- 优先用：`Form` / `InputNumber` / `Select` / `Input.TextArea` / `Button` / `Alert` / `Table` / `Descriptions` / `Card` / `Space` / `Tag` / `Typography`

---

## 五、API 设计（S3-frontend 调用契约；不需再读 backend）

### 5.1 `POST /api/v1/assignments`（创建）

- Headers: `X-User-Id: 1`, `Content-Type: application/json`
- Body: `{ "chapter_id": 1, "tier": "D" | "C" | "B" | "A", "total_count": 30, "seed": null }`
- 201: `AssignmentRead`（含 `review` 字段 = B4 新增）
- 401 / 404 / 422

### 5.2 `GET /api/v1/assignments/{id}`（查询）

- Headers: `X-User-Id: 1`
- 200: `AssignmentRead`（含 `review` 字段 = B4 新增）
- 401 / 404

### 5.3 `PATCH /api/v1/assignments/{id}/review`（审阅）

- Headers: `X-User-Id: 1`, `Content-Type: application/json`
- Body: `{ "status": "reviewed" | "modified", "notes": "..." }`
- 200: `{ "id": id, "review": TeacherReviewStatus }`
- 422（`status=pending` Literal 拒）/ 404

### 5.4 `POST /api/v1/assignments/{id}/export`（PDF stub 闸门）

- Headers: `X-User-Id: 1`
- 200: `{ "assignment_id": id, "export_id": "stub-{id}", "status": "queued", "note": "S3 stub; S4 接真 PDF 生成" }`
- 403: `review_status != APPROVED`（§7.5 硬约束）
- 401 / 404

---

## 六、B4 必改 + pytest 验证

### 6.1 B4 schema 改动

**`backend/app/api/v1/schemas/assignments.py`**:

- 在 `AssignmentRead` class 内（line 56-73 区间）加字段：
  ```python
  review: TeacherReviewStatus
  ```
- 顶部 import 已有 `from app.api.v1.schemas.academic import TeacherReviewStatus`（无需新增）

### 6.2 B4 router 改动

**`backend/app/api/v1/routers/assignments.py`**:

- GET endpoint（line 111-130）：改 `return AssignmentRead.model_validate(assignment)` → 手动构造（含 `review` 字段，仿 §4.1 模式）
- POST endpoint（line 67-104）：改 `return AssignmentRead.model_validate(assignment)` → 手动构造（含 `review` 字段）
- 注意：`_to_api_review_status` 已在文件 line 60-72 局部定义，**复用即可**
- 注意：`TeacherReviewStatus` 已在文件 line 21 import，**复用即可**
- 注意：`_enforce_owner_or_404` 不动（§三 禁）

### 6.3 B4 pytest 验证

**`backend/tests/api/v1/test_assignment_review.py`**:

- 加 1 个用例（`test_F2_get_assignment_includes_review_field_200` 或类似命名）：
  - **前置**: 建 assignment（`review_status=pending`）→ `GET /api/v1/assignments/{id}`（同 user）
  - **断言**: `response.status_code == 200` + JSON 包含 `review` 字段 + `review.review_status == "pending"` + `review.reviewed_by is None` + `review.reviewed_at is None` + `review.review_notes is None`
  - **DB 直查**: `assignment.review_status.value == "pending"`（无修改）
- **不改既有 7 用例**（避免预期值变化导致旧用例挂；既有用例不查 `review` 字段，应保持 PASS）

---

## 七、作业生成页 UI（`frontend/src/pages/Assignments.tsx`）

### 7.1 现状

21 行 placeholder（Card + Title + Paragraph + Tag），路由 `/assignments`。

### 7.2 目标

真 UI - 表单 + 结果展示 + 闸门演示。

### 7.3 布局（antd 组件）

- **Card 1: 创建作业表单**
  - `Form` `layout="vertical"`
  - `Form.Item` label="章节 ID" `name="chapter_id"` `InputNumber` min=1（写死 default=1 给 demo）
  - `Form.Item` label="档位" `name="tier"` `Select` options=`[{value:'D',label:'D 基础'},{value:'C',label:'C 进阶'},{value:'B',label:'B 挑战'},{value:'A',label:'A 扩展'}]`
  - `Form.Item` label="总题数" `name="total_count"` `InputNumber` min=1 max=200 default=30
  - `Form.Item` label="随机种子" `name="seed"` `InputNumber` placeholder="留空 = 系统时间"
  - `Button type="primary"` htmlType="submit" → 调 `POST /api/v1/assignments`

- **Card 2: 创建结果**（提交成功后显示）
  - `Descriptions` 展示 assignment 字段（id, chapter_id, tier, total_count, d_count, c_count, b_count, a_count, created_at）
  - `Alert` 展示 review 字段（review_status, reviewed_by, reviewed_at, review_notes）
  - `Button` "导出 PDF" → 调 `POST /api/v1/assignments/{id}/export`
    - **200**: `Alert type="success"` 显示 `export_id` + `status="queued"` + `note`
    - **403**: `Alert type="warning"` 显示 "未通过审阅（review_status=pending）" + §7.5 闸门提示
    - **404**: `Alert type="error"` 显示 "assignment 不存在"
    - **401**: `Alert type="error"` 显示 "X-User-Id 缺失"

### 7.4 错误处理

- `try / catch` axios.post → `catch (err) { const code = err.response?.status; ... }`
- 按 status code 显示对应 Alert
- **不要** `console.log` 静默

### 7.5 State

- 用 `useState` 管 form + result + alert
- 不引入 zustand（`useAppStore` 不动）
- 不用 React Query / SWR（暂不引新依赖）

---

## 八、审阅页 UI（`frontend/src/pages/Review.tsx`）

### 8.1 现状

21 行 placeholder，路由 `/review`。

### 8.2 目标

真 UI - 加载 + 显示 + 审阅表单。

### 8.3 布局

- **Card 1: 加载作业**
  - `InputNumber` min=1 输 assignment_id
  - `Button` "加载" → 调 `GET /api/v1/assignments/{id}`
    - **200**: 显示 Card 2 + 3
    - **404**: Alert "assignment 不存在"
    - **401**: Alert "X-User-Id 缺失"

- **Card 2: 作业详情**（加载成功后显示）
  - `Descriptions` 展示 assignment 全字段
  - `Alert` 展示 review 字段（4 子字段）

- **Card 3: 审阅表单**
  - `Form` `layout="vertical"`
  - `Form.Item` label="审阅状态" `name="status"` `Select` options=`[{value:'reviewed',label:'通过 (reviewed)'},{value:'modified',label:'修改 (modified)'}]`
  - `Form.Item` label="审阅备注" `name="notes"` `Input.TextArea` rows=4 maxLength=4000
  - `Button type="primary"` htmlType="submit" → 调 `PATCH /api/v1/assignments/{id}/review`
    - **200**: 更新 Card 2 状态 + Alert "审阅成功"
    - **422**: Alert "status 必为 reviewed/modified（Literal 拒 pending）"
    - **404**: Alert "assignment 不存在"
    - **401**: Alert "X-User-Id 缺失"

### 8.4 State

- 用 `useState` 管 assignment_id + assignment + form + alert
- PATCH 成功后更新本地 assignment state

---

## 九、Commit 划分（3 commit；守 §5 教训 #9 不并片）

| # | 文件 | 范围 | 预检 |
|---|---|---|---|
| **C1** | `backend/app/api/v1/schemas/assignments.py` + `backend/app/api/v1/routers/assignments.py`（GET + POST）| `AssignmentRead` 加 `review` 字段 + GET/POST 手动构造 review | `ruff check app tests` 0 + `mypy app` 0 |
| **C2** | `backend/tests/api/v1/test_assignment_review.py` | 1 新用例（F2 GET 含 review 字段）| `pytest tests/api/v1/test_assignment_review.py` 8/8 PASSED（容器 PG）|
| **C3** | `frontend/src/pages/Assignments.tsx` + `frontend/src/pages/Review.tsx` | 2 page 真 UI（含 §七 + §八 完整布局）| `npx tsc --noEmit` 0 + `npx vite build` 0 errors |

注：frontend 必检 `tsc` + `vite build`。pytest 必跑容器 PG（dev box SQLite 会假红/假绿；M2-S3-brief §九 已实证）。

---

## 十、入场闸（承 M2-S3-brief §九 + 增 frontend）

- `cd backend && ruff check app tests` → 0 errors
- `cd backend && mypy app` → 0 errors（含 §治理.16 既有债豁免）
- `docker compose exec backend python -m pytest -q tests/api/v1/test_assignment_review.py` → 8/8 passed（容器 PG；dev box 跑不算）
- `cd frontend && npx tsc --noEmit` → 0 errors
- `cd frontend && npx vite build` → 0 errors

---

## 十一、§治理.19 派工前/后 4 验 baseline（必做）

**派工前**（在 worktree 跑）:

1. `docker compose exec backend alembic current` → 期望 `0011_question_images (head)`
2. `docker compose exec backend python -m pytest -q tests/api/v1/test_assignment_review.py` → 期望 7/7 passed（**触发 conftest `drop_all` = dev 库清空 = 字面绿口头红 trap 实证**；不重跑）
3. `docker compose exec backend python -c "..."` 查 user_tables + enums → 期望 0/0 + `alembic_version=0011`（**字面绿口头红 trap 实证记录**）
4. (不重跑避免 `drop_all` 二次)

**派工后**（**必 2 步重建**）:

1. `docker compose exec backend alembic stamp base && docker compose exec backend alembic upgrade head`（**必 2 步；§治理.19 修正规则**：单跑 `upgrade head` = 不动 trap）
2. `docker compose exec backend python -c "..."` 查 user_tables + enums → 期望 19/7 + `alembic_version=0011`（**重建真值**）
3. `docker compose exec backend python -m pytest -q tests/api/v1/test_assignment_review.py` → 期望 8/8 passed（**新增 F2**）
4. `docker compose exec backend python -c "..."` 再查 user_tables + enums → 期望 0/0 + `alembic_version=0011`（pytest 又 `drop_all`；**记录不修复** = 收工 8 步父会话最后重建）

---

## 十二、D-43-X §5 修正规则 #1 派工纪律

1. **1 次 subagent 派工（试）**
2. **silent failure → 再派 1 次**：报回不完整 / 越界 / 未跑 pytest / commit 缺 4 字段 / frontend 报"tsc 通过"但无原文 / "vite build 通过"但无原文 → 立即重派
3. **仍失败 → 父会话干**：2 次都失败才允许父会话自实施；必须留痕（§治理.13 系列 + `memory/2026-10-13.md` §X）

---

## 十三、完成定义（DoD）

3 刀全部 commit + 报回 = subagent 完成：

- `ruff check app tests` exit 0
- `mypy app` exit 0
- `pytest tests/api/v1/test_assignment_review.py` 8/8 passed（容器 PG）
- `npx tsc --noEmit` exit 0
- `npx vite build` exit 0
- 3 commit message 各含 4 字段（依赖 / 下游 / 预检 / 范围）+ `[origin-push]`
- `git diff master..HEAD --stat` 仅含允许范围（B4 + pytest + 2 page）
- `git status --porcelain` empty
- 未 push（push 归收工 8 步 §7）

---

## 十四、报回格式（每刀必带）

```
## C{N} 完成
- worktree: <path>
- branch: <name>
- commit: <hash>
- message: <完整>
- 验收: <ruff / mypy / pytest / tsc / vite build 原文输出 + exit code>
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

## 十五、修订追记

无（v1 落字；如有 round 2/3 反馈 = 加追记模式，仿 M2-S3-brief 末尾）

---

> **【2026-10-13 14:00 变更说明 · plans/M2-S3-frontend-brief.md】**
>
> **修订范围**: 1 项 v1 落字（M2-S3-frontend brief 首版）
> 1. **M2-S3-frontend brief 入库** = B4 必改 (backend) + 1 pytest 验证 (F2) + 2 page 真 UI = 3 commit
> 2. **§四 关键发现**: `TeacherReviewStatus` 无 `from_attributes=True` → 必须手动构造 review（仿 PATCH /review 模式；§三 严禁下唯一可行）
> 3. **§十一 §治理.19 派工前/后 4 验**: 字面绿口头红 trap 实证记录 + 必 `stamp base + upgrade head` 二步重建
> 4. **§三 严禁继承 M2-S3-brief §13 + S3-frontend 增**: 不动 TeacherReviewStatus / mapping / 既债
>
> **法源依据**: M2-S3-brief §三 Q1 拆 2 段 + M2-A.1-brief 7-bullet 框架 + v0.5 §3.6/§7.5 + 决策书 §3 备注 + 补丁 B
>
> **承载体**: 本文件 + `plans/` 目录（既有 brief 共居）= 不入 gitignore
