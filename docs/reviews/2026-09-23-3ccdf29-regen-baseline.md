# M2-A.0 + 历史 review baseline 重生成（regen）

> **冻结 SHA**: `3ccdf293b8b27b74454f83d68110dd97ef645784` (M2-A.0 本体)
> **冻结时间**: 2026-09-23
> **目的**: 弥补 review2 baseline 永久缺一环（落在 WorkBuddy，从未进仓）
> **来源**: review3 (fbb7275) + review4 (27515d2) + review5 (3ccdf29) + review5 baseline (3ccdf29-baseline.md) + 9/20/21/22 memory 合并去重
> **关联决策**: D-31（冻结）/ D-32（判级）/ D-33（中立）/ D-34（baseline 复核）/ D-35（豁免）/ D-36（证据三锚）/ D-37（可证伪）/ D-39（审查材料归档 — 第 5 条 push 后禁止 amend）/ D-39-X（2026-09-23 补登 — 末行强制引用 baseline 路径）/ D-42（fail-open 三层）/ D-44（M2 解封路径重定）
> **关联前次审查**: review3 `docs/reviews/2026-09-21-fbb7275.md` + review4 `docs/reviews/2026-09-21-27515d2.md` + review5 `docs/reviews/2026-09-23-3ccdf29.md`
> **关联 baseline**: review5 baseline `docs/reviews/2026-09-23-3ccdf29-baseline.md`（review5 一次性 review 冻结 17 项）
> **维护者**: 作者冻结（不得 amend；D-39 第 5 条硬规则 — 本文件为该规则首次实战）
> **关联永久缺**: 第一轮 review2 baseline 在 WorkBuddy 工作区，从未进仓（收口决策书 §一 Q1 + §四）

---

## §1 Brief（冻结点 + 范围 + 评估类别）

- **冻结点**: M2-A.0 = `3ccdf293b8b27b74454f83d68110dd97ef645784`
- **范围**: 完整历史 baseline（review3/4/5 + review5 baseline + 9/20/21 memory 合并去重）
- **评估类别**: baseline 复核（弥补 review2 baseline 永久缺一环）

**regen 与 review5 baseline 的关系**：
- review5 baseline 范围 = review5 一次性 review（17 项 P0/P1/P2 + D-37 四类初判）
- 本 regen baseline 范围 = **完整历史 baseline**（≥ 17 项，含 review3/4/5 + memory）
- 互补关系：review5 baseline 不可替代本 regen baseline（review5 baseline 编号体系虽已 frozen，但仅覆盖 review5 一次性 review，缺少 review2/3/4 历史闭环轨迹 + 9/20/21 memory 决策记账路径）

---

## §2 原始证据

### §2.1 review3 (`docs/reviews/2026-09-21-fbb7275.md`) baseline 引用

- §1.4 pytest collect errors 数：review2 baseline (77095e6) = 78 collected, 9 errors；review3 actual (fbb7275) = 84 collected, 9 errors → **+6 tests**（test_p0n1_subject_ownership.py 2 + test_p15_title_quality.py 4）；9 errors 全 pre-existing
- §2.1 review2 baseline B1-B5 状态复核表（5 项 P2 carry-over）
- §2.2 review3 baseline 增量 B6-B9（4 项：P0-N1 / P1-5 / D-37 负面测试 / 测试覆盖度）
- §3 P1-1（新发现）：等分 fallback 路径 KnowledgeReview FK bug

### §2.2 review4 (`docs/reviews/2026-09-21-27515d2.md`) baseline 引用

- §1.1 review2/3 baseline B1-B9 状态复核表（review4 全部 carry-over 不动）
- §1.2 review4 baseline 增量 B10：P1-1-1 fix 引入 `db.flush()`（+6 行 / 1 文件）
- §6.3 闸门退出码：RUFF=0 / MYPY=0 / HELPER=0 / COLLECT=0
- §6.4 SQLite 复现输出：After flush / COMMIT OK（独立 SQLAlchemy 2.0 minimal）

### §2.3 review5 (`docs/reviews/2026-09-23-3ccdf29.md`) baseline 引用

- §0 报告头：冻结 SHA = `3ccdf293b8b27b74454f83d68110dd97ef645784`
- §1.3 mypy baseline 漂移观察（D-34 第 1 条状态复核）：review3/4 = line 449 narrowing；本轮 = 0 errors（cache 漂移，但 B1 baseline 项未关闭）
- §3 D-34 Baseline 状态复核（B1-B17）
- §4 P1-3（新发现）：PATCH `body.type` + 不传 `body.choices` + 原本有 choices 路径漏清空（academic.py:1177-1185 M2-A.0 introduce）— **不计入 baseline，列入 review5 新发现**

### §2.4 review5 baseline (`docs/reviews/2026-09-23-3ccdf29-baseline.md`) 引用

- §3.1 Pre-existing baseline B1-B5（review3/4 carry-over，本轮 carry-over）
- §3.2 Review3 retro fixes 闭环 B6-B9（fbb7275 + 27515d2 落地，本轮 carry-over）
- §3.3 D-37 四类命中点 B10-B13（M2-A.0 新引入）
- §3.4 M2-A.0 数据模型 + 业务规则 B14-B17
- §3.5 baseline 计数：P0 = 7 条（B6/B8/B10/B11/B12/B15/B17） / P1 = 3 条（B7/B13/B16） / P2 = 5+2 = 7 条（B1-B5/B9/B14）

### §2.5 9/20 memory (`memory/2026-09-20.md`) baseline 引用

- L34-42 "仍未闭环的 baseline（carry-over 至今晚）" 表格：
  - B1 `textbook_upload.py:407` mypy 错误（仍开，行号漂移） — **review2 baseline 永久缺一环的现场记录**
  - B2 dev box pytest collect errors（仍开 9 errors，py3.8 缺 psycopg）
  - B3 CI 闸门含 PG fixture（配置闭环 / 执行未跑）
  - B4 mypy config（已闭环，15f03a0）
  - B5 dev box 真 LLM + alembic（配置闭环 / 执行未跑）

### §2.6 9/21 memory (`memory/2026-09-21.md`) baseline 引用

- L12: P0-N1 + P1-5（subject 归属校验 + title 质量门槛 + D-37 负面测试，fbb7275） — = B6/B7
- L30: run #2 (3c21dd1) step 7 Mypy failed → B1 narrowing（review2 baseline 已 lock） — = B1
- L55-59: B1-1 cast fix (171aabe) — B1 narrowing 修复尝试（被回滚，仅作 B1 子项轨迹）
- L112: review3 冻结点 `fbb7275`
- L142: fbb7275 commit message "M1-B retro P0-N1 + P1-5"

### §2.7 9/22 memory

- **缺日**：无 `memory/2026-09-22.md` 文件
- 备注：9/22 工作内容散落在 handoff/ 与 docs/decisions.md，未单独留 memory 日志

### §2.8 9/23 memory (`memory/2026-09-23.md`) baseline 引用

- L65: `0194c4f docs(review): N-4 M2-A.0 baseline + review5（2026-09-23）`
- L72: N-4 subagent 的 review 工作（baseline + review5）
- L124: 同期未推送 commit `0194c4f`

---

## §3 合并去重 baseline 清单（17 项 — 沿用 review5 baseline frozen 编号体系）

> **合并去重原则**：
> - review5 baseline 的 B1-B17 编号已 frozen（§3.5 计数自洽）→ 本 regen baseline 沿用同套编号
> - review4 §1.2 B10（P1-1-1 fix db.flush()）在 review5 baseline §3.3 B13 里被重定义为「db.flush() 时序」 → 合并去重后 = review5 baseline B13（复用 27515d2 P1-1-1 fix narrow 模式）
> - 9/20 memory L34-42 B1-B5 / 9/21 memory L12 P0-N1 + P1-5 / 9/21 memory L30 B1 narrowing → 全部 merge 进 review5 baseline B1-B17
> - 9/22 memory 缺日（无文件）→ 不影响合并去重（review4 §1.1 已 carry-over B1-B9）
> - review5 §4 P1-3 新发现 → **不计入 baseline**（baseline 锁定 review5 frozen 文件 §3.3）

| # | 项（合并去重后的统一描述）| source（合并去重路径）| 类型 | D-37 触发类 |
|---|---|---|---|---|
| **B1** | `textbook_upload.py` mypy narrowing error（行号随 commit 漂移；review2 = 407 / review3 = 443 / review4 = 449 / review5 = 0 errors cache 漂移但项未关闭）| review2(永久缺)/9-20 memory L34/review3 §2.1 B1/review4 §1.1 B1/review5 baseline §3.1 B1 | P2 | — |
| **B2** | dev box pytest collect 9 errors（py3.8 + PEP 585 `Mapped[list[Class]]` 解析失败 + psycopg 缺；全 pre-existing 与 3ccdf29 无关）| review2(永久缺)/9-20 memory L34/review3 §2.1 B2/review4 §1.1 B2/review5 baseline §3.1 B2 | P2 | — |
| **B3** | CI 闸门含 PG fixture + 集成测试（dev box 不可达；CI 4-5 次 run 全 failure 根因为 ci.yml 路径问题，与 M2-A.0 内容无关）| review2(永久缺)/9-20 memory L34/review3 §2.1 B3/review4 §1.1 B3/review5 baseline §3.1 B3 | P2 | — |
| **B4** | mypy config `[tool.mypy] disable_error_code` 无效（dev box py3.8 mypy 不识别；已实修 15f03a0 但 dev box baseline 项本身未关闭）| review2(永久缺)/9-20 memory L34/review3 §2.1 B4/review4 §1.1 B4/review5 baseline §3.1 B4 | P2 | — |
| **B5** | dev box 真 LLM + alembic 验证不可达（DeepSeek API + 真 PDF 5 章节验证需 docker；dev box 无 docker）| review2(永久缺)/9-20 memory L34/review3 §2.1 B5/review4 §1.1 B5/review5 baseline §3.1 B5 | P2 | — |
| **B6** | P0-N1 subject 归属校验（fbb7275 8 端点 `_enforce_owner_or_404` helper + service 层 defense-in-depth；M2-A.0 5 新端点必须复用）| 9-21 memory L12/review3 §2.2 B6/review4 §1.1 B6/review5 baseline §3.2 B6 | **P0** | D-37 第 3 类 — 安全与归属边界（D-35 不可豁免）|
| **B7** | P1-5 title 质量门槛（fbb7275 `is_template_title` helper + 等分 fallback 路径标 PENDING；27515d2 fix narrow 完成 P1-1 FK bug）| 9-21 memory L12/review3 §2.2 B7/review4 §1.1 B7/review5 baseline §3.2 B7 | P1 | 门槛类 |
| **B8** | D-37 负面测试可证伪性（fbb7275 `test_p0n1_full_fail_open_would_leak_data_returns_201` + 27515d2 `test_p15_equal_split_placeholder_marks_review_pending`；review5 检查 M2-A.0 是否新增对等负面测试）| review3 §2.2 B8/review4 §1.1 B8/review5 baseline §3.2 B8 | **P0** | D-37 第 2 类 — 验证器脚本（硬门槛）|
| **B9** | 测试覆盖度 baseline（review2: 78 / review3: 78→84 / review4: 84 / review5: 84→105）| review3 §1.4/review4 §1.1 B9/review5 baseline §3.2 B9 | P2 | — |
| **B10** | 迁移 `alembic/versions/0008_questions.py`（建 3 张表 questions / choices / question_knowledge_points + 2 PG native enum；迁移原子性 + downgrade 可逆性）| review5 baseline §3.3 B10 | **P0** | D-37 第 1 类 — 迁移 |
| **B11** | 复用 `_enforce_owner_or_404` 安全边界（5 新端点 POST/GET×2/PATCH/DELETE + `_check_knowledge_point_ownership` KP→chapter 路径归属；跨用户 404 而非 403）| review5 baseline §3.3 B11 | **P0** | D-37 第 3 类 — 安全与归属边界（D-35 不可豁免）|
| **B12** | 5 新端点实现正确性（POST 创建 type=choice 必传 / 非 choice 不能传 + GET 单个/列表过滤 + PATCH 部分替换 choices 完全替换 + DELETE cascade）| review5 baseline §3.3 B12 | **P0** | D-37 第 3 类（端点=归属边界入口）+ 门槛类（业务规则 type×choices 一致性）|
| **B13** | db.flush() 时序（routers/academic.py:1070 / 1186 / 1195 三处 flush；复用 27515d2 P1-1-1 fix narrow 模式 = review4 §1.2 B10 合并去重）| review4 §1.2 B10（合并去重）/review5 baseline §3.3 B13 | P1 | D-37 第 4 类 — 幂等与并发语义 |
| **B14** | 数据模型完整（Question / Choice / QuestionDifficulty / QuestionType / question_knowledge_points 关联表；含 owner_user_id/chapter_id/content/difficulty/type + 1×toMany KnowledgePoint + 1×toMany Choice）| review5 baseline §3.4 B14 | P2 | — |
| **B15** | KnowledgePoint 归属校验（KP→chapter 路径，`_check_knowledge_point_ownership` 通过 `chapter.owner_user_id == user_id` 校验；KP 不存在/跨用户 → 404）| review5 baseline §3.4 B15 | **P0** | D-37 第 3 类 — 安全与归属边界（D-35 不可豁免）|
| **B16** | Choice 业务规则校验（type=choice 必传 choices ≥1；type≠choice fill/subjective 不能传 choices；PATCH 修改 type 时若新 type≠CHOICE 必须清空 choices）| review5 baseline §3.4 B16 | P1 | 门槛类 |
| **B17** | D-29 反 ID 泄漏（404 而非 403）+ D-32 第 3 类覆盖（5 新端点 + `_check_knowledge_point_ownership` 全部返 404 而非 403；D-32 第 3 类 安全/归属边界硬门槛）| review5 baseline §3.4 B17 | **P0** | D-32 第 3 类（D-35 不可豁免）|

### §3.1 baseline 计数汇总

- **总项数**：17 项（B1-B17）— **≥ 17 项门槛达成**
- **P0**：7 条（B6 / B8 / B10 / B11 / B12 / B15 / B17）— D-35 不可豁免
- **P1**：3 条（B7 / B13 / B16）
- **P2**：7 条（B1 / B2 / B3 / B4 / B5 / B9 / B14）

### §3.2 合并去重审计日志

| baseline 项 | review3 source | review4 source | review5 baseline source | review5 report source | memory source |
|---|---|---|---|---|---|
| B1 | §2.1 B1（部分修/不变）| §1.1 B1（不变）| §3.1 B1 | §1.3 mypy baseline 漂移观察（项未关闭）| 9-20 L34 / 9-21 L30 |
| B2 | §2.1 B2（不变）| §1.1 B2（不变）| §3.1 B2 | §1.4 pytest 20 skip 根因（pre-existing）| 9-20 L34 |
| B3 | §2.1 B3（不动）| §1.1 B3（不动）| §3.1 B3 | §1.3 CI 4 次 run evidence | 9-20 L34 |
| B4 | §2.1 B4（不动）| §1.1 B4（不动）| §3.1 B4 | — | 9-20 L34 |
| B5 | §2.1 B5（不动）| §1.1 B5（不动）| §3.1 B5 | — | 9-20 L34 |
| B6 | §2.2 B6 ✅ 修好 | §1.1 B6（不动）| §3.2 B6 | §2.2 复用点 | 9-21 L12 |
| B7 | §2.2 B7 ⚠️ 部分修（详见 P1-1）| §1.1 B7（不动）| §3.2 B7 | §2.3 db.flush() 时序 | 9-21 L12 |
| B8 | §2.2 B8 ✅ 修好 | §1.1 B8 ✅ 仍存在 | §3.2 B8 | — | — |
| B9 | §1.4 +6 tests | §1.1 B9（不变）| §3.2 B9 | — | — |
| B10 | — | — | §3.3 B10（迁移）| — | — |
| B11 | — | — | §3.3 B11 | §2.2 复用点 | — |
| B12 | — | — | §3.3 B12 | — | — |
| B13 | — | §1.2 B10 ✅ 不引入新 bug | §3.3 B13（db.flush() 时序，重定义）| §2.3 db.flush() 时序 | — |
| B14 | — | — | §3.4 B14 | — | — |
| B15 | — | — | §3.4 B15 | — | — |
| B16 | — | — | §3.4 B16 | §4 P1-3 新发现（PATCH 漏清空）| — |
| B17 | — | — | §3.4 B17 | — | — |

### §3.3 编号冲突说明

- **review4 §1.2 B10**（P1-1-1 fix 引入 `db.flush()`） 与 **review5 baseline §3.3 B10**（迁移 `0008_questions.py`）编号相同但主题不同
- **合并去重策略**：沿用 review5 baseline frozen 编号体系（B1-B17），review4 §1.2 B10 合并进 review5 baseline §3.3 B13「db.flush() 时序」（同一修复模式在 routers/academic.py:1070/1186/1195 三处复用）
- **理由**：review5 baseline 是 frozen baseline（§6.1 已 frozen），其编号体系自洽；保持 regen baseline 与 review5 baseline 编号一致便于后续审计

---

## §4 与 review5 baseline 关系（互补 / 不可替代）

### §4.1 范围对比

| 维度 | review5 baseline | 本 regen baseline |
|---|---|---|
| 范围 | review5 一次性 review（17 项 P0/P1/P2 + D-37 四类初判）| 完整历史 baseline（17 项 P0/P1/P2 + source 合并去重路径 + 9/20/21 memory 引用）|
| 覆盖 review2 | ❌（review5 仅 carry-over review3/4 baseline）| ✅（通过 9-20 memory L34-42 提取 review2 baseline 永久缺一环）|
| 覆盖 review3 | ⚠️（仅 carry-over 编号，不含 review3 §2.1/§2.2 状态复核）| ✅（含 review3 §2.1 B1-B5 + §2.2 B6-B9 全部状态）|
| 覆盖 review4 | ⚠️（仅 carry-over 编号，不含 review4 §1.2 B10 增量）| ✅（含 review4 §1.1 B1-B9 + §1.2 B10 增量；§1.2 B10 合并进 B13）|
| 覆盖 review5 report | ❌（仅 baseline 文件）| ✅（含 review5 §1.3 mypy 漂移 + §1.4 pytest 20 skip + §4 P1-3 新发现）|
| 覆盖 memory 决策记账 | ❌ | ✅（9/20 L34-42 + 9/21 L12/L30/L55-59/L112/L142 + 9/23 L65/L72/L124）|

### §4.2 互补关系

- **review5 baseline 不可替代本 regen baseline**：review5 baseline 范围太局部，仅覆盖 review5 一次性 review 的 frozen baseline 清单
- **本 regen baseline 不可替代 review5 baseline**：本 regen baseline 沿用 review5 baseline 编号体系，但 regen 是「历史合并去重视图」，review5 baseline 是「frozen baseline 文件」（D-34 第 3 条冻结）
- **二者并存关系**：review5 baseline = frozen baseline 本体；本 regen baseline = 历史 baseline 合并去重审计视图

### §4.3 永久缺一环的弥补

- **review2 baseline**（落在 WorkBuddy 工作区，从未进仓）= 永久缺一环
- **弥补路径**：9/20 memory L34-42 是 review2 baseline 的唯一现场记录（含 B1-B5 描述 + 状态 + 行号）
- **本 regen baseline** 通过 §2.5 引用 9/20 memory 表格 + §3 baseline 清单 B1-B5 source 列「review2(永久缺)」标注，永久缺一环已被记录在仓

---

## §5 元规则

### §5.1 regen baseline 维护规则

- 本 baseline 由 B2 subagent 重生成，**未经独立审查员签字**（B2 是 subagent 接力任务，无独立审查）
- 后续每个 milestone 启动前，baseline 必须经独立审查员签字（D-33 中立性 + D-34 baseline 复核硬规则）
- D-39 第 5 条归档 commit freeze 规则适用本文件（**push 后禁止 amend — 本次首次实战**）

### §5.2 末行自引用（D-39-X 自带出口检查）

本 baseline 末行 = 自引用本文件路径 `docs/reviews/2026-09-23-3ccdf29-regen-baseline.md`

### §5.3 与 review5 baseline frozen 体系的关系

- review5 baseline 文件 `docs/reviews/2026-09-23-3ccdf29-baseline.md` 仍为 frozen baseline 本体（D-34 第 3 条）
- 本 regen baseline 不修改 review5 baseline 内容（仅在 §3 source 列引用）
- review5 baseline §3 末行自引用 = `Baseline: docs/reviews/2026-09-23-3ccdf29-baseline.md (frozen)`
- 本 regen baseline §3 末行自引用 = `Baseline: docs/reviews/2026-09-23-3ccdf29-regen-baseline.md (frozen)`

### §5.4 D-39 第 5 条首次实战

- 本 regen baseline = D-39 第 5 条「push 后禁止 amend」首次实战
- 一旦本文件 push 到 origin + github，**任何 amend 必须派新 subagent 写新文件 + 新 commit**（D-39 第 5 条硬规则）
- 失败时汇报：参考 D-42 第 7 条 + D-43 第 6 条精神（不循环 verify 同一事实；3 次同样失败 = 失败模式，停下来报告）

---

## §6 元数据

- **冻结 SHA**：M2-A.0 = `3ccdf293b8b27b74454f83d68110dd97ef645784`
- **冻结时间**：2026-09-23
- **合并去重来源数**：review3 (1) + review4 (1) + review5 baseline (1) + review5 report (1) + memory (9-20/9-21/9-23 = 3) = **7 个 source**
- **合并去重后 baseline 项数**：17 项（≥ 17 项门槛达成）
- **关联决策**：D-31 / D-32 / D-33 / D-34 / D-35 / D-36 / D-37 / D-39 / D-39-X / D-42 / D-44
- **关联前次审查**：review3 / review4 / review5
- **关联 baseline**：review5 baseline `docs/reviews/2026-09-23-3ccdf29-baseline.md`
- **缺失源**：
  - 9/22 memory 缺日（无 `memory/2026-09-22.md` 文件 — 9/22 工作内容散落在 handoff/ 与 docs/decisions.md，未单独留 memory 日志）
  - 9/19 memory 缺日（无 `memory/2026-09-19.md` 文件 — 历史 daily memory 索引外）
- **维护者**：B2 subagent 冻结（D-39 第 5 条禁止 amend）

---

## §7 报告末行（D-39-X 强制 — baseline 必引用）

Baseline: docs/reviews/2026-09-23-3ccdf29-regen-baseline.md (frozen)