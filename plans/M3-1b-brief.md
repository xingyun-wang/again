# 题库层第 1 步 · 1b brief — 题库列表页

> 星云 2026-10-19 21:02 拍题库层第 1 步（1a 后端补齐 / 1b 题库列表页 / 1c 新建编辑抽屉）。
> 规格书 = 星云 10-19 21:02 附件《题库层设计 · 第 1 步（2026-10-19）》。
> 本 brief 摘自该规格 §二 1b + §五，并补 1b 的后端依赖（见 §1）。
> 基线 HEAD = `28ef94b`（本地）；待推 5 笔 = `741e6b3` / `814a334` / `1120d83` / `7ca9574` / `28ef94b`。
> **1a 已落地**（迁移 0012 加 points+answer_text + 3 接口 + P2 补丁自增/409）。

---

## 0. 已核源的事实（主 agent 实测，别再猜）

| 事实 | 证据 |
|---|---|
| `GET /questions` 现有参数 | `chapter_id` / `difficulty` / `type` / `knowledge_point_id`（单选）/ `limit`(≤200) / `offset`；**无 keyword** |
| `GET /questions` 响应 | `QuestionListResponse{items: QuestionRead[], total: int}` |
| `QuestionRead` 字段 | `id / owner_user_id / chapter_id / content / difficulty / type / points / answer_text / knowledge_point_ids / choices / created_at / updated_at`；**无 KP 名、无图片数** |
| `GET /textbooks` | ✅ 已存在（1a 落地）→ `TextbookSummary{id,title,grade,subject}` |
| 教材→章节级联 | ✅ `GET /textbooks/{textbook_id}/chapters` 已存在 |
| 知识点来源 | ✅ `GET /chapters/{id}` → `knowledge_points: [{id,name,concept,teaching_order}]`（1a 新建的 KP 就在这里） |
| 难度枚举 | `QuestionDifficulty`: D=基础 / C=进阶 / B=挑战 / A=扩展（`models/academic.py:671`）|
| 题型枚举 | `QuestionType`: choice / fill / subjective（`models/academic.py:690`）|
| 鉴权 | 前端必须带 `headers: {'X-User-Id': '1'}`（见 `frontend/src/pages/Assignments.tsx:117`）|
| 错误体形状 | 全局 handler 把 `detail` 改写成 `message` + `error_code`（`app/core/errors.py:107`）|
| 删题接口 | ✅ `DELETE /questions/{question_id}` 已存在（`routers/academic.py:1351`）|
| 前端范式 | `Assignments.tsx` = 纯 `useState` + antd + `apiClient`（**禁 zustand / React Query / SWR**）|
| `Questions.tsx` 现状 | 21 行 placeholder 骨架（`frontend/src/pages/Questions.tsx`）|
| 导航标签 | `frontend/src/components/Layout.tsx:35` = "设置"（规格 §五 要求改"题库"）|

---

## 1. 范围 = 2 个 commit（后端在前，前端在后）

### 1b-1 · 后端最小补充（commit A）— 规格 1b 要的 3 个能力现在拿不到

**为什么必须改**：规格 §二 1b 明确要求"关键词"筛选、"知识点（多选）"、"知识点标签"列、"图片数"列。
1a 只做了单选 `knowledge_point_id`，且 `QuestionRead` 不带 KP 名 / 图片数。**前端自己补 = N+1 请求 + 口径不一致**，所以后端补。

**改动 1 — keyword 搜索**
```python
keyword: Annotated[str | None, Query(min_length=1, max_length=200, description="题干关键词（ILIKE 模糊匹配）")] = None,
```
实现：`query = query.filter(Question.content.ilike(f"%{keyword}%"))`
（`ilike` SQLAlchemy 跨 PG/SQLite 自动降级为 `like`，不要写裸 `ILIKE` SQL）

**改动 2 — 知识点多选**
```python
knowledge_point_ids: Annotated[list[int] | None, Query(description="按知识点过滤（多选，OR 语义）")] = None,
```
- 语义 = **OR**（属于任一所选知识点即命中；老师按"等值线判读"筛出相关题）
- 实现注意：join 会产生重复行（一个题关联多个 KP）⇒ **必须 `.distinct()`**
```python
if knowledge_point_ids:
    query = (
        query.join(Question.knowledge_points)
        .filter(KnowledgePoint.id.in_(knowledge_point_ids))
        .distinct()
    )
```
- **既有单选 `knowledge_point_id` 保留不动**（向后兼容，1a 测试依赖它）
- 若 `knowledge_point_ids` 与 `knowledge_point_id` 同时给 ⇒ AND（两个条件都生效）

**改动 3 — QuestionRead 加 2 个展示字段**
```python
# QuestionRead 内新增
knowledge_point_names: list[str] = Field(default_factory=list, description="知识点名（表格标签列）")
image_count: int = Field(default=0, description="题目图片数（表格列）")
```
取值方式（**与既有 `knowledge_point_ids` property 同款**，见 `models/academic.py:849`）：
- 在 `models/academic.py` 的 `Question` 类加两个 **只读 property**（**不加列、不加迁移**）：
  ```python
  @property
  def knowledge_point_names(self) -> list[str]:
      return [kp.name for kp in self.knowledge_points]

  @property
  def image_count(self) -> int:
      return len(self.images)
  ```
- `Question.knowledge_points` 与 `Question.images` 都是 `lazy="selectin"` ⇒ **无 N+1**
- Pydantic v2 `from_attributes=True` 会自动读 property ⇒ schema 不用写 validator

**硬约束（1b-1）**
1. **不改迁移**：不新增迁移文件、不改 `0012_questions_points_and_answer.py`、不改任何 Question 列定义
2. **不改既有列**：只加 property（只读），不加 `mapped_column`
3. **不改前端**（本 commit 只动 backend）
4. **不改既有接口语义**：`knowledge_point_id` 单选保留；`GET /questions` 路径不变
5. **不改 batch / 抽题 / 学生 / 出卷 业务**（规格 §四 明确不做）
6. **不改 `GET /chapters/{id}` / `GET /textbooks` 响应形状**（1a + 既有页面依赖）
7. pytest 显式切 test 库，不污染 dev 库（跑法见 §5）
8. **不要 git push**（`[origin-push]` = 等主 agent 批推）

**测试**（新建 `backend/tests/test_m3_1b_backend.py`，不塞进 test_m3_1a.py）
至少 4 个 case：
1. `test_keyword_filters_questions` — 建 2 题（内容含"等值线" / "大气环流"）→ keyword="等值线" 只命中 1
2. `test_knowledge_point_ids_multi_or_semantics` — 建 3 题，分别关联 KP-A / KP-B / 无 KP → 传 [A,B] 命中 2 题（OR 语义），且**不重复计数**（total 正确）
3. `test_question_read_exposes_names_and_image_count` — 建 1 题关联 2 个 KP → 断言 `knowledge_point_names == ["KP名A","KP名B"]`（顺序按 KP 关系顺序）、`image_count == 0`
4. `test_existing_single_knowledge_point_id_still_works` — **回归**：单选参数行为不变（保证 1a 的 15 个测试不破）

### 1b-2 · 前端题库列表页（commit B）

**替换** `frontend/src/pages/Questions.tsx`（21 行 placeholder → 真页面）。

**筛选区**（顶部，antd Row/Col）
| 筛选项 | 控件 | 数据源 |
|---|---|---|
| 教材 | Select | `GET /textbooks` |
| 章节 | Select（**级联**：选教材后拉 `GET /textbooks/{textbook_id}/chapters`；未选教材时列出全部章节或禁用）| `GET /textbooks/{id}/chapters` |
| 知识点 | Select `mode="multiple"` | 选中章节 → `GET /chapters/{id}` 的 `knowledge_points`；**未选章节时 = 所选教材下所有章节的 KP 汇总**（可为空数组，别报错）|
| 难度 | Select（单选）| **显示名不显示字母**：D=基础 / C=进阶 / B=挑战 / A=扩展 |
| 题型 | Select（单选）| choice=选择题 / fill=填空题 / subjective=主观题 |
| 关键词 | Input.Search | 传给 `keyword` query |

**表格列**（规格 §二 1b 逐条对齐）
`ID` | `题干摘要`（`content` 截断 ~50 字 + Tooltip 全文）| `题型` | `难度`（显示名）| `分值`（`points`）| `知识点标签`（`knowledge_point_names` → 多个 `Tag`）| `图片数`（`image_count`）| `更新时间`（`updated_at`）| `操作`

**操作列 3 个按钮**
- `编辑` → 1c 才实现 ⇒ `message.info('编辑抽屉在 1c 实现')`，**不要自己画半成品抽屉**
- `看图` → 同上 `message.info(...)`（图片预览属 1c）
- `删除` → **真实现**：`Popconfirm` 二次确认 → `DELETE /questions/{id}` → 成功后刷新列表；失败按 `message` 展示（注意错误体是 `message` 不是 `detail`）

**分页**：`total` + `limit/offset`（`limit` 默认 20，`offset = (page-1)*limit`）；显示总数（`showTotal`）。
- 后端 `limit` 上限 200 ⇒ pageSize 选 20/50/100 均可

**主按钮**：`新建题目` → 1c 才实现 ⇒ `message.info('新建抽屉在 1c 实现')`

**状态管理**：纯 `useState`（**禁 zustand / React Query / SWR**）；鉴权 `headers: {'X-User-Id': '1'}`。
**错误处理**：请求失败时 `Alert`/`message` 展示 `body.message`（全局 handler 改写过，不是 `body.detail`）。
**加载态**：`Table loading` + 筛选请求中禁用按钮。

**IA 小修（规格 §五，1 行）**
`frontend/src/components/Layout.tsx:35`：`设置` → `题库`。
> 规格原文建议"归到'出作业'分组（或独立一级）"——**本笔只改标签文字，不动菜单位置**（位置调整属 IA 变更，超 1b 范围）。

**硬约束（1b-2）**
1. 只改 `frontend/src/pages/Questions.tsx` + `frontend/src/components/Layout.tsx`（后者只改那 1 个字）
2. **不新建前端文件**（组件就放 `Questions.tsx` 内）
3. **不改路由**（`/questions` 已在 `src/router/index.tsx:32`）
4. **不改后端**（本 commit 不动 backend）
5. **不改 9 条路由**、不动学情 / 出作业 / 备课页
6. **不引新依赖**（`package.json` 不动；antd / axios / react-router-dom 已够）
7. **不 push**

---

## 2. 1b 明确不做（规格 §四 + 星云边界）

- ❌ 抽题 / 学生 / 出卷 / 知识点自动提取 / 统计看板
- ❌ 新建编辑抽屉本体（= 1c）
- ❌ 批量导入 / 题目复制 / 版本历史 / 富文本 / 公式编辑器
- ❌ 外部题库导入（CSV / 粘贴）
- ❌ 图片上传（= 1c；1b 只显示 `image_count`）

---

## 3. 验收判据（1b 的 DoD）

1. `GET /questions?keyword=...` 真能筛出（curl 或 pytest 实证）
2. `GET /questions?knowledge_point_ids=1,2` 真能多选筛出且 total 不重复计数
3. `GET /questions` 响应含 `knowledge_point_names` + `image_count`
4. 前端 `/questions` 页面：筛选区 6 项齐全、表格 9 列齐全、分页可用、难度显示中文名
5. `npm run lint`（`--max-warnings 0`）+ `npx tsc -b --noEmit` + `npm run build` 全过
6. **运行时证据**（不许只贴代码）：vite dev 起服务后，编译产物里能找到筛选区 6 个控件的 JSX + 表格 9 列的列头 + `知识点` / `分值` / `图片数` 等字样（贴 grep 出来的编译后 JSX 片段）
7. `Layout.tsx` 的 "题库" 标签在编译产物里出现
8. **不得 push**

---

## 4. 必报项（缺一项 = 回执不完整）

1. commit SHA × 2（1b-1 后端 / 1b-2 前端）+ 各自 commit message 全文
2. 各自 `git show --stat`
3. **pytest 输出**：新测试文件 + **全量** `pytest tests -q`（显式 test 库）
4. **新增字段真值**：`grep -n "knowledge_point_names\|image_count" backend/app/{models,api/v1/schemas}/academic.py` + `grep -n "keyword\|knowledge_point_ids" backend/app/api/v1/routers/academic.py`
5. **迁移未动**：`git diff HEAD~2 --name-only -- backend/alembic | wc -l` = 0
6. **前端 3 证据**：`npm run lint` / `npx tsc -b --noEmit` / `npm run build` 输出 + 编译后 JSX grep 片段
7. **4 法核源**：`git rev-parse --show-toplevel` + `--absolute-git-dir` + `HEAD` + `git remote -v` + `git status --porcelain`
8. **未推送确认**：`git log origin/master -1 --format=%h` 仍为 `a6e30a5`；`git log github/master -1 --format=%h` 仍为 `a6e30a5`
9. **已知 pre-existing 照实报**：本地 host mypy 1.14.1/py3.8 会在 `app/services/question_generator.py:217,266` 报 2 个 `[index]` 错误 —— 那是**跨环境假红**（容器 py3.11 + mypy 2.4.0 = `Success: no issues found in 40 source files`），**不要去改它**。若你改动的文件在容器 mypy 下有真错，必须修。

---

## 5. 环境硬约束（血泪，务必照做）

### 5.1 backend 无 bind-mount ⇒ 改完代码必须先同步再跑测试
`docker-compose.yml` 的 backend 服务**不挂载源码**（只挂 `./data/uploads`）⇒ 容器 `/app` = 镜像烘焙版。
**不改镜像直接跑 pytest = 跑旧代码 = 假绿**（已真实踩过：首次跑出「15 passed」是假绿）。

**做法（二选一）**：
```bash
# A) 重建镜像（最干净，但慢 ~3-5 min）
docker compose build backend && docker compose up -d backend
# B) 直接同步改动文件进容器（快）
docker compose cp backend/app backend:/app/app
docker compose cp backend/tests backend:/app/tests
```
> ⚠️ **runtime 镜像不含 pytest**（dev 依赖只在 builder stage）⇒ 跑测试要用 builder 镜像：
> ```bash
> docker build --target builder -t thp-backend-builder:latest backend/
> docker run --rm --network tiered-homework-m0_thp-net \
>   -e DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/tiered_homework_test \
>   -e DEEPSEEK_API_KEY=dummy -w /app thp-backend-builder:latest \
>   python -m pytest tests -q
> ```
> 用 builder 镜像时 `DATABASE_URL` 用 **test 库**（`tiered_homework_test`），**不要用 dev 库**。

### 5.2 test 库跑法（每轮 pytest 前必做 2 条）
conftest teardown 只 `drop_all(Base.metadata)`，**不动 `alembic_version`** ⇒ 第二轮起 `alembic upgrade head` 变 no-op ⇒ 表全丢 ⇒ `NoSuchTableError`。
```bash
docker compose exec -T postgres psql -q -U postgres -d tiered_homework_test -c "DROP TABLE IF EXISTS alembic_version;"
docker compose exec -T -e DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/tiered_homework_test backend alembic upgrade head
```

### 5.3 断言错误体用 `body["message"]`
全局 handler 把 `detail` 改写成 `message` + `error_code`（`app/core/errors.py:107`）；409 → `error_code="CONFLICT"`。

### 5.4 CI 等价数字参考
- builder 镜像 + PG（`DEEPSEEK_API_KEY=dummy`）全量 = **343 passed, 14 skipped**（总 357）
- 容器内 mypy = `mypy app` → `Success: no issues found in 40 source files`
- CI 的 `ruff check app tests` 只查 `app` + `tests`（**不含 `scripts/`**）

---

## 6. 失败处理

任何一步卡住：**立即停止**，回执写明 `卡在第 N 步 / 现象 / 已排除的原因 / 需要什么才能继续`。
**不要自行扩大范围**、**不要留半成品 commit**、**不要 push**。
