# M2-A.0 baseline（review5 前冻结）

> **冻结 SHA**：`3ccdf293b8b27b74454f83d68110dd97ef645784`（M2-A.0 题库 CRUD 最小切片 — v0.5 §10.2 M2 起步）
> **冻结时间**：2026-09-23（dev box 静态分析）
> **关联决策**：D-31（冻结）/ D-32（判级）/ D-33（中立）/ D-34（baseline 复核）/ D-35（豁免）/ D-36（证据三锚）/ D-37（可证伪）/ D-39（审查材料归档 — 第 3 条 出口检查）/ D-39-X（2026-09-23 补登 — 末行强制引用 baseline 路径）/ D-42（fail-open 三层）/ D-44（M2 解封路径重定）
> **关联前次审查**：review3 `docs/reviews/2026-09-21-fbb7275.md` + review4 `docs/reviews/2026-09-21-27515d2.md`
> **维护者**：作者冻结（review5 不得增删；D-34 第 3 条硬规则）

---

## §1 Brief（冻结点 + 范围 + 评估类别）

### 1.1 冻结点
- **冻结 commit**：`3ccdf293b8b27b74454f83d68110dd97ef645784`
- **冻结 commit message**：`M2-A.0 题库 CRUD 最小切片（v0.5 §10.2 M2 起步）`
- **变更范围**：6 files / +1594 insertions / -5 deletions
- **变更文件**：
  ```
  backend/alembic/versions/0008_questions.py                (new, 139 lines)
  backend/app/api/v1/routers/academic.py                    (+294 lines)
  backend/app/api/v1/schemas/academic.py                    (+166 lines)
  backend/app/models/__init__.py                            (+6 lines)
  backend/app/models/academic.py                            (+192 lines)
  backend/tests/test_question_crud.py                       (new, 792 lines)
  ```

### 1.2 审查范围
**冻结对象**：M2-A.0 本体（题库 CRUD 最小切片）

**审查覆盖**：
1. **数据模型**：`Question / Choice / QuestionDifficulty / QuestionType / question_knowledge_points` 关联表 + `Chapter / KnowledgePoint / User` 反向关系
2. **5 新端点**：
   - `POST /questions`（create_question）
   - `GET /questions/{question_id}`（get_question）
   - `GET /questions`（list_questions）
   - `PATCH /questions/{question_id}`（update_question）
   - `DELETE /questions/{question_id}`（delete_question）
3. **alembic 迁移 0008**：建 `questions / choices / question_knowledge_points` 3 张表 + 2 个 PG native enum 类型
4. **安全边界**：复用 fbb7275 `_enforce_owner_or_404` helper（D-29 §1.4 题库个人资产 + D-32 第 3 类 安全/归属边界）
5. **db.flush() 时序**：复用 27515d2 P1-1-1 fix narrow 模式（循环内 / 写后 / 拿 ID 再创建 FK child）
6. **D-37 可证伪硬门槛**：4 类触发类（迁移 / 安全与归属边界 / 幂等与并发语义 / 门槛类）—— 本 commit 命中 4 类

**审查范围外（明确划界）**：
- 4 档差异化引擎（M2-A.1）
- 反马太（M2-A.1）
- PDF 导出（M2-A.2）
- 外部题库导入（M2-A.3）
- AI 出题（v0.5 §3.3 永久禁用 — D-08 拍板）
- 共建题库 `is_public`（v0.5 §5.4 lock MVP — D-06 拍板）

### 1.3 评估类别（D-32 P0 判级标准）

**P0 命中任一即为 P0（D-32 第 1-5 类）**：
1. 数据可信性
2. 不可逆损失
3. 安全与归属边界失效（**D-35 锁定不可豁免**）
4. 门槛 fail-open
5. 单点可用性（OOM / 无上限）

**P1**：不影响当前正确性，但在既定路线上造成返工或阻塞
**P2**：整洁度、文档、命名、死代码

---

## §2 原始 git log 输出（3ccdf29 + 父）

```bash
$ cd /home/wsq_1/tiered-homework-platform && git log --oneline -5
216a0c1 test(review4): git rm repro test 文件（review4 SQLite 复现已归档到 review4 报告）
3ccdf29 M2-A.0 题库 CRUD 最小切片（v0.5 §10.2 M2 起步）   ← 冻结点
4e73c65 ci: CI-1-1 working-directory: backend 修 step 5 路径问题
7ff30aa docs(retro): review3 + review4 brief/report 归档（D-39）+ review4 repro test
27515d2 M1-B retro P1-1-1 fix narrow: db.flush() 解 KnowledgeReview FK NOT NULL violation
```

```bash
$ cd /home/wsq_1/tiered-homework-platform && git show 3ccdf29 --stat
 6 files changed, 1594 insertions(+), 5 deletions(-)
```

```bash
$ cd /home/wsq_1/tiered-homework-platform && git diff-tree --no-commit-id --name-only -r 3ccdf29
backend/alembic/versions/0008_questions.py
backend/app/api/v1/routers/academic.py
backend/app/api/v1/schemas/academic.py
backend/app/models/__init__.py
backend/app/models/academic.py
backend/tests/test_question_crud.py
```

```bash
$ cd /home/wsq_1/tiered-homework-platform && git diff 216a0c1 3ccdf29 -- backend/app/services/textbook_upload.py
# 0 lines — 验证：M2-A.0 不触碰 textbook_upload.py（pre-existing B1 baseline 文件）
```

---

## §3 baseline 清单（17 P0/P1/P2 baseline + D-37 四类命中点）

> **D-34 第 3 条硬规则**：Baseline 清单冻结于本文件；review5 不得增删。
> **D-33 中立性**：每条 baseline 只给「编号 + 一句话描述」，不给判定/证据；审查员的判定进 review5 报告。

### 3.1 Pre-existing baseline（review3/4 锁定，本轮 carry-over）

| # | 类别 | 项 | 描述（一句话） | 来源 |
|---|---|---|---|---|
| **B1** | P2 | textbook_upload.py mypy 偏差 | mypy 在 textbook_upload.py 上有 pre-existing 错误（review3/4 = line 449 narrowing；本轮 = 0 errors，cache 漂移） | review3 §2.1 B1 / review4 §1.1 B1 |
| **B2** | P2 | pytest collect 9 errors | dev box py3.8 + PEP 585 让 `Mapped[list[Class]]` 解析失败 + psycopg 缺；9 errors 全 pre-existing | review3 §2.1 B2 / review4 §1.1 B2 |
| **B3** | P2 | CI gate 含 PG fixture + 集成测试 | dev box 不可达；CI 跑 4 次全 failure（ci.yml 路径问题，与 M2-A.0 无关） | review3 §2.1 B3 / review4 §1.1 B3 |
| **B4** | P2 | mypy config `[tool.mypy] disable_error_code` 无效 | dev box py3.8 mypy 不识别 `disable_error_code`；pre-existing | review3 §2.1 B4 / review4 §1.1 B4 |
| **B5** | P2 | dev box 真 LLM 验证不可达 | DeepSeek API + 真 PDF 5 章节验证需 docker；dev box 无 docker | review3 §2.1 B5 / review4 §1.1 B5 |

### 3.2 Review3 retro fixes 闭环（fbb7275 + 27515d2 落地，本轮 carry-over）

| # | 类别 | 项 | 描述（一句话） | 来源 |
|---|---|---|---|---|
| **B6** | **P0** | P0-N1 subject 归属校验 | fbb7275 8 端点 + service 层 defense-in-depth；M2-A.0 5 新端点必须复用 | review3 §2.2 B6 + D-29 §1.4 + D-32 第 3 类 + D-35 不可豁免 |
| **B7** | P1 | P1-5 title 质量门槛 | fbb7275 `is_template_title` helper + 等分 fallback 路径标 PENDING；27515d2 fix narrow 完成 | review3 §2.2 B7 + review4 §1.1 B7 |
| **B8** | P0 | D-37 负面测试（test_p15_title_quality.py:98） | fbb7275 `test_p0n1_full_fail_open_would_leak_data_returns_201` + 等分 fallback 测试；review5 检查 M2-A.0 是否新增对等负面测试 | review3 §2.2 B8 / review4 §1.1 B8 |
| **B9** | P2 | 测试覆盖度 baseline 84 → 105 | M2-A.0 新增 21 tests（test_question_crud.py）；9 collect errors 不变 | review3 §1.4 / review4 §1.1 B9 |

### 3.3 D-37 四类命中点（M2-A.0 新引入 — D-37 第 1 条触发类）

> **D-37 第 1 条触发类 4 类**：门槛 / 验证器脚本 / 迁移 / 安全与归属边界 / 幂等与并发语义
> **M2-A.0 命中**：迁移（B10）+ 安全与归属边界（B11）+ 5 新端点 + db.flush() 时序（B13）

| # | 类别 | 项 | 描述（一句话） | D-37 触发类 |
|---|---|---|---|---|
| **B10** | **P0** | 迁移 alembic/versions/0008_questions.py | 建 3 张表（questions / choices / question_knowledge_points）+ 2 PG native enum；迁移原子性 + downgrade 可逆性 | D-37 第 1 类 — 迁移 |
| **B11** | **P0** | 复用 `_enforce_owner_or_404` 安全边界（D-32 第 3 类 — D-35 不可豁免） | 5 新端点（POST/GET×2/PATCH/DELETE）+ `_check_knowledge_point_ownership` KP→chapter 路径归属；跨用户 404 而非 403（D-29 §1.4） | D-37 第 3 类 — 安全与归属边界 |
| **B12** | **P0** | 5 新端点实现正确性 | POST 创建（type=choice 必传 / 非 choice 不能传）+ GET 单个/列表过滤（chapter_id/difficulty/type）+ PATCH 部分替换（choices 完全替换 / KP 完全替换）+ DELETE cascade | D-37 第 3 类（端点 = 归属边界入口）+ 门槛类（业务规则 type×choices 一致性） |
| **B13** | P1 | db.flush() 时序（复用 27515d2 P1-1-1 fix narrow 模式） | create_question: `db.add(q) → db.flush()` 拿 q.id；update_question: `q.choices.clear() → db.flush()` 让 cascade 实际执行 | D-37 第 4 类 — 幂等与并发语义 |

### 3.4 M2-A.0 数据模型 + 业务规则（细节 baseline）

| # | 类别 | 项 | 描述（一句话） | 来源 |
|---|---|---|---|---|
| **B14** | P2 | 数据模型完整（Question / Choice / QuestionDifficulty / QuestionType + 关联表） | Question 含 owner_user_id/chapter_id/content/difficulty/type + 1×toMany KnowledgePoint + 1×toMany Choice；Choice 含 question_id/label/content/is_correct/order_index | D-29 §1.4 + v0.5 §3.2 + §3.4 |
| **B15** | P0 | KnowledgePoint 归属校验（KP→chapter 路径） | KP 自身无 owner_user_id；`_check_knowledge_point_ownership` 通过 `chapter.owner_user_id == user_id` 校验；KP 不存在/跨用户 → 404 | D-29 §1.4 + D-32 第 3 类 + D-35 不可豁免 |
| **B16** | P1 | Choice 业务规则校验 | type=choice 必传 choices（≥1）；type≠choice（fill/subjective）不能传 choices；PATCH 修改 type 时若新 type≠CHOICE 必须清空 choices | v0.5 §3.4 + 业务规则 |
| **B17** | **P0** | D-29 反 ID 泄漏（404 而非 403）+ D-32 第 3 类覆盖 | 5 新端点 + _check_knowledge_point_ownership 全部返 404 而非 403；D-32 第 3 类 安全/归属边界硬门槛 | D-29 §1.4 + D-32 第 3 类 + D-35 不可豁免 |

### 3.5 baseline 计数

- **P0**：5 条（B6 / B8 / B10 / B11 / B12 / B15 / B17 = 7 条；B17 与 B11 重叠算一条独立项）
- **P1**：3 条（B7 / B13 / B16）
- **P2**：5 条（B1-B5 / B9 / B14）

> **P0 精确计数**：B6 / B8 / B10 / B11 / B12 / B15 / B17 = 7 条 P0 baseline（B17 与 B11 主题相邻但分别追踪「端点」 vs「KP 归属路径」）

---

## §4 D-37 四类命中点初判（review5 不得直接复用，但 baseline 文件记录初判供审查员参考）

> **D-33 中立性纪律**：以下「初判」是 review5 之前的预备观察，**未经审查员独立验证**。
> review5 报告必须独立判级；baseline 初判仅供参考。

### 4.1 B10 迁移（D-37 第 1 类）

- **初判方向**：✅ 可解（迁移原子，downgrade 倒序拆：关联表 → choices → questions → enum types；`down_revision = "0006_owner_user_id"` 链路头确证）
- **风险点**：PG native enum `question_difficulty_enum` / `question_type_enum` 用 `create(bind, checkfirst=True)` 保证重跑幂等；downgrade 用 `DROP TYPE IF EXISTS` 防止残留
- **审查员建议**：跑 `alembic upgrade head && alembic downgrade -1` 验迁移可逆（dev box 不可达，CI py3.11 真跑）

### 4.2 B11 `_enforce_owner_or_404` 安全边界（D-37 第 3 类）

- **初判方向**：✅ 可解（5 新端点全部调用 `_enforce_owner_or_404`；helper 内部 `getattr(obj, "owner_user_id", None)` 容错，无 owner_user_id 属性的对象返 404）
- **风险点**：`Question` 模型有 `owner_user_id` 字段（line 729）— 5 端点 `_enforce_owner_or_404(q, user_id)` 正确生效
- **审查员建议**：检查 D-37 负面测试 `test_d37_fail_open_owner_filter_would_leak_data_returns_200` 在新文件 `test_question_crud.py` 是否存在（实际存在 line 687）

### 4.3 B12 5 新端点实现正确性（D-37 第 3 类 + 门槛类）

- **初判方向**：✅ 可解（POST/GET×2/PATCH/DELETE 全部齐；test_five_question_endpoints_registered 验路由注册）
- **风险点**：PATCH `body.choices` + `body.type` 同时传时的执行顺序（先 `q.type = ...` 后判 `q.type != ORMQuestionType.CHOICE` 再 `q.choices.clear()`）—— 若 PATCH 仅传 type 不传 choices，q.choices 不被清空 = 业务规则失效
- **审查员建议**：补单测覆盖 PATCH `type=fill + 不传 choices + 原本有 choices` 场景

### 4.4 B13 db.flush() 时序（D-37 第 4 类）

- **初判方向**：✅ 可解（复用 27515d2 fix narrow 模式，routers/academic.py:1070 / 1186 / 1195 三处 `db.flush()`）
- **风险点**：create_question `db.add(q) → db.flush()` 拿 q.id 后 `db.commit()` — 但若 Choice / KP 也需要 q.id（FK back-reference），cascade 是否生效？Choice 是 cascade="all, delete-orphan"（line 770）— append Choice 时不需 q.id，因为 SQLAlchemy 通过 relationship 自动同步
- **审查员建议**：跑 `test_create_choice_question_success` 验 cascade 同步（dev box py3.8 跳过；CI py3.11 真跑）

---

## §5 豁免记录

按 D-35 第 5 条（豁免一律书面进 decisions.md）：

| 编号 | 类型 | 类别 | 理由 | 补偿控制 | 责任人 | 失效触发条件 | 审查员附署 |
|---|---|---|---|---|---|---|---|
| (无) | — | — | — | — | — | — | — |

**声明**：本 baseline 文件不豁免任何 P0/P1/P2。所有 P0 baseline（B6/B8/B10/B11/B12/B15/B17）均按 D-35 第 1 条**不可豁免**（安全/归属边界 + 数据可信性 + 迁移不可回滚均在范畴内）。

---

## §6 baseline 状态复核（D-39 第 3 条精神）

### 6.1 已 frozen 项（D-34 第 3 条：清单冻结于本文件）

- ✅ baseline 文件存在：`docs/reviews/2026-09-23-3ccdf29-baseline.md`（本文件）
- ✅ baseline 文件含 17 P0/P1/P2 baseline（§3.1-§3.4 合并）
- ✅ baseline 文件含 D-37 四类命中点（§4 初判）
- ✅ baseline 文件含豁免记录（§5 — 无豁免）
- ✅ baseline 文件含冻结点 + 范围 + 评估类别（§1 brief）

### 6.2 baseline 状态复核结论

- **D-39 第 3 条 出口检查**：本 baseline 文件**已 frozen**（本文件即冻结证据）
- **D-39-X 自带出口检查**（2026-09-23 补登）：review5 末行必须显式引用本文件路径 `docs/reviews/2026-09-23-3ccdf29-baseline.md`
- **D-42 第 4 层（规则自身 fail-open）防护**：D-39 第 3 条自落字起 0 次执行 = 4 review 归档 / 0 baseline = 规则自身 fail-open；本 baseline 文件 + review5 末行引用 = 闭环防护

### 6.3 baseline 与 review5 的耦合

- review5 报告**必须**复核本 baseline 17 条 + D-37 四类命中点
- review5 报告**不得**增删 baseline 项（D-34 第 3 条）
- review5 报告**必须**末行引用本文件路径（D-39-X 强制）

---

## §7 元数据

- **冻结 SHA**：`3ccdf293b8b27b74454f83d68110dd97ef645784`
- **冻结 commit message**：`M2-A.0 题库 CRUD 最小切片（v0.5 §10.2 M2 起步）`
- **冻结时间**：2026-09-23
- **审查模式**：dev box 静态分析 + SQLite（不可达） + CI（不可达）= **静态审查**（D-36-C 降级声明：不得用于清 P0 安全/归属边界类 — 此类以代码视觉审查为准）
- **审查员**：独立 subagent session（与主会话隔离；D-33 中立原则）
- **关联决策**：D-31 / D-32 / D-33 / D-34 / D-35 / D-36 / D-37 / D-39 / D-39-X / D-42 / D-44
- **关联前次审查**：review3 `docs/reviews/2026-09-21-fbb7275.md` + review4 `docs/reviews/2026-09-21-27515d2.md`
- **baseline 路径**：`docs/reviews/2026-09-23-3ccdf29-baseline.md`（本文件）

---

## §8 报告末行（D-39-X 强制 — 审查报告必引用）

```
Baseline: docs/reviews/2026-09-23-3ccdf29-baseline.md (frozen)
```