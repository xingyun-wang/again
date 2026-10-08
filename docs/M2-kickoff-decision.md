# M2 Kickoff 决策书（2026-10-07）

> **状态**：3 决策点待拍板 + 1 延后（D-M2-3b，S4 后重提）→ 拍板后启动 S0
> **制定方**：载曜（基于《下一步工作计划-M2出作业全路径（2026-09-27）》，事实基线 `@b2a0d66`）
> **不立元规则**（per 星云 2026-10-07 拍板）—— 本决策书不进 `docs/decisions.md` D-XX 系列，仅作工程决策记录于本文档。

---

## 1. M2 范围（七组件 + 来源：产品定义 v0.5 §10.2 行 508）

| # | 组件 | 阶段 | 状态 |
|---|---|---|---|
| ① | 题库 CRUD | — | ✅ 已完成（commit `3ccdf29`，迁移 `0007_questions.py`） |
| ② | 外部题库导入 | S6 | ⬜ 可后置 / 可降级 |
| ③ | §3.2 4 档差异化引擎 | S1 | ⬜ |
| ④ | §3.5 反马太引擎（**只从 C 抽**）| S1 | ⬜ |
| ⑤ | 老师手动覆盖档位 + 动态调整 K/M/N | S2 | ⬜ |
| ⑥ | §3.6 作业生成 + 审阅 + PDF | S3 + S4 | ⬜ |
| ⑦ | §7.5 审阅硬约束（未审不得导出） | S3 | ⬜ |

---

## 2. 三前置债（P1/P2/P3，源文件 §0 一页结论）

| # | 前置债 | 状态 | 备注 |
|---|---|---|---|
| **P1** | 零产品 UI（`frontend/src/` 6 文件 166 行）| ⬜ 待启动 | **贯穿 S3 起为硬依赖**（§3.6 四步教师流程 + §7.5 审阅状态机都需要 UI）|
| **P2** | 题库内容为零（无任何种子数据）| ⬜ 待启动 | 反马太判据要求 ≥100 C + ≥100 D；可与并轨 B（精录）合并做 |
| **P3** | 业务端到端零实证（verify 恒失败 + 3 重 CI 阻塞）| **✅ 已修** | commit `b2a0d66` + pytest 7/7 passed |

---

## 3. 计划骨架（守 D-25：每段一个可验收产物）

```
S0  前置  （3 决策点拍板（D-M2-1 / D-M2-2 / D-M2-4）+ 1 延后（D-M2-3b，S4 后）+ TWAIN 轨启动 + C 池 ≥100 题启动）
S1  出题引擎        = §3.2 4 档 + §3.5 反马太（只从 C 抽）    ← 原 M2-A.1
S2  档位管理        = §3.2 手动覆盖 + 动态调整 K/M/N
S3  作业生成 + 审阅 = §3.6 四步流程 + §7.5 审阅硬约束 + **前端首块 UI**
S4  PDF 导出        = §3.4 每生一份                            ← 原 M2-A.2
S5  端到端验收      = 第一个差异化作业包（M2 收官位）
S6  外部题库导入    = §3.3（可后置 / 可降级）                   ← 原 M2-A.3

并轨 A：TWAIN 架构路径验证（mock 掉 HTTP 桥即可；不要求真扫描仪）
并轨 B：§5.3.2 精录 + C 池 ≥100 题内容建设
```

**注意**（源文件 §4）：并轨 A 的产出**不是**"1 款扫描仪实测"——实测属 M3/M5。M2 只需要"**架构路径通**"。把实测塞进 M2 = 用跨里程碑依赖锁住第一步。

---

## 4. 3 决策点 + 1 延后（待星云拍板 / D-M2-3b 待 S4 后）

### D-M2-1：前端策略（M2 是否必须交付 UI？）

- **(a) 后端先行 + S3 起补 UI**（源文件默认假设；推荐）
- (b) M2 只交付后端 + 脚本验收，UI 推 M2.5
- (c) 先补 M1 的 UI（AI 声明 / 审阅页）再进 M2

### D-M2-2：外部题库（S6）走 CSV/粘贴导入 还是 API 对接？

- **CSV / 粘贴导入**（v0.5 §3.3 已说"菁优网 API 暂不接入"；MVP 降级推荐）
- 对接第三方 API（菁优网 / 学科网）

### D-M2-3a：C 池输入规模 ≥100 C + ≥100 D —— ✅ 已落地（2026-10-07）

S1 用结构占位 fixture 已够；commit `feat(fixture): ...`（200 行 Q-POOL-C-001..100 + Q-POOL-D-001..100），内容 = `[content team: ... — 内容轨待填]`。解锁 D-47 输入规模 + 防 owner_user_id NOT NULL 落库必挂。

> ⚠️ **内容质量留给内容轨**：题目 content / knowledge_points / choices 都是结构占位，**不是真题**。生产真题池何时建 / 怎么建 = D-M2-3b 延后议题（见下）。

### D-M2-3b：生产真题池的规格（手工 / 导入 / 精录） —— ⏸ 延后

**时点**：S4（PDF 导出）完工后。那时才知道引擎对题干长度 / 选项数 / 知识点粒度的实际要求，再决定是手工 / 导入 / 精录产出。

备选：
- 手工录入（教师手动建库）
- 导入（已有题库 / 第三方素材）
- 精录产出（合并并轨 B，§5.3.2 长期任务）

> **为什么不现在决**：S4 完工前的"规格"是猜测，决策质量不如 S4 后真凭实证拍。延后 ≠ 删，是更精确的"何时决"。

### D-M2-4：TWAIN 轨是否本周启动？

- 买 / 借扫描仪（影响硬件采购）
- **先只做架构路径 mock**（推荐；源文件 §4 建议"mock 掉 HTTP 桥即可"）



---

## 5. 风险与反模式

- **scope creep**（AGENTS 教训 #9）：M2 7 组件，**一次只推一段**（S1 → S2 → …），不并片
- **前端从零起是隐性大块**（教训 #22）：166 行 → 路由 + 状态 + 表单 + 审阅状态机；工作量估算 ×1.5-2
- **不要把门槛挂在 `verify` 上**（P3 已修）：verify = 端到端（真 PDF + key + 80s），不进 per-push = 设计非债（**D-M2-5 已撤销**；per 星云 2026-10-07 12:40 拍板；并 D-47/D-49/D-44）
- **不要跨里程碑并行**：§10.5/§10.6 明令"不允许 M2 + M3 并行"
- **不要用本地 ref 判断远端已同步**（源文件 §1.4）：`origin/master` / `github/main` / `gitee master` 三方真值需在收工时 `git ls-remote` 核
- **P3 fail-open 防护只是结构层最小保障**（commit `b2a0d66` 字面量静态检查）；完整 fail-open stub 攻击防护需要扫描型 PDF fixture（不在本 commit 范围）

---

## 6. 启动检查清单

- [ ] 3 决策点拍板（D-M2-1 / D-M2-2 / D-M2-4）+ 1 延后（D-M2-3b，S4 后重提）
- [ ] S0 启动：
    - 派 subagent TWAIN 架构路径 mock（S0-3）
    - C 池 ≥100 题内容建设启动（S0-4 / 并轨 B）
- [ ] S1 出题引擎派工（per `plans/README.md` 命名规则：`M2-A.1-brief.md`）

---

## 7. 决策账本（待星云拍板后填）

| 决策 | 拍板选项 | 拍板日期 | 落实 commit |
|---|---|---|---|
| D-M2-1 前端策略 | — | — | — |
| D-M2-2 外部题库（S6） | — | — | — |
| D-M2-3a C 池规模 ≥100 | ✅ 已落地 | 2026-10-07 | (fixture commit) |
| D-M2-3b 生产真题规格 | ⏸ 延后 | — | （S4 完工后重提） |
| D-M2-4 TWAIN 轨 | (a) 先只做架构路径 mock + 3 补丁 A/B/C | 2026-10-08 15:11 | —（待 commit） |
| ~~D-M2-5 CI 三重阻塞~~ | — | **已撤销**（2026-10-07 12:40 拍板：verify 不进 per-push = 设计；并 D-47/D-49/D-44）| — |

### 7.1 拍板记录（D-M2-1 · 2026-10-08 13:55）

- **决策**：D-M2-1 前端策略（M2 是否必须交付 UI？）
- **拍板选项**：**(a) 后端先行 + S3 起补 UI**（与决策书源文件默认假设一致）
- **附 3 个补丁**：
  - **补丁 A · 防风险 1（前端从零起是隐性大块）**：S0 启动时一并起前端骨架（React 18 + TS + Vite + AntD 5 = v0.5 §7 已定稿）—— 只搭：路由 + 状态管理 + ProTable 模板 + 空白 `App.tsx`；**不连功能页**（路由表 7 段 M2 组件全部 placeholder）
  - **补丁 B · 防风险 2（scope creep）**：S3 UI 一次只出 **1 个核心页**（题库 CRUD = 教师管理后台入口），做端到端验证；再批量复制到其他组件（教师审阅 / 4 档分配 / PDF 预览）
  - **补丁 C · 防风险 3（后端期无可视化）**：M2 验收 = **pytest + e2e 脚本 + PDF 文件验收**（每周一次 4 档 × 50 生 = 200 PDF 抽样 → `docs/M2-weekly-review/`）
- **拍板时点**：2026-10-08 13:55 +0800
- **来源**：星云拍板 + 载曜建议（详见 `memory/2026-10-08.md §十二`）
- **驳回选项**：
  - (b) M2 只后端 + UI 推 M2.5 — ❌ 不推荐（M2 不闭环；M2.5 = 新里程碑松散；星云作为老师日常接触面 = UI）
  - (c) 先补 M1 UI 再进 M2 — ❌ 不推荐（M1 已收口；CHARTER §5.3 反 AI 直接入库的未来警惕 = M2-A.1 brief 规则即可；M2 启动延期）
- **落实 commit**：待 commit（与 D-M2-4 拍板后一起；commit 时填 §7 表 + 本段同步）

### 7.2 拍板记录（D-M2-2 · 2026-10-08 14:56；技术方案修订后）

- **决策**：D-M2-2 外部题库（S6）走 CSV/粘贴导入 还是 API 对接？
- **拍板选项**：**(a) CSV / 粘贴导入**（与 CHARTER §5「菁优网 API ⏳ 接口预留，未来重启」+ v0.5 §3.3「外部题库：菁优网 / 学科网 / 其他」一致）
- **S1 前置债 1 · 题目图片承载（必修 · 拍板时机 = S1 题库模型定稿前）**：
  - **模型**：独立 `question_images` 表（1:N，与 `choices` 同构）；12 列字段 = id / question_id(FK) / order_index / file_ext(String(8)) / storage_path(String(512)) / source(enum: self_built|external_imported) / desensitization_status(enum: pending|done|skipped) / desensitized_at / uploaded_at / uploaded_by_user_id(FK) / oss_object_key / oss_uploaded_at
  - **关系**：`Question.images: Mapped[list[QuestionImage]]` = `relationship(..., order_by="QuestionImage.order_index")`
  - **路径模板**：`{chapter_id}/{question_id}/{image_id}.{ext}`（修 D-43-X：旧 `{chapter_uuid}/{question_uuid}_{n}.{ext}` = 失实，uuid 列不存在）
  - **API**：`POST/GET/DELETE /questions/{id}/images[/{image_id}]`
  - **存储**：
    - 本地 = `backend/uploads/images/{chapter_id}/{question_id}/{image_id}.{ext}`
    - 云端 = 阿里云 OSS bucket `thp-images-{env}` + 脱敏后上传（v0.5 §6.5 + §7.2）
  - **1:N vs ARRAY 优势**：SQLite 测试栈 ✅ / 排序 / 脱敏标记 / 来源追溯 / OSS 状态 per-row（详见 `memory/2026-10-08.md §十三 D`）
  - **工作量估**：~250 行 backend + 50 行 model migration + 30 行前端上传组件
- **产品定义补字**（`v0.5 §3.4`，行 146-152 后）：
  > **图像密集学科（地理等）的题干必须为图片（地图 / 等值线 / 示意图）预留 image / asset 承载**——实现走独立 `question_images` 表（1:N，与 `choices` 同构），不混在 `questions` 表内
- **导入补丁**（防撞名；§7.1 已用「补丁 A/B/C」）：
  - **导入补丁 A**：MVP 只支持 1 个标准 CSV schema（schema 由产品定义好）→ 老师手动转格式
  - **导入补丁 B**：MVP 不做 OCR / auto-detect → Phase 2 再支持
- **不立元规则**：撤回 D-80 提案（特定学科硬伤前置 = 工程细节级约束，不必上升到元规则层；落字在 §3.4 硬约束 + `QuestionImage` 模型 docstring = 双重落字）
- **拍板时点**：2026-10-08 14:56 +0800
- **来源**：星云拍板 + 载曜建议（详见 `memory/2026-10-08.md §十三`）
- **驳回选项**：
  - (b) 对接第三方 API（菁优网 / 学科网） — ❌ 不推荐（API 鉴权 + 协议适配 + 数据格式转换 = 工作量 ×2-3；违反 CHARTER §5「菁优网 API ⏳ 接口预留」）
- **落实 commit**：待 commit（3 决策点齐；commit 时同步填 §7 表 D-M2-2/D-M2-4 行 + §7.2/§7.3 段 + `[origin-push]` 授权）

### 7.3 拍板记录（D-M2-4 · 2026-10-08 15:11）

- **决策**：D-M2-4 TWAIN 轨是否本周启动？
- **拍板选项**：**(a) 先只做架构路径 mock**（与决策书 §3「并轨 A」+ §D-M2-4「推荐」+ v0.5 §6.4.1 一致）
- **3 个补丁**：
  - **补丁 A · 防风险 1（HTTP 桥契约稳定）**：mock = HTTP 桥抽象层 + pytest 桩（4 档答案卡模拟响应）；接口契约 = `POST /scan/omr` 接受 PDF/图片 → 返回 `{"answers": [...], "metadata": {...}}`；M3 接入真扫描仪 = 仅替换 mock 为真 HTTP 桥实现
  - **补丁 B · 防风险 2（跨边界架构预留）**：v0.5 §6.4.1 三层架构（Linux 容器只走 HTTP 桥 / 容器 ↔ 宿主机 HTTP 通信 / Windows 宿主机跑 TWAIN DSM 服务）；mock 按三层架构做 = M3 替换 mock 时零返工
  - **补丁 C · 防风险 3（硬件询价并行）**：mock 启动派 subagent（不依赖硬件）+ 硬件询价同步启动（询价/走采购/备选 3 步并行；不影响 M2 启动）；防 M5 前紧急
- **拍板时点**：2026-10-08 15:11 +0800
- **来源**：星云拍板 + 载曜建议（详见 `memory/2026-10-08.md §十四`）
- **驳回选项**：
  - (b) 买/借扫描仪做实测 — ❌ 不推荐（违反 v0.5 §6.4 真值；M2 提前实测 = 跨里程碑依赖锁住第一步；决策书 §3「注意」明示）
  - (c) 本周不启动 — ❌ 不推荐（决策书 §6 启动清单第 2 项 = 本周必须；推迟 = S0 启动撞 TWAIN 空白）
- **落实 commit**：3 决策点齐（D-M2-1 ✅ + D-M2-2 ✅ + D-M2-4 ✅）；可执行 commit + `[origin-push]` 授权

---

## 8. 待办 / Follow-ups

- **chapter_ref FK 修复**：fixture 198 行用 `CP-DEMO-{C,D}-{1..10}`（20 种占位章节），但 `questions_tier_demo.json` 只有 4 个 `CH-DEMO-{A,B,C,D}-1`。当前不阻塞（conftest 只内存加载、不写库），但 S1 真写库时 FK 会解析不到 ⇒ S1 启动前对齐章节（用 demo 的 4 个，或扩 demo 章节集到 ≥10 / tier）。

---

**不立元规则**（per 星云 2026-10-07 拍板）：本决策书不进 `docs/decisions.md` D-XX 系列；仅作工程决策记录于本文档。如未来需立元规则，由星云另行拍板。

**事实基线核源**（取数时刻 2026-10-07 12:40 +0800）：

```
git -C /home/wsq_1/tiered-homework-platform rev-parse HEAD    # b2a0d66
git -C /home/wsq_1/tiered-homework-platform log --oneline -5
git -C /home/wsq_1/tiered-homework-platform status --porcelain   # clean
docker images postgres:15-alpine --format "{{.ID}}\t{{.Size}}\t{{.CreatedSince}}"  # aad6289ca337 292MB 7 weeks ago
```