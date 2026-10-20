# 题库层第 1 步 · 1a-2 brief — 题组模型（题组表 + 块表 + 图片表改造 + 题组 CRUD）

> **来源**：星云 2026-10-20 12:15「D1-D4 全按星轨的 (a)」+ 08:14《需求评价 · 地理题库（含题组）》§三/§五 + 08:31《材料结构方案 · 块模型》§三/§六
> **执行**：载曜（主 agent 自己改，不派 subagent —— 本笔含迁移，回滚定位要靠自己）
> **前置**：`88a0a74`（P0/P2/P3 修复，CI #126 绿）、`f517428`（P1 字段防御 + ErrorBoundary，CI #127 绿）
> **本笔 = 本轮最大的一次迁移**（星轨 08:31 §六原话），模型定型后前端才能画题组折叠与块编辑器

---

## 0. 已核源的事实（主 agent 实测，别再猜）

1. **全仓零命中**（`backend/app` + `backend/alembic` + `backend/tests` + `frontend/src` 全扫）：
   `question_group` / `QuestionGroup` / `group_id` / `group_order` / `content_blocks` / `group_knowledge_points` / `parent_id` —— **各 0 处**。
   ⇒ 题组是全新模型，没有任何可复用的半成品，也不存在"已有 group_id 但没人用"的脏状态。

2. **现有迁移到 `0012`**（`backend/alembic/versions/` 共 12 个）。
   `0012_questions_points_and_answer.py` = `questions` 加 `points` + `answer_text` **两列**。
   ⇒ 本笔新迁移号 = **`0013`**，编号不要跳。

3. **`Question` 模型现状**（`backend/app/models/academic.py:755-830`）：
   `id` / `owner_user_id` FK→`users.id` RESTRICT / `chapter_id` FK→`chapters.id` CASCADE / `content` Text /
   `difficulty` SAEnum `question_difficulty_enum` / `type` SAEnum `question_type_enum` /
   `points` Numeric(5,1) default 2.0 / `answer_text` Text NULL /
   关系 `knowledge_points`(M2M) `choices` `images`。
   ⇒ **无 group_id / group_order**，本笔加这两列。

4. **`QuestionImage` 现状**（`academic.py:981-1030`）：
   `id` / `question_id` FK→`questions.id` **CASCADE NOT NULL** `index` / `order_index` /
   `file_ext` String(8) / `storage_path` String(512) / `source` SAEnum `question_image_source_enum` /
   `desensitization_status` / `desensitized_at` / `uploaded_at` / `uploaded_by_user_id`。
   ⇒ 本笔：`question_id` **改可空** + 加 `group_id` + 加 CHECK 防孤儿图。

5. **`question_knowledge_points` 关联表**（`academic.py:737-752`）：
   复合主键 `(question_id, knowledge_point_id)`，两侧 `ondelete="CASCADE"`。
   ⇒ `group_knowledge_points` **照抄这个结构**（只把 `question_id` 换成 `group_id`），不要另发明。

6. **`knowledge_points` 表名** = `knowledge_points`（`academic.py:460`）。

7. **块模型的 JSON 坑**（08:31 §三.4，**必须照做**）：
   测试用 SQLite，**直接写 `JSONB` 会让 SQLite 建表崩（本地红、CI 绿）**。
   必须 `JSON().with_variant(JSONB, "postgresql")` —— PG 走 JSONB，SQLite 走 JSON。

8. **`question_groups` 不复用 `questions` 自引用**（星轨 08:14 §三）：
   材料不是题 —— 没有题型、没有答案、不该进"题目列表 / 题量统计"。自引用会让每处查询都得记得排除"假题"，迟早漏。

---

## 1. 范围 = 2 个 commit（迁移在前，API 在后）

### 1a-2-1 · commit A — 迁移 `0013` + 模型

**新表 1：`question_groups`**

| 列 | 类型 | 约束 | 依据 |
|---|---|---|---|
| `id` | Integer | PK autoincrement | |
| `owner_user_id` | Integer | FK→`users.id` RESTRICT NOT NULL index | 与 `Question.owner_user_id` 同款（D-29 题库属教师个人资产） |
| `chapter_id` | Integer | FK→`chapters.id` CASCADE NOT NULL index | 与 `Question.chapter_id` 同款 |
| `difficulty` | SAEnum `question_difficulty_enum` | NOT NULL | **D2(a)：难度挂整组**，小题继承 |
| `created_at` / `updated_at` | DateTime(tz) | server_default now() | |

**明确不建的列**（写下来免得实现时"顺手加"）：
- ❌ `title` —— 星轨 08:14 §三 模型方案未列；材料在块里，列表页显示「题组（N 小题）」+ 首块摘要即可。**加列 = 改表结构，成本翻倍。**
- ❌ `type` —— 星轨默认：「题组内**允许混合题型**，题组本身不设题型」。
- ❌ `points` —— 星轨默认：「分值**按小题各自设**，题组总分 = 小题之和，材料不计分」。
- ❌ `content` —— **材料统一走 `content_blocks` 块序列**（08:31 块模型取代 08:14 的「材料正文 Text」方案）。留 `content` 会造成双源真相。

**新表 2：`group_knowledge_points`**
照抄 `question_knowledge_points`（`academic.py:737-752`）结构：复合主键 `(group_id, knowledge_point_id)`，两侧 CASCADE。
依据：星轨默认「知识点**挂题组上**（整组共享）；单题仍挂自己的；抽题时取并集」。

**新表 3：`content_blocks`**（材料块序列）

| 列 | 类型 | 约束 |
|---|---|---|
| `id` | Integer | PK autoincrement |
| `owner_type` | SAEnum `('group','question')` | NOT NULL —— MVP 只用 `group`；`question` **预留**（题干将来也能图文混排，现在不做 UI，但表结构不用再改） |
| `owner_id` | Integer | NOT NULL（多态，不建 FK） |
| `order_index` | Integer | NOT NULL（0 起） |
| `block_type` | SAEnum `('text','image','table')` | NOT NULL |
| `text_content` | Text | NULL（`text` 块用） |
| `image_id` | Integer | FK→`question_images.id` CASCADE NULL（`image` 块用，**只引用不存文件**） |
| `table_json` | `JSON().with_variant(JSONB,'postgresql')` | NULL（`table` 块用：`{"header":true,"rows":[["",""],["",""]]}`） |
| `created_at`/`updated_at` | DateTime(tz) | server_default now() |

- `UNIQUE(owner_type, owner_id, order_index)`
- **CHECK 按 block_type 验字段**：`'text'` ⇒ `text_content` NOT NULL 且另两个 IS NULL；`'image'` ⇒ `image_id` NOT NULL 且另两个 IS NULL；`'table'` ⇒ `table_json` NOT NULL 且另两个 IS NULL。

**改表 4：`questions` 加两列**
- `group_id` Integer FK→`question_groups.id` CASCADE **NULL** index —— NULL = 单题（现有题全部保持 NULL ⇒ 行为零变化）
- `group_order` Integer **NULL** —— 题组内题序（0 起）

**改表 5：`question_images` 约束改造**
- `question_id` **NOT NULL → NULL**
- 新增 `group_id` Integer FK→`question_groups.id` CASCADE NULL index
- **CHECK `(question_id IS NOT NULL OR group_id IS NOT NULL)`** —— 防孤儿图
  依据 **D4(a)**：材料图挂题组（`group_id` 有值、`question_id` 为 NULL），小题图挂小题（`question_id` 有值）。两张入口、同一张表、一个渲染路径。
- 迁移只动约束、**不改数据**（现有行都有 `question_id`，CHECK 天然满足）。

**迁移硬约束**
- `0013` 严格只做上面 5 件事，**不夹带**任何其它列
- `down_revision = "0012_questions_points_and_answer"`
- `downgrade` 必须能完整回退（`downgrade -1` 一次退到底）
- 迁移文件放 `backend/alembic/versions/0013_question_groups_and_content_blocks.py`

### 1a-2-2 · commit B — 题组 CRUD API

**6 个端点**（全部挂 `academic` router，前缀 `/api/v1/academic`）：

| 方法 | 路径 | 作用 | 要点 |
|---|---|---|---|
| POST | `/question-groups` | 建题组 | body：`chapter_id` + `difficulty`；建空组（材料/小题后挂） |
| GET | `/question-groups` | 列题组 | 可选 `chapter_id` / `knowledge_point_id`；返回含 `small_question_count`、`total_points` |
| GET | `/question-groups/{id}` | 详情 | 返回 `blocks[]`（按 order_index）+ 小题列表（按 group_order） |
| PUT | `/question-groups/{id}` | 改题组 | 改 `difficulty`；`blocks` 整体替换（材料是序列，替换比增量安全） |
| DELETE | `/question-groups/{id}` | 删题组 | **级联**：材料块 + 小题 + 组图一起消失 |
| POST | `/question-groups/{id}/questions` | 挂小题 | body：`question_id` + `group_order`；校验小题归属当前 user 且未被别的组占用 |

**归属校验**（与 `Question` 同款，别自创）
- 跨用户隔离走 **D-29 单门**：`chapter → owner_user_id` 链
- 建组 / 挂小题时，校验目标 `chapter` 归属当前 `X-User-Id`，否则 **404**（不泄露存在性）
- 挂小题时，若该题已属于别的组 ⇒ **409**

**响应字段（新增）**
```
QuestionGroupRead:  id / owner_user_id / chapter_id / difficulty
                    small_question_count: int   （小题数）
                    total_points: float         （= 小题 points 求和，不含材料）
                    created_at / updated_at
QuestionGroupDetail: QuestionGroupRead + blocks: list[ContentBlockRead]
ContentBlockRead:    id / block_type / order_index / text_content / image_id / table_json
```

**行为契约**（与 D1-D4 对齐，API 层就要保证，别留给下游）
- **D1(a)** 题组 = 材料 + 全部小题 ⇒ 详情一次返回两者；抽题引擎按组取
- **D2(a)** 难度只存组上 ⇒ 小题**不单独存组难度**（小题自己的 `difficulty` 列保留原值不动，但**组内继承以组为准**）
- **D3(a)** 题量按**小题数**累加 ⇒ `small_question_count` 就是计数口径
- **D4(a)** 材料图挂组、小题图挂小题 ⇒ `question_images` 两入口

**不动**
- **不改** `GET /questions` 的参数与语义（`knowledge_point_id` / `knowledge_point_ids` / `keyword` 等 1b 已有的一律不动）
- **不改** `QuestionRead` 现有字段
- **不改** 现有题目的 `group_id`（全部 NULL）
- **前端零改动**（本笔不含任何 `frontend/` 改动）

---

## 2. 1a-2 明确不做

1. ❌ **前端任何改动** —— 列表页「题组（N 小题）」折叠展示属 **1b 增量**；块编辑器属 **1c-2**。本笔只出模型 + API。
2. ❌ 抽题 / 组卷 / PDF / 评分（星轨 08:14 §四：第 2 步 / 第 4 步）
3. ❌ 表格**合并单元格**（见 §7 待确认，默认 (a) 不支持）
4. ❌ 单元格合并 / 公式 / 分栏 / 音频 / 富文本样式（文字块纯文本）
5. ❌ 题干块化 UI（`owner_type='question'` 只留表结构口子，不做 UI、不做接口）
6. ❌ 图片宽度三档的 UI（块编辑器在 1c-2）
7. ❌ `question_groups.title` / `type` / `points` / `content` 列（理由见 §1）
8. ❌ 拖拽排序（题组内用 `group_order` 数字，块顺序用上下移按钮，都在 1c-2）
9. ❌ 题目/题组版本历史（星轨 §七）
10. ❌ 改 `0012` 或更早任何迁移

---

## 3. 验收判据（DoD —— 全部要有真输出，不接受"应该可以"）

1. `alembic upgrade head` 建出 `question_groups` / `group_knowledge_points` / `content_blocks` 三张新表 + `questions` 加 2 列 + `question_images` 改约束；
   `alembic downgrade -1` 能完整回退到 `0012`（**升级/降级都要跑一次**）。
2. 建题组（chapter + 难度）⇒ **201**，返回 `id`。
3. 组挂 3 个知识点 ⇒ `GET /question-groups?knowledge_point_id=<其中一个>` **能筛出该组**。
4. 组挂 3 道小题（分值 3/5/2）⇒ 详情 `small_question_count = 3`、**`total_points = 10.0`**。
5. 材料 = `[text, image, table]` 三块混排 ⇒ 存入后读回**顺序正确**（`order_index` 0/1/2），`block_type` 各自正确。
6. 材料图挂组 ⇒ `question_images` 该行 `group_id` 有值、`question_id` **为 NULL**；
   孤儿图（两者都 NULL）⇒ **CHECK 拒绝**（插入报错）。
7. **删题组 ⇒ 级联**：材料块 + 3 道小题 + 组图一起消失（逐张表查残留 = 0）。
8. **现有单题行为零变化**：`GET /questions` 的 `total` 与本笔之前一致；`points` / `answer_text` 正常；`knowledge_point_ids` / `knowledge_point_ids[]` 筛选仍正常。
9. 现有题目 `group_id` 全为 NULL（`SELECT count(*) FROM questions WHERE group_id IS NOT NULL` = 0）。

---

## 4. 必报项（缺一项 = 回执不完整）

1. commit SHA × 2（1a-2-1 迁移 / 1a-2-2 API）+ 各自 commit message 全文
2. 各自 `git show --stat`
3. **pytest 输出**：新测试文件 + **全量** `pytest tests -q`（显式 test 库，见 §5.2）
4. **迁移文件全文**（`git show` 里的 0013 完整内容）
5. **模型真值**：`grep -n "class QuestionGroup\|class ContentBlock\|group_knowledge_points = Table\|group_id\|group_order" backend/app/models/academic.py`
6. **迁移未夹带**：`git diff HEAD~2 --name-only -- backend/alembic` 只含 `0013_*.py` 一个文件
7. **alembic 双向**：`upgrade head` 与 `downgrade -1` 的完整输出
8. **4 法核源**：`git rev-parse --show-toplevel` / `--absolute-git-dir` / `HEAD` / `git remote -v` / `git status --porcelain`
9. **未推送确认**：`git log origin/master -1 --format=%h` 与 `git log github/master -1 --format=%h` 仍为推送前的 SHA
10. **前端口径**：本笔**未改任何前端文件**（`git diff HEAD~2 --name-only -- frontend` 输出为空），并贴 `npm run lint` / `npx tsc -b --noEmit` / `npm run build` 三条通过（证明没碰坏前端）
11. **已知 pre-existing 照实报**：`app/services/question_generator.py:217,266` 的 mypy `[index]` 错误是**跨环境假红**（容器 py3.11 + mypy 2.4.0 = `Success: no issues found in 40 source files`），**不要去改它**。

---

## 5. 环境硬约束（血泪，务必照做）

### 5.1 backend 无 bind-mount ⇒ 改完代码必须先同步再跑测试

```bash
# A) 重建镜像（最干净，但慢 ~3-5 min）
docker compose build backend && docker compose up -d backend

# B) 直接同步改动文件进容器（快）
docker compose exec -T backend sh -c "rm -rf /app/app/app"
docker compose cp backend/app/. backend:/app/app      # ← 必须带 /. ！
docker compose exec -T backend sh -c "find /app/app -name '__pycache__' -type d -exec rm -rf {} +"
docker compose restart backend
```
- **`docker compose cp backend/app backend:/app/app` 会嵌套成 `/app/app/app`** ⇒ 跑旧代码 ⇒ **假绿**。必须写 `backend/app/.`。
- 迁移文件也要同步：`docker compose cp backend/alembic/. backend:/app/alembic`

### 5.2 test 库跑法（每轮 pytest 前必做 2 条）

```bash
docker compose exec -T postgres psql -q -U postgres -d tiered_homework_test \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker compose exec -T -e DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/tiered_homework_test \
  backend alembic upgrade head
```
- **只 `DROP TABLE alembic_version` 不够**（PG 上 conftest 的 `drop_all` 不删 PG enum 类型，二轮 upgrade 会撞 `type already exists`）⇒ 必须整 schema 重建。
- **显式指定 `tiered_homework_test`**，不得污染 dev 库 `tiered_homework`。

### 5.3 断言错误体用 `body["message"]`
全局 handler 把 `detail` 改写成 `message`（见 1b brief §5.3）。写测试断言 404/409/422 时用 `body["message"]`。

### 5.4 CI 等价数字参考
`docker build --target builder` 会跑 `ruff check . && mypy app && python -m pytest -q`（CI 等价 gate）。
本笔前基线：**349 passed, 16 skipped**（`88a0a74` 之后 + P1 那笔前的 builder 跑数）。本笔新增测试后 passed 数应 = 349 + 新增 case 数。

---

## 6. 失败处理

- 迁移 upgrade 失败 ⇒ **不要手工改库**，改迁移文件后 `downgrade -1` 回退再 `upgrade head`。
- 迁移 upgrade 成功但 downgrade 失败 ⇒ 报出来，**不要用 `DROP TABLE` 糊过去**（那样 `alembic_version` 与实际 schema 会不一致）。
- 测试红 ⇒ 先分清是**本笔引入**还是**pre-existing**（对照 §5.4 基线数字），只修本笔引入的。
- 任何拿不准的**产品语义**（不是实现细节）⇒ **停下来问星云**，不要自行拍板。

---

## 7. 待你确认 1 件（不阻塞开工，按建议默认走）

**表格是否支持合并单元格？**（来自 08:31《材料结构方案》§七）

- **(a) 不支持** ← **星轨建议，本 brief 默认按这个走**
  7 行 × 4 列以内的纯文本表格，够地理材料用；PDF 渲染不用自己算跨行跨列。
- (b) 支持：编辑器复杂度 ×2，PDF 渲染要自己算 colspan/rowspan。

**你批这份 brief 时如果没另说，就按 (a) 执行。**

另：D1-D4 你已拍「全按 (a)」，本 brief 已全部按 (a) 落进 §1 的表结构与 §1 的行为契约 —— 不再重复问。
