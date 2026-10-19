# M3-1a brief: 题库层第 1 步 · 后端补齐（迁移 0012 + 3 接口）

> **派工人**：载曜｜**派工日**：2026-10-19 21:0x｜**批准**：星云（题库层第 1 步 21:02 拍）
> **基线**：HEAD = `a6e30a5`（B2 越权推后；CI run #124 绿；推双 remote 已发生）
> **阻塞**：1b / 1c 依赖 1a（前端需要 1a 接口）
> **回执 commit message 必带**：`[origin-push]`（WAKEUP 8 步授权机制）

---

## §1 任务清单（4 项 = 1 alembic 迁移 + 3 接口）

### 1.1 迁移 `0012` = questions 加 **严格两列**（星云明确）

> **0012 只加两列，不要夹带批次/学生/条码**（星云 §六 #2）；0013 的事不进 0012。

| 列 | 类型 | server_default | nullable |
|----|------|---------------|----------|
| `questions.points` | `Numeric(5,1)` | `"2.0"` | False |
| `questions.answer_text` | `Text` | (无) | True |

**新文件**：`backend/alembic/versions/0012_questions_points_and_answer.py`

- `revision = "0012_questions_points_and_answer"`
- `down_revision = "0011_question_images"`（继承 chain；**必须** `alembic upgrade` + `downgrade` 都跑通）
- `upgrade()` = `op.add_column("questions", sa.Column("points", sa.Numeric(5,1), nullable=False, server_default="2.0"))` + `answer_text` 同
- `downgrade()` = drop 两列

**model 同步**（同一 commit）：
- `backend/app/models/academic.py` `Question` 类加：
  - `points: Mapped[float] = mapped_column(Numeric(5,1), nullable=False, default=2.0)`
  - `answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)`

### 1.2 `GET /api/v1/academic/textbooks`（**新建**）

**现状**：`POST /textbooks/upload` + `GET /textbooks/{id}/chapters`；**无 GET 列表**

**新接口**：
```python
@router.get("/textbooks", response_model=list[TextbookSummary])
def list_textbooks(...):
    rows = db.query(Textbook).filter(Textbook.owner_user_id == current_user.id).order_by(Textbook.id.asc()).all()
    return rows
```

- `TextbookSummary` schema = `backend/app/api/v1/schemas/academic.py` 新增（4 字段：id / title / grade / subject）
- 显式按 `owner_user_id` 过滤（per CHARTER §3 题库属教师个人资产）

### 1.3 `POST /chapters/{chapter_id}/knowledge-points`（**新建**）

**现状**：`KnowledgePoint` model 已存在（`academic.py:456`；`__tablename__ = "knowledge_points"`）；`chapter.knowledge_points` 关系已存在（:432 `lazy="selectin"`）；`question_knowledge_points` 多对多表已存在（:736）；**仅缺 POST 创建接口**

**新接口**：
```python
@router.post("/chapters/{chapter_id}/knowledge-points", response_model=KnowledgePointDetail, status_code=201)
def create_knowledge_point(chapter_id: int, payload: KnowledgePointCreate, ...):
    # 1. chapter 存在性检查 (404 if not)
    chapter = db.get(Chapter, chapter_id)
    if not chapter:
        raise HTTPException(404, "chapter not found")
    # 2. 创建 KP
    kp = KnowledgePoint(chapter_id=chapter_id, name=payload.name, concept=payload.concept, teaching_order=payload.teaching_order)
    db.add(kp); db.commit(); db.refresh(kp)
    return kp
```

- `KnowledgePointCreate` + `KnowledgePointDetail` schema = `schemas/academic.py` 新增
- 字段：name（必填）/ concept（可空）/ teaching_order（数字，默认 0）

### 1.4 `GET /questions` 加 `knowledge_point_id` 参数（**修改**）

**现状**：`GET /questions` 已支持 `chapter_id` / `difficulty` / `type` 过滤（`academic.py:953` 注释 + 实际路由在 `:1008-1080` 段附近）

**修改**：
```python
def list_questions(
    ...,
    knowledge_point_id: int | None = Query(None),
    ...,
):
    q = db.query(Question)
    if knowledge_point_id:
        q = q.join(Question.knowledge_points).filter(KnowledgePoint.id == knowledge_point_id)
    ...
```

- join 走 `Question.knowledge_points`（model 已声明 `secondary="question_knowledge_points"`）—— **不要**直接 join 关联表（用 ORM 关系即可）

---

## §2 4 边界（per 规格 §四 + §六）

### 2.1 不做（per 规格 §四）
- 外部题库导入（CSV / 粘贴）
- 批量导入、题目复制、版本历史
- 题干富文本 / 公式编辑器
- 知识点自动提取
- 题库统计看板

### 2.2 不做（per 规格 §六 #1 "不要顺手做"）
- 抽题（决策 1-7 = batch 实体；属 A2 / 0013）
- 学生（决策 3 = 学生子集；属 0013+）
- 出卷（决策 6 = 合并 PDF；属 D3）

### 2.3 不做（per 规格 §六 #2 "0012 严格两列"）
- 批次字段（0013 的事）
- 学生字段（0013 的事）
- 条码字段（0013 的事）
- KP 表 / KP model / 关联表（**都已存在**于早期 alembic 迁移，**不**在 0012 范围）

### 2.4 不动
- 0011 之前的迁移（不动 alembic chain 中的历史迁移）
- 现有 `KnowledgePoint` / `Chapter` / `Question` / `question_knowledge_points` model（只**加字段**给 Question；不改其他）
- `frontend/`（**完全不动**；1b / 1c 范围）
- 现有 pytest（**只加** 1a 接口相关测试；不删 / 不改既有测试）

---

## §3 4 法核源（必跑 + 必报）

| 项 | 文件 / 实际 | 4 法核源结果 |
|----|------------|--------------|
| alembic 最新 | `backend/alembic/versions/0011_question_images.py` | `revision = "0011_question_images"` / `down_revision = "0010_assignment_review_fields"` |
| Question model 现状 | `backend/app/models/academic.py` `class Question(Base):` | 已有；**无 points / answer_text 字段** —— 1.1 要加 |
| KnowledgePoint model | `backend/app/models/academic.py:456` | **已存在**（F1 描述"零命中"是过时观察；model 真的在） |
| chapter.knowledge_points 关系 | `backend/app/models/academic.py:432` | **已存在**（`lazy="selectin"`；`back_populates="chapter"`） |
| question_knowledge_points 表 | `backend/app/models/academic.py:736` | **已存在**（`Table("question_knowledge_points", Base.metadata, ...)`） |
| Textbook model | `backend/app/models/academic.py` | 已有；1.2 用 owner_user_id 过滤 |
| /textbooks 路由 | `backend/app/api/v1/routers/academic.py:221, 348` | 只有 upload + chapters；**缺 GET 列表** |
| /questions 路由 | `backend/app/api/v1/routers/academic.py:1008-1080` | 已支持 chapter/difficulty/type 过滤；**缺 knowledge_point_id** |
| /chapters/{id}/knowledge-points POST | `grep -rn "/knowledge-points" backend/app/api/v1/` | **完全缺失** |
| 测试库 | `tiered_homework_test` | 显式 `-e DATABASE_URL=postgresql+psycopg://...tiered_homework_test`（per §治理.19；**不污染 dev 库**） |

---

## §4 必报项（per D-43-X = 4 法核源 + 物理可达证据）

1. **CI run #**（ruff + mypy + alembic upgrade + alembic downgrade + pytest 全套）+ commit SHA
2. **0012 迁移双跑** = `alembic upgrade head` + `alembic downgrade base && alembic upgrade head` 真实跑过（**真可回滚** = D-43-X §3）
3. **0012 字段真值** = alembic upgrade 后用 SQLAlchemy `inspect()` 或 psql `\d questions` 验证 `points` + `answer_text` 两列真存在
4. **3 接口 curl 真值**（沙箱内本地起 backend + curl）：
   - `POST /api/v1/textbooks/upload`（建 1 教材）+ `GET /api/v1/textbooks`（验证列表含）
   - `POST /api/v1/chapters/{chapter_id}/knowledge-points`（建 3 KP）+ `GET /api/v1/chapters/{chapter_id}`（验证 KP 列表含）
   - `POST /api/v1/questions`（建 1 题 with points=10.0 + knowledge_point_ids=[1]）+ `GET /api/v1/questions?knowledge_point_id=1`（筛出）
5. **pytest 测试库全绿** = 显式切测试库（**不污染 dev 库**）+ 既有测试 + 1a 新接口测试 全过
6. **git status + diff stat**（期望 4 文件改）：
   - 1 新 alembic 迁移 `0012_*.py`
   - 1 改 model `academic.py`（加 2 字段到 Question）
   - 1 改 router `routers/academic.py`（加 GET /textbooks + POST /chapters/{id}/knowledge-points + GET /questions 加参数）
   - 1 改 schema `schemas/academic.py`（加 TextbookSummary + KnowledgePointCreate + KnowledgePointDetail）
7. **0012 严格两列** = `git diff HEAD -- backend/alembic/versions/0012_*.py` 输出只有 `points` + `answer_text` 两行 `add_column`（**不夹带批次/学生/条码** —— 4 法核源列出实际字段名）

---

## §5 派工回执必带（不写 = 拒收）

- commit SHA
- CI run #（**实际跑过**；不接受"本地绿"）
- `alembic upgrade head` 输出（确认 0012 落）+ `alembic downgrade base && alembic upgrade head` 输出（确认 chain 干净）
- 0012 字段真值证据（SQLAlchemy `inspect()` 或 psql `\d questions` 输出）
- 3 接口 curl 输出（按 §4.4 顺序；每接口 status code + 响应体）
- pytest 测试库输出（**显式 -e DATABASE_URL**；全绿）
- `git diff HEAD -- backend/alembic/versions/0012_*.py` 输出（**只 points + answer_text 两列** = 4 法核源列出实际字段名）
- 报告命令用 4 法核源（**不写"我以为"或"已支持"**）

---

## §6 派工 subagent 行为模式（per MEMORY.md 2026-10-19 实证）

### 6.1 不要 git push（**必修**）
- `[origin-push]` 标记 = **等主 agent 批推**；subagent 自己 push = **越权**（实证：2026-10-19 B2 越权推 Gitee+GitHub；D2 越权推 Gitee）
- 派工回执必含**越权 push check**（`git log origin/master -1` vs `git log HEAD -1` 比对）
- **如果 subagent 跑完发现已 push** = 必报"我已 push = 越权"；主 agent 决定撤销 / 接受

### 6.2 pytest 必显式切测试库
- `pytest -q --override-ini="env=DATABASE_URL=postgresql+psycopg://postgres:postgres@<host>:5432/tiered_homework_test"` 或用 `scripts/init-test-db.sh` 之类（per §治理.19）
- **绝对不**在 dev 库 (`tiered_homework`) 跑 pytest（污染 dev 库）

### 6.3 4 法核源必跑 + 必报
- §3 的 10 项必须实际跑（grep / sed / wc 等）不写"应该"或"我以为"
- 跑 4 件真值数据 = grep 实际输出 + sed 取实际行号 + wc 算实际字节

### 6.4 失败必报 FAIL
- "FAIL <原因>" + 自查（哪步失败 + 为何 + 怎么修）
- 不推 pre-existing；不"我以为"

### 6.5 已知纪律
- §治理.19 / 修法 v6 / D-43-X / D-17（subagent 写代码；主聊天不写大段）

---

## §7 同步说明（不需要 subagent 做）

- **1b / 1c** = 题库列表页 + 新建/编辑抽屉 = **本 brief 不做**；1a 跑完 commit 后主 agent 再派
- **A2 0012 brief**（完整 A2 = 4 处改 = 章节→知识点 / 单份→批次 / 无分值→分值+答案 / 无识别码→条码）= **被星云 21:02 缩到 1a**（仅分值+答案两列 = 决策 8 partial；其他列 = 0013 推迟）
- **派工 subagent 行为模式 #1** = subagent 不准自己 push = 本 brief §6 显式写
- **基线 commit `a6e30a5`** 已被 B2 越权推双 remote（已发生事实；本 brief 不动 push 决策）

---

> **【2026-10-19 21:0x 变更说明 · plans/M3-1a-brief.md】**
>
> **修订**：新建（M3 题库层第 1 步 · 后端补齐）
> **基线**：HEAD = `a6e30a5`（B2 越权推后；CI run #124 绿）
> **派工日**：2026-10-19 21:0x（星云 21:02 拍）
> **内容**：§1 4 项任务（迁移 0012 严格两列 + 3 接口）/ §2 4 边界 / §3 10 项 4 法核源 / §4 必报项 / §5 派工回执必带 / §6 派工行为模式（**不推**） / §7 同步
> **法源依据**：
> - 规格《题库层设计 · 第 1 步（2026-10-19）》星云 21:02 拍
> - 交接书 §4 A1+1 §3（实施顺序：先 1a 后 1b/1c）
> - D-17（subagent 写代码；主聊天不写大段）
> - D-43-X（4 法核源 + 物理可达证据；拒收"我以为"）
> - §治理.19（pytest 显式切测试库）
> - MEMORY.md 2026-10-19 元教训（**派工 subagent 行为模式 #1 = 不准自己 push**；B2/D2 越权实证）
> **派工范围**：仅 backend（迁移 + model + routers + schemas）；frontend 完全不动；1b/1c 不做
> **来源**：规格文件（星云 21:02 拍）+ 核源 exec 输出（alembic 0011 + Question model + KP/chapter/question_knowledge_points 已存在）
