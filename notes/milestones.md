# notes/milestones.md — STATE.md 主体迁出（2026-10-04 commit 6）

> **用途**：STATE.md 超 8.25× 软上限（25319 B / 3072 B）触发 §5.3 #6 剪枝；按审查员核对回执 2026-10-04 21:18 §七 α 修正"不需用户确认"提前做 → 主体迁出到本文件，STATE.md 瘦身到指针 + 元数据字段
> **维护规则**：每节定稿 / W 阶段 commit 后 / 用户明确要求时更新（同 STATE.md 旧规则）
> **最后更新**：本笔 commit 6（2026-10-04 21:18）

---

## 一页纸摘要

| 问 | 答 |
|---|---|
| **从哪来** | 8/12-8/15 研究 + v0.1~v0.4 四版定义 + W1~W4 工程（已封存于 `.bak.2026-09-10/`，参考用）→ 9/14 v0.5 §0-§5 定稿 → 9/14 晚上工作流重构 + 灾难恢复落地 |
| **谁做的** | **王星云**（方向+拍板，本人析木高中地理老师）/ **载曜**（技术+想法/建议/问题+记录） |
| **做到哪** | **v0.5 §0-§11 全定稿**；WAKEUP.md + 4 项灾难恢复已建；**M0 docker 验收 9/9 ✅**（含国内镜像源 patch）；**M1-B B.0/B.1/B.2/B.3 全过**；旧工程代码保留为参考；新工程从 v0.5 §10 起写 |
| **下一步** | **开 M2 题库 CRUD**（M2 = 作业生成 + 题库 + 4 档差异化 + 反马太 + PDF 导出）。**§10.4 并行工作**：§6.4 TWAIN 扫描仪实测（M5 最大 blocker，应立即启动）。D-25 §7.6 工程推进分阶段底线不破 |

---

## 硬约束（来自前序研究，将在 v0.5 中逐节重新确认）

> 这些是前序研究的产物，不是 v0.5 的定稿。v0.5 重写过程中，如发现与新定义冲突，**按 v0.5 走**。

- 学科：高中地理选择性必修 1 全 5 章（前序研究结论）
- 档位（字母升序=难度升序）：D 基础 / C 进阶 / B 挑战 / A 扩展（前序研究结论）
- 反马太：D 档作业强制 20% 拔高（前序研究结论）
- 题库：老师自建为主；菁优网 API 暂不接入；AI 出题全面废弃（2026-08-21 拍板）
- 共建题库：MVP 不启用 `is_public`；阶段 2 启动（2026-08-30 拍板）
- 合规：家长授权 / 数据脱敏 / AI 声明 / 教师终审 / 未成年人"钢铁模式"（来自前序政策研究）

---

## 工作约定（确认于 2026-09-14）

- 王星云：方向 + 拍板
- 载曜：技术 + 想法 / 建议 / 问题 + 记录
- v0.5 §0 灵魂：星云口述，载曜记录；不主动插技术反馈
- §0 定稿后：载曜进开发者模式
- **旧工程代码：参考用，不接旧进度；新工程从 v0.5 定稿后写起**
- **2026-09-14 增**：reset/收工/唤醒工作流——收工由载曜做 4 步（更新 memory / 改 STATE / 跑 backup.sh / 报告），然后星云 reset
- **2026-09-14 增**：wake-up 固定 4 项 = 产品定义 / 最近 3 天日志 / 进度 / 宪法（详见 `WAKEUP.md`）
- **2026-09-14 增**：项目日志放项目本地 `tiered-homework-platform/memory/`，不依赖 zaiyao-memory 全局目录
- **2026-09-16 增**：v0.5 §10 排期定稿 = 里程碑式 M0-M7 + 依赖图；v0.4 W1-W12 废弃；MVP 启动 = 4 条件 blocker 全满足；CHARTER §7.0 会话分工在 M0-M7 实施阶段严格执行
- **2026-09-16 增**：v0.5 §11 变更日志定稿 = v0.5 期间每节定稿变更（§11.2）+ 演进里程碑（§11.1）+ v0.4→v0.5 全量追踪（§11.3，末尾表升级迁入）；原则=存在且精简，写给未来的载曜
- **2026-09-16 晚增**：M0 docker 验收 9/9 全过（pull + build + up + /api/health + SPA bundle+proxy + ruff + mypy + pytest + npm lint）；patch = 国内镜像源（backend Aliyun apt+PyPI / frontend npmmirror）；judgment = #5 SPA 验收放宽 / alembic upgrade head 未入 compose 启动链路；教训 = 镜像源工程模板化 + exec tracker stale 实战对策
- **2026-09-16 晚增**：M0 优化 = pip 镜像源 ENV → `--index-url` flag 形式（决策室 judgment；per-RUN 显式，避免污染容器全局 pip 配置）；README + .env.example 加国内镜像源注释；flag 形式 build 等 M1 复跑确认
- **2026-09-18 增**：M1-B 实质收官 = B.3 端到端 5 章节验证全过。B.3.1 = `POST /textbooks/upload` 升级 multipart/form-data + PyMuPDF + pdfplumber 双库（adapter in service）；B.3.2 = 真 PDF + 真 LLM 5 章节 extract + lesson-plan + review 全跑通（`scripts/verify_end_to_end_5_chapters.py`，20 API + 10 LLM 调用 / 80s）；B.3.3 = §7.5 review_notes 持久化验证 + OpenAPI AIAnnotation/TeacherReviewStatus 完整 + README 更新。pytest 146 passed / 8 skipped；ruff + mypy 全过。judgment = #1 upload 暂不支持 batch / #2 LLM 失败 fail-fast / #3 review_notes 可选 / #4 adapter 放 service 层。教训 = FastAPI Form 依赖 python-multipart；nginx 默认 client_max_body_size=1M 不够；errookept handler 自定义 ErrorResponse{message}（无 detail 键）。等决策室 commit/push → M2 启动

---

## 链接索引

- **历史 STATE（详细，参考）**：`.bak.2026-09-10/STATE.md`
- **项目宪法（前序 v0.1，参考）**：`docs/PROJECT-CHARTER.md`
- **v0.4 产品定义（参考）**：`docs/产品定义-v0.4.md`
- **v0.5 产品定义（定稿中）**：`docs/产品定义-v0.5.md`
- **决策日志**：`docs/decisions.md`
- **待解决问题**：`docs/open-questions.md`
- **唤醒清单（4 项固定读取）**：`WAKEUP.md`
- **项目级工作约定**：`AGENTS.md`
- **教训**：`zaiyao-memory/MEMORY.md` §B/§C/§D
- **8/12-8/15 研究**：`zaiyao-memory/memory/2026-08-1{2,5}-*.md`
- **9/14 工作日志**：`memory/2026-09-14.md`
- **9/15 工作日志**：`memory/2026-09-15.md`
- **9/16 工作日志**：`memory/2026-09-16.md`
- **灾难恢复（zaiyao-memory 仓）**：`git@gitee.com:wang-xingyun1021/zaiyao-memory.git`

---

## session 启动清单（详见 `WAKEUP.md`）

**4 项固定读取**：
1. `docs/产品定义-v0.5.md`
2. 最近 3 天 `memory/YYYY-MM-DD.md`（不存在的跳过）
3. `STATE.md`（本文件已迁出至 `notes/milestones.md`，STATE.md 仅保留指针）
4. `docs/PROJECT-CHARTER.md`

读完后第一句话：「上次停在 X，下一步 Y，开放问题 Z」（不复述内容）

**不**启动旧服务（vite/uvicorn 是旧工程的；新工程从 v0.5 §10 起写）

---

## §10 排期快照（详见 `docs/产品定义-v0.5.md` §10）

| M | 名称 | 关键产物 | 依赖 |
|---|---|---|---|
| **M0** | 准备 | Docker Compose + 项目骨架 + CI/lint | — |
| **M1** | 备课（§2.2 步骤 1） | 学科知识库 + AI 辅助录入 + AI 备课助手 + 学情数据模型预留 | M0 |
| **M2** | 出作业（§2.2 步骤 2） | 题库 CRUD + 外部题库 + 4 档差异化引擎 + 反马太 + PDF 导出 | M1 |
| **M3** | 上传+评分（§2.2 步骤 3） | 答题卡模板 + TWAIN 实测通过 + OMR + 主观题录分 UI + 云端备份 | M2 |
| **M4** | 学情画像+再备课（§2.2 步骤 4） | 三维度学情画像 + 三层备课建议 + 重点关注清单 + 闭环回 M1 | M3 |
| **M5** | MVP 上线条件验证 | 4 步闭环跑通 + TWAIN + 本学期精录 + UI 走查 | M1-M4 |
| **M6** | 星云 1 班试用（§8.5） | MVP 上线 + 1 班验证（不通过=迭代修复） | M5 |
| **M7** | Phase 2 起点 | §1.2 全学段小范围（+1 初中地理老师） | M6 通过 |

**并行工作**（与开发并行启动）：
- §5.3.2 本学期精录章节（M1 AI 辅助录入上线后启动；M5 前完成）
- §6.4 TWAIN 扫描仪实测（M0 后立即启动；M5 前通过）

**CHARTER §7.0 会话分工**：M0-M7 实施阶段所有写前后端 / 跑代码 / debug 工作在 subagent 工地，不在决策室。

---

## 反思与元规则（2026-09-23 增）

### D-41 双重未遵守事实

- **2026-09-21（D-41 落字当天）**：9/21 日志明写「backup.sh 下个 commit 一起做」 = 第 3 项未跑
- **2026-09-22（次日）**：memory 缺日 = 第 1 项未跑（补登见 `memory/2026-09-22.md`）

### 反思

- D-41 写「必须」但没有「未遵守怎么办」= 规则自身 fail-open（D-42 第 4 层）
- **D-43-X 候选**：每轮收工 1 行 grep 表，新规则执行次数 < 1 = 标 ⚠️ 并列入下轮必办
- 这是「落字」≠「执行」的典型表现，与决策书 §4 三条「落字未落地」表同构

### 与 D-43 关系

D-43 第 5 条「决策室不修代码逻辑」+ 第 6 条「决策室验证环路」已落字；D-43-X 是元规则层的扩展，
对应「规则自身的出口检查」，等星云拍是否独立编号（D-44-X 或并入 D-43 第 7 条）。

### 来源

外部决策书 §4「三条落字未落地」表 + §2 拍板 7 元规则建议。

---

## 收口轨迹（2026-09-23 增）

### Phase A 决策室立刻做的（5 件）

| # | 件 | 结果 |
|---|---|---|
| P0 | `git ls-remote` 三方核 | ✅ local = origin = github = `a170083c57478c08ecd8202f34db98ca97679f1b`（证据强度升级到 D-36-A 级）|
| A1 | `bash ~/zaiyao-memory/backup.sh` | ✅ push Gitee `ba43250..394b711  main -> main`（D-14 停跑 5 天已补）；同步 4 个 memory 文件进 zaiyao-memory 仓 |
| A2 | 修 handoff §5（补 handoff/）+ §8（编号 1-5）| ✅ |
| A3 | 修 handoff §6.4.1 段（推断错让路注）| ✅ |
| A4 | STATE.md 追加一轮（本段）| ✅ |
| A5 | 找 34 条 baseline | ⚠️ zaiyao-memory + OpenClaw 工作区 + /tmp + /var 全无 —— baseline 永久缺一环（决策书 §四自陈正确）|

### Phase B/C/D（待派工 / 收尾）

- **B1**：review5 改名 f949e91.md → 3ccdf29.md + D-39 第 1 条补 `<sha7>` 定义 + 「归档 commit freeze」新规则（治 3 次 amend 漂移源）
- **B2**：34 条 baseline 永久缺 → 从当前 3ccdf29 状态**重生成** baseline 清单（详见下面 §「Baseline 永久缺一环处置」）
- **B3**：N-1 P2 欠账登记到 `docs/decisions.md` D-43 段末 + STATE.md
- **B4**：commit 决策室改动（5 modified + 4 untracked）+ push + 三方核
- **C1**：验 CI step 7 mypy（gh api / curl GitHub Actions API，避开 readability裁剪）
- **D1**：再跑 backup.sh（D-14 灾备补二次）
- **D2**：更新 handoff/2026-09-23.md §8 推荐路径（标记已执行）

### D-44-X 物理事实强化（核源回执实测）

- `fbb7275^` = `8d3e3be`（M1-B retro CI-1）
- `8d3e3be^` = `a4d49d3`（Step 1 段 1 迁移 rename）
- reflog 还原链：`a4d49d3` → `8d3e3be` → `fbb7275` → `3c21dd1` → `171aabe` → reset → `fbb7275`（force push）

### N-1 P2 欠账（2026-09-23 登记）

**事实**：

- commit `9d332cc` (`fix(mypy): N-1 修 B1 pre-existing narrowing`) 在工地 subagent 产生 → D-43 第 5 条合规
- 改动：`backend/app/services/textbook_upload.py` 行 37 import 加 `cast`，行 449 `pending_path = cast(Path, None)`
- 本地 mypy EXIT=0（29 文件全过）—— 验收门槛过
- 但 `cast(Path, None)` 注释自承「运行时仍为 None」= 让 mypy 闭嘴，未修类型

**与 171aabe 实质比较**：

- 171aabe 改 `target_path` (line 442) + `pending_path` (line 443) 两个 cast
- 9d332cc 只改 `pending_path` (line 449) —— 比 171aabe 略不完整（少 target_path）
- 净代码效果（mypy EXIT 状态）：171aabe 之前 EXIT=1 → 171aabe 后 EXIT=0 → C 路径回滚后 EXIT=1 → 9d332cc 后 EXIT=0
- 净代码效果（行数）：从 0 cast → 1 cast（净增 1 行 cast 调用；171aabe 是 2 行）

**P2 欠账**：

- 未找到无 narrowing 路径（`committed: bool` flag / 重新 narrow / 拆 if 分支）
- `cast(Path, None)` = type: ignore 的另一种写法，掩盖而非修复
- 长期：未来 cast 加到几十处 → review2 baseline B1（B1 narrowing 改善观察）恶化

**处置**：

- **不开 fix 工单**（P2 不是 P0/P1）—— 等 review2 baseline 重启时一并处理
- 写进 M2-A.1 brief：M2-A.1 子任务「textbook_upload.py 重构」时一并消化此 P2
- D-43-X 候选规则「cast > type ignore > 重构 优先序」不适用此 case（mypy 已 EXIT=0，类型修正 = P2 推迟）

来源：收口决策书 2026-09-23 §三 + git show 实测（171aabe line 442/443 vs 9d332cc line 449）

### 推断错让路原则（2026-09-23 立）

- §6.4.1 / §10.4 TWAIN 推断（Windows 宿主机层调用）未经实测
- 若实测发现 TWAIN 在 Linux 侧有桥接方案（libtwain / WIA 服务）= 推断错
- 推断错 → §6.4.1 撤回 + §10.4 排期松绑 + M2 启动路径不变
- 门槛保留 fail-closed 精神，但不绑死推断（决策书 §四 + 决策室接受）

### Baseline 永久缺一环处置

- 第一轮 34 条 baseline 落在 WorkBuddy 工作区，从未进项目仓（决策书 §四 + 收口决策 §一 Q1）
- 9/22-9/23 多次搜索未果（zaiyao-memory + OpenClaw + /tmp + /var）
- **B2 调整方案**：不从 WorkBuddy 找 = 从当前 `3ccdf29` 状态**重生成** baseline 清单（17 P0/P1/P2 + D-37 四类命中点），冻结为 `docs/reviews/2026-09-23-3ccdf29-regen-baseline.md`
- 与 review5 baseline 合并管理：review5 末行引用本次 regen baseline（D-39-X 自带出口检查）

### 来源

收口决策书 2026-09-23 §一 §二 §三 §四 §五 + 外部核源回执 2026-09-23 + git reflog 验证（f949e91 amend 3 次实测） + 9/22 memory 反思。

---

## 收口决策书接住 + 接受率 backlog（2026-09-26 增）

### D-43-X 实战失实 4 次序列（同型事故）

| # | 误报 | 失实根源 |
|---|---|---|
| 1 | F949E91 死 SHA 命名 | run 命名 vs 实际 commit |
| 2 | "backup.sh 不存在" | `ls ~/zaiyao-memory/backup.sh` 路径未展开 |
| 3 | "M2-A.0 origin-unknown" | `git log --all -- tests/...` 漏 `backend/` 前缀 |
| 4 | "run #16 5/6 步通过" | ⊘ skipped 误读为 ✅ passed |

### 收口决策书 §四 7未办事项（执行状态）

| # | 项 | Phase | 状态 |
|---|---|---|---|
| 1 | 5ce46442 头部加注释 | A | ✅ 通过 memory/2026-09-26.md + STATE.md backlog + review5 §10 交叉引用 |
| 2 | 真 wait-postgres / debug-postgres 重写 | B1 | 待 subagent |
| 3 | 派独立审查 subagent（review6 + M2-A.1 准入 gate）| B2 | 待 subagent |
| 4 | 修订 review5 §6.1（D-45 第 3 条 compliance）| A | ✅ review5 §10 段新增 |
| 5 | M2-A.1 启动 | C | **等用户拍板确认** |
| 6 | 自报 review5 §6.1 假数据 | A | ✅ memory/2026-09-26.md §三 3.1 |
| 7 | 接受率入 STATE backlog | A | ✅ 本段 |
> [2026-09-28 S0-1 状态更新]
> - :227 真 wait-postgres —— 已实现（S1-⑩, 2026-09-26, ci.yml:107），销账
> - :228 review6 —— 已派（星轨 general-purpose subagent），M2-A.1 准入 gate 已解
> - :230 M2-A.1 启动 —— 名字废止；D-49 第 4 条已 flip（用户 2026-09-27 go）；后续按 D-50–D-54 重定框架走 S0-5 / S0-4 / S1

### 接受率（真实修订率）

- 决策书 §一.5 自报"接受率 0%"= 决策书 self-grep 验证
- 我方接受率真实 = **7/7 = 100%**（§四 7 未办事项全部接受为执行计划）

### D-42 升级（决策书 §六 接住，2026-09-26 立）

> **原 D-42**：fail-open 三层复发 + D-36 操作化
> **D-42 升级（§六 烧 3 次修复后立）**：CI/部署配置里任何关于**"平台会怎么做"**的断言，必须附：
> 1. **官方文档出处**（GitHub Docs URL + 章节 / version）
> 2. **一次实跑证据**（git log + ci run + 实际输出）
>
> 不满足上述两条者，在评审时按 **P1** 计。
>
> **实战失实样本**（决策书 §六）：
> - 44624f2 ci.yml:92-94 注释："DNS 传播瞬时失败 = race condition"——无 Docs 出处、无实跑证据 → 烧本次修复链
> - 5ce4644 ci.yml:27 注释："容器内 host = `postgres`（GitHub Actions service 默认 DNS 名）"——错的（无 `container:` 键不适用此规则）
> - ci.yml:88-90 注释："迁移 ID 字符数回到 32 以内，scaffold 无必要"——0005 35 字符 现实责为"以上为假陈述"（决策书 §五）
>
> **B2 review6 同样违反 D-42**：§2.4 + §3.1 仅看 "形式自洽" 未看"根因错"——修订为 ⚠️

### B1' 准备 spec（自选式探针，决策书 §五 接住，2026-09-26 19:22 立）

**单 commit 替换 wait-postgres 步**（决策书 §五提议；D-43-X-2 §1 §2 设计要求：禁 2>/dev/null / 探针自证）：

```yaml
      - id: wait-postgres
        name: Wait for postgres ready (self-selecting host)
        run: |
          # 决策书 §五：自选式探针 — 两个 candidate + 失败 dump
          # D-43-X-2 升级：禁 2>/dev/null + 探针自证（不静默 stderr）
          for host in 127.0.0.1 postgres; do
            echo "--- Probing $host:5432 ---"
            if (timeout 5 bash -c "echo > /dev/tcp/$host/5432") 2>&1; then
              echo "PG_HOST=$host" >> "$GITHUB_ENV"
              echo "PG_PORT=5432" >> "$GITHUB_ENV"
              echo "Found working host: $host:5432"
              exit 0
            else
              echo "FAILED: $host:5432 unreachable"
            fi
          done
          echo "ERROR: neither 127.0.0.1 nor postgres reachable on port 5432"
          echo "=== Diagnostic dump (D-43-X-2 §3 必附证据) ==="
          echo "--- ss -tlnp ---"
          ss -tlnp 2>&1 || echo "ss not available"
          echo "--- docker ps -a ---"
          docker ps -a 2>&1 || echo "docker not available"
          echo "--- /proc/self/cgroup ---"
          cat /proc/self/cgroup 2>&1 || echo "cgroup not available"
          echo "--- getent hosts postgres ---"
          getent hosts postgres 2>&1 || echo "FAIL getent"
          echo "--- /etc/hosts ---"
          cat /etc/hosts 2>&1
          echo "--- ps aux postgres ---"
          ps auxf | grep -i postgres | head -5 || echo "no postgres process"
          exit 1
```

**同步改 ci.yml:53** `DATABASE_URL`：
```yaml
# 旧：DATABASE_URL: postgresql+psycopg://postgres:postgres@127.0.0.1:5432/tiered_homework_test
# 新：DATABASE_URL: postgresql+psycopg://postgres:postgres@${{ env.PG_HOST }}:5432/tiered_homework_test
```
理由：若 127.0.0.1 通 → ${env.PG_HOST} 解析为 127.0.0.1 → 后续 step 正常
       若 postgres 通 → ${env.PG_HOST} 解析为 postgres → 后续 step 走 postgres hostname

**预期**（决策书 §八）：
- 127.0.0.1 通 → CI 全绿（alembic / pytest / verify）= M2-A.1 准入门禁达 3/3
- ⚠️ [2026-09-28 作废标记] verify 步是 dispatch-only（已加 `if: workflow_dispatch` 跳过 per-push）；`_check_extraction_source_gate` 段 A/B 互补恒返回 False（D-54 V2 素材分档决策，2026-09-28）；verify 不再作为 per-push 准入门槛。
- postgres 通 → 后续 step 走 postgres hostname → CI 全绿
- 两都失败 → dump 6 源诊断（ss + docker + cgroup + getent + /etc/hosts + ps）= 决策书 §四 B 触发条件

**不**做：
- 不改 verify 步（已加 if: workflow_dispatch 跳过 per-push）
- 不改 DATABASE_URL 之外的 env 段
- 不改 services: postgres 块（healthcheck 已够）
- 不改 alembic 0005/0006（5d68b3c 已修 chain）

### 来源

收口决策书 2026-09-26 §一 §二 §三 §四 §五 §六 §七 §八 §九 + git 实测（5ce46442 + 9d332cc vs 171aabe + test_question_crud.py SKIPPED 验证 + HEAD = 5ce46442 三方一致 + ci.yml L27/L51/L78-90/L100-129/L165-177 全文 + alembic 0005 35字符 + materials/ git tracked 空 + .gitignore materials/ + DEEPSEEK_API_KEY 在 ci.yml L170 引用 `secrets.DEEPSEEK_API_KEY` 待查）+ memory/2026-09-26.md + decisions.md D-43/D-44/D-45/D-43-X + review5 §10 D-45 compliance 段 + review6 §2.4/§3.1 D-45 §3 修订。


>
> **[2026-09-29 备注 · GitHub 仓设计 · 12:00 UI 操作]** `xingyun-wang/again` 是本项目 GitHub 备份仓。**9/29 12:00 用户 GitHub UI 操作**:`default branch = master` + **删 `main` 分支**。**历史链**:D-40 push 策略 `master:main` 显式 refspec(`decisions.md:542`)= `main` 存在原因;09-27 及之前推 `main`,09-29 10:24 起改推 `master`,`main` 定格 `a891562`;12:00 清理。**非两个项目承载**;"OpenClaw 工作区覆盖 main"风险**不存在**(无来源)。
>
> **[2026-09-29 12:36 · 审查员意见书 v3 接住 + n1 F401 修落地 + 决策账本 D-58/D-59 落字]**
> - C 工单 commit `7eac2af` 推 GitHub 后 CI run `36521672033` = **failure**（Ruff check app+tests F401：`import pytest` 未用，后续 mypy/alembic/pytest/verify 全 skipped）；`+1` 验收**从未在 CI 执行过** — D-43-X #6（工具失败要换路径重试）+ #2（任何 tests/ 工单必须含入场闸）违反
> - n1 工单：subagent 删 `backend/tests/test_question_pool_fixture.py:14` 的 `import pytest` + ruff/mypy 双闸双绿 + pytest 1 passed；commit `610dd18`（本地 ahead 1，**未 push**，等用户拍 n4 push 责任）
> - **D-58 落字**：dev box SQLite fallback 保真度（主题工单挂 backlog） — 真违约列 = `textbooks.owner_user_id`（FK `nullable=False`）；不影响 MVP
> - **D-59 落字**：任何 tests/ 工单入场闸硬规则（必含 `ruff check app tests` + `mypy app` 双闸绿才允许 commit）
> - **D-60 落字**：`+1` 验收判据口径订正 — **同环境相邻 run 差值 + 新 nodeid 出现**，废止绝对数 N=199（另见 `decisions.md` D-60）

---

> **【2026-09-30 12:45 变更说明 · STATE.md】**
>
> **修订范围**：1 项 + 1 落字
> 1. **L3-L5 + L323 四行「最后更新」→ 合并为单行最新值 `2026-09-30 12:45`**（D-66 ② 类元数据字段；§2① 物理病根修法）
> 2. **实战失实 #11-#15 落字**（D-43-X-3 段 append；commit 3 同步）
>
> **法源依据**：
> - **D-67**（2026-09-30 立，本笔同落）= §2① STATE.md 病根修法
> - **D-68**（2026-09-30 立，本笔同落）= §2② 自指悖论修法
> - **D-43-X-3**（2026-09-27 立）= 实战失实落字
> - **审查员核对回执 2026-09-29/30 §2① + §2② + §1 B + §4 a**
>
> **历史沿革**（原 L3-L5 + L323 四行，已合并）：
> - L3 原内容（2026-09-27 13:00）：M2-A.0 pre-flight 闭环 + D-47/48/49 落字 + M2-A.1 硬门禁 = 等用户明确 "go"
> - L4 原内容（2026-09-28 19:03）：S0-1 收口（STATE.md 时间戳 + :302 verify 作废标记 + :227/:228/:230 状态更新块 — 4 项 append 式；D-43 例外内）
> - L5 原内容（2026-09-29 13:46）：w3+w4 记账（D-59 修正注记 + 立 D-61）；同笔 meta commit，双推 Gitee/GitHub（锚点 `b33e333`）
> - L323 原内容（2026-09-29 10:23）：GitHub 补推 CI success（run `36512464472`, head_sha=`aa2ad72`, 2分25秒）+ 状态修订（B2 关闭 D-51 / B1 拍板并行开 S0-5 + S0-4）+ memory/2026-09-29.md 新建 + F1 死守卫 / F2 label 缺等 ed2eb46 复核问题待派 subagent 工单
>
> **4 行原文逐字**（按 D-67 + D-61 §2 三要素；取证 `git show f2159ec:STATE.md`）：
> - L3 原文（f2159ec line 3）：`> **最后更新**：2026-09-27 13:00（**M2-A.0 pre-flight 闭环 + 3 决策落字 + M2-A.1 硬门禁**：per-push CI 9dad894 全绿 + pytest 实证 194+ passed / 0 failed；D-47/48/49 落字（M2-A.1 验收判据 / §3.5 反马太修正 / 启动模式）；M2-A.1 启动硬门禁 = 等用户明确 "go"）`
> - L4 原文（f2159ec line 4）：`> **最后更新**：2026-09-28 19:03 — S0-1 收口（STATE.md 时间戳 + :302 verify 作废标记 + :227/:228/:230 状态更新块 — 4 项 append 式；D-43 例外内）`
> - L5 原文（f2159ec line 5）：`> **最后更新**：2026-09-29 13:46 — w3+w4 记账（D-59 修正注记 append blockquote + 立 D-61「账本修正一律 append，禁原地改写」）；同笔 meta commit，双推 Gitee/GitHub（锚点 = `b33e333` 提交时间 `2026-09-29 13:46:25`）`
> - L323 原文（f2159ec line 323）：`> **最后更新**：2026-09-29 10:23 — GitHub 补推 CI success（run `36512464472`, head_sha=`aa2ad72`, 2分25秒）；状态修订（B2 关闭 D-51 已拍 / B1 拍板并行开 S0-5 + S0-4 不叫 v0.6）+ memory/2026-09-29.md 新建；F1 死守卫 + F2 label 缺等 ed2eb46 复核问题待派 subagent 工单（详见 memory/2026-09-29.md）`
>
> **影响范围**：
> - **失实 #11 物理病根** = STATE.md 多值「最后更新」字段 = 移除（合并为唯一真值）
> - **§5.3 #4 第 5 项核源动作**（WAKEUP.md 已落地，commit 1 `f2159ec`）+ **STATE.md 唯一真值** = **双护栏**（下次 reset 醒后必跑）
>
> **来源**：审查员核对回执 2026-09-29/30 §2① + §2② + §1 B + §4 a + `grep -n -F '最后更新' STATE.md` 4 行实证 + 用户拍 a

---

> **【2026-10-04 21:18 变更说明 · STATE.md → notes/milestones.md】**
>
> **修订范围**：1 项结构重组
> 1. **STATE.md 主体 → 迁出至 `notes/milestones.md`**（D-66 ② 类元数据字段；§5.3 #6 触发后动作按审查员核对回执 2026-10-04 21:18 §七 α 修正"不需用户确认"提前做；STATE.md 超 8.25× → 瘦身到 ~3 KB 范围）
>
> **法源依据**：
> - **D-70**（2026-10-04 立，本笔同落）= 双口径类数字必带右端锚点 + STATE.md 重组 + 失实 #24 双推归档修订
> - **D-69**（2026-09-30 立）= 凡"锚点/指针"字段只能写回查式
> - **D-67**（2026-09-30 立）= §2① STATE.md 病根修法
> - **D-66**（2026-09-30 立）= 三类分法（① 账本 / ② 元数据字段 / ③ 协议/清单文件）
> - **审查员核对回执 2026-10-04 21:18 §三 订正 1+2+3 + §七 α 修正**
>
> **影响范围**：
> - **失实 #11/#24/#25/#26 物理病根修复路径闭环**：双护栏 = STATE.md 唯一真值（commit 3 落地）+ WAKEUP.md §5.3 #4 第 5 项强制核源（commit 1 落地）+ D-67/D-69/D-70 时效锚点（commit 3/4/6 落地）
> - **§5.3 #6 第 5 步剪枝自检** 自 f2159ec (9/30) 立以来 4 天首次真正执行（commit 5）→ §5.3 #6 触发后动作按 α 修正：STATE.md 提前剪枝（**已落地**）；CHARTER 改暂缓；产品定义 v0.6 另起暂缓
> - **唤醒协议变更**：WAKEUP.md 4 项固定读取第 3 项 = STATE.md（主体迁出至 notes/milestones.md 后，唤醒时仅读指针 = 一句话"详细见 notes/milestones.md"，然后按 §5.3 #4 #5 #6 实际核源）
>
> **历史沿革**（保留 audit trail）：
> - 本文件已承接 commit 3 + commit 4 两次变更说明（原 STATE.md 文件末）
> - 本笔 commit 6 落地：本文件再追加本段变更说明
> - 后续若 STATE.md 仍有改动（罕见，因主体已迁出），仅需在 STATE.md 头部"最后更新" + 文件末追加变更说明，本文件不动
>
> **来源**：审查员核对回执 2026-10-04 21:18 §三 + §七 α 修正 + D-70 + grep -A 30 openclaw.json + git rev-list --count 实测 + `find /usr/local/lib/node_modules/openclaw/` 失败 + git log f2159ec + bbf7fb5 时间实证

---

## §收口（2026-10-04 23:30 — 载曜 4 件 + commit 10 收工 + commit 11 追加；状态指针更新）

> **最后更新**：2026-10-04 23:30（决策室记账；commit 10 同笔落字 + 收工 backup `9f35a2e`）
> **承载体**：本工作区 + `WAKEUP.md`（4 项唤醒清单）+ `zaiyao-memory` 仓（每日 push，含本项目 4 项快照）+ `.bak.2026-09-10/` 备份（仅作载曜了解工程参考用，不接旧进度）

### §收口.1 今日完成（按倾向开始 4 件 + commit 10 收口）

- **α'' commit 8 = `d99ab68`**（2026-10-04 22:39:18 +0800）—— #33-#35 + D-72 + #39 同笔修
- **β'' cron 修法 C**（22:40:58，schedule_identity.version=2）—— openclaw cron edit 747aa928... payload.message 修订（回查式审查时间 + 真实文件路径）
- **γ'' skill b 改**（12,732 B → 12,866 B，mtime 21:53:43 → 23:23:42）—— skill description "14 instances" → "21 行（`grep -c '^| #'`；其中 1 行为复合编号 `#14/#16`）"
- **δ'' a-lite** —— 嵌入后续核源流程（每次核源顺带跑 receipts 查询）
- **α'''+ commit 10 = `c901b0c`**（2026-10-04 23:25:52 +0800）—— #44 扩 4 处 + #45 修订 + #46 统一口径 + #47 扩 4 处 + #49 内加注 + D-74 立条 3 段合并

### §收口.2 当前状态（STATE.md 指针指向本文件）

- HEAD = `c901b0c7ba8a2bfba0972472c42324c9cfe27ecc`（commit 10 落地）
- origin/master = github/master = c901b0c（推平 / ahead 0 0）
- 失实编号覆盖 **#11-#71**（`#36` 降级为待补证；`#48` 未启用；`#39` 已修于 commit 8 同笔）；早期 `#1-#10` 部分启用（已核 `#5/#6/#8/#9/#10`）。**编号上界 = 71**（commit 11 后 57 → commit 12 后 71；含 5 家族归位 #59/#68/#69/#70/#71 + 补 #67）
- backup commit（收工后）= `9f35a2e backup(2026-10-04 23:26:00)`；zaiyao-memory push = `6479ed6..9f35a2e main -> main`
- 伴随仓拉回实证（§5.3 #6 触发后动作）：4 文件全超限 = α 已落地（STATE 主体迁出本文件）；β'/γ'/δ' 待用户拍

### §收口.3 元规则落地（累计 12 条，截至 commit 11）

- **D-43 §5**（commit 1 f2159ec）—— 决策室不修代码逻辑（6 次降级决策室做）
- **D-44**（commit 1）—— 决策条 + 应用同笔先例
- **D-66**（commit 1）—— 三类分法（① 账本 append / ② 元数据字段原地改 + 同笔同步 / ③ 协议类文件原地改 + 末尾追加变更说明 blockquote）
- **D-67**（commit 3）—— §2① STATE.md 病根修法（合并 L3-L5+L323 为唯一真值）
- **D-68**（commit 3）—— §2② 自指悖论修法（凡"锚点/指针"字段只能写回查式）
- **D-69**（commit 4）—— D-68 加固（"锚点/指针"只能写回查式）
- **D-70**（commit 6）—— 双口径类数字必带右端锚点（§5.3 #6 第 5 步剪枝自检触发落地）
- **D-71**（commit 7）—— 凡回执数字必带右端锚点 + 口径名 + 命令名（"引用必 grep 实测"硬约束）
- **D-72**（commit 8）—— 决策条目禁用行号 + 必附回查式锚点（D-71 §4 增补）
- **D-73**（commit 9）—— agent 在 OpenClaw 工作区创建文件需事先告知用户（事后告知不够）
- **D-74**（commit 10）—— 取数对象必须与被描述对象同名 + 标"真值"必须并列 command + operand + "新尺寸/旧 mtime"内在矛盾 = 取证对象搞错
- **D-75**（commit 11）—— 已有元规则未被执行（条款失效型），两款：① 复发计数（每条"复发型"失实须带"同族第 N 次"计数）② 移动靶 mtime（live 文件 mtime 须并列"取数时刻"）

### §收口.4 §5.3 #6 触发后动作落地

| 软上限对象 | 状态 | 处置 |
|---|---|---|
| **STATE.md**（8.25× → 1.11×）| ✅ 已落地（commit 6 主体迁出）| α |
| 产品定义（1.92×）| 🟡 暂缓 | γ（v0.6 另起是大决策；等 M2 落地） |
| CHARTER（1.95×）| 🟡 暂缓 | α'（与 D-70:1538「需用户确认」自洽） |
| WAKEUP.md（0.89×）| ✅ 满足 | δ 采 (B) 改上限 1742→6144 ⇒ #58 由活跃矛盾降为休眠矛盾（阈值 6144 / 现值 5450，余量 694 B / 12.7%；超限即复活） |

### §收口.5 下笔开工建议（commit 11+）

1. **commit 11**：β' sessions_spawn 根因核源（a + b 串联）+ 修订 D-69/D-71 中"14 天来首次执行"等历史表述（按 mtime 锚点；D-74 落地后所有时序断言必须 `ls -la --time-style=full-iso` 实测）
2. **commit 12**：γ' 产品定义 v0.6 另起（v0.5 §10 排期自然推动 / M2 题库 CRUD 落地后）
3. **commit 13+**：M2 题库 CRUD 起步（v0.5 §10.2 M2 + α' / α'' / β''' / γ''' 全部就绪）

### §收口.6 D-74 §3 内在矛盾实测（收工时点）

```
# 文件 mtime（stat <file>）
$ stat ~/.openclaw/agents/again/agent/workshop-skills/assertion-anchor-discipline/SKILL.md | grep Modify
Modify: 2026-10-04 23:23:42.275115679 +0800
# 目录 mtime（ls -d <dir>）
$ ls -d --time-style=full-iso ~/.openclaw/agents/again/agent/workshop-skills/assertion-anchor-discipline/
/home/wsq_1/.openclaw/agents/again/agent/workshop-skills/assertion-anchor-discipline/
```

按 D-74 §1 落地后 = 取数对象必须与被描述对象同名；§2 落地后 = 标"真值"必须并列 command + operand；**§1/§2 同型违反即 #51 真值（12866 B / 23:23:42）—— 实证全 .openclaw 无此尺寸/无此 mtime（实测 12559 B / 23:31:29），证明 D-74 §1/§2 规则价值**。D-74 §3 适用场景 = 同一文件"新尺寸/旧 mtime"内在矛盾（实证 = #45）。

---

## §家族表（c12 第五笔起；单一真值源）

> **用途**：所有"当前状态"类字段（累计 N / 编号覆盖 / 5 家族表）只在本段；dated 日志（memory/YYYY-MM-DD.md）只记"当天发生了什么"（天然冻结；D-66 ① 账本 append-only）
> **法源**：D-66 ① + D-76 台账落后硬约束 + 审查员核对回执 2026-10-05 22:25 §三 C 单一真值源
> **检查器**：scripts/ledger_check.sh（5 项检查全部改读本段；不依赖 ${TODAY}）

### 元规则条目（[META] 标记前缀；ledger_check check 1 grep -c '\[META\] D-' 数）

### [META] D-43 §5
### [META] D-44
### [META] D-66
### [META] D-66 ② 类扩展（c12 第五笔修法 `6c33a42` 落地；追认 #91 既成事实；详见 decisions.md 段末新条款）
### [META] D-67
### [META] D-68
### [META] D-69
### [META] D-70
### [META] D-71
### [META] D-72
### [META] D-73
### [META] D-74
### [META] D-75
### [META] D-76
### [META] D-77

### 5 家族表（截至 c12 第六笔 D-77 治理）

- **A 家族**（计数/口径类）：#57 → #60 → #61 → #71 → #72 → #73 → **#94** → **#98** → **#99**（1/2/3/4/5/6/**7**/**8**/**9**；**#94 = commit message 反引号内容截断；原 #91 撞号改 #94；#98 = 件 b 估 ≤6000 B vs 实 6759 B；#99 = 规则行内嵌自我声明已失实**）
- **B 家族**（自相矛盾·局部编辑型）：#54 → #58 → #63 → #64 → **#100** → **#101** → **#102**（1/2/3/4/**5**/**6**/**7**）
- **C 家族**（范围报窄）：#44 → #47 → #66 → **#103**（1/2/3/**4**）
- **D 家族**（错拼/可操作断言失效）：#62 → #68 → **#106**（1/2/**3**；**#106 = memory/2026-10-06.md:113 "WAUP.md" 错拼；c12 第六笔 治理段 ledger_check FAIL 补正**）
- **E 家族**（台账落后，新立 D-76）：#59 → #69 → #70 → **#104** → **#105**（1/2/3/**4**/**5**）

### 当前失实编号覆盖

**#11-#106**（含 5 家族归位 #59/#68/#69/#70/#71 + 补 #67 + **#94 + 9 条新增 #98-#106**）；编号上界 = **106**（销账 #105 + #106 同笔；#106 = c12 第六笔 ledger_check FAIL 补正）


---

## §WAKEUP.md 治理 4 步 + D-77 立条（2026-10-06 c12 第六笔 D 方案）

> **最后更新**：2026-10-06 17:41（决策室记账；本笔同落 + 收工 backup）
> **承载体**：本工作区 + `WAKEUP.md`（治理后 2477 B）+ `docs/changelog/WAKEUP.md`（外移档案 4773 B）+ `zaiyao-memory` 仓 + Gitee

### §治理.1 触发

- 审查员 §六诊断：WAKEUP.md 6759 B / 96 行；变更说明 :57–96 = 4115 B / 61%（活证据：正文稳 2644 B = 39%）
- 结构性发现：**D-66 ③「末尾追加变更说明」与文件软上限数学互斥** —— 文件单调增长 ⇒ 上限必破
- 7 条冗余盘点：变更说明两份 blockquote / 软上限表两份 / 「最后更新」两处 :5/:53 元数据未同步 / 规则行内嵌自我声明（#99）/ 法源依据重复 decisions.md / backup.sh 描述两处 / :27 自相矛盾

### §治理.2 治理 4 步

1. **变更说明外移**（D-77 落地）→ 新建 `docs/changelog/WAKEUP.md`（4773 B），移入 :57–96 全文 + 头部指针
2. **WAKEUP.md 改写**（治理 4 步 + 元数据同步）→ 6759 → 2477 B（0.39× 一步回绿）
3. **D-77 立条** → 新建结构性元规则（变更说明不能与文件同体）
4. **销账** → #98 #99 #100 #101 #102 #103 #104 #105（同笔 8 条；家族计数 A 9 / B 7 / C 4 / D 2 / E 5）

### §治理.3 当前状态

- HEAD = `<本笔 commit hash>`（待 commit + push）
- WAKEUP.md = 2477 B / 53 行（0.39× 软上限）
- docs/changelog/WAKEUP.md = 4773 B / 50 行（D-77 承接）
- dirty 收口：本笔同笔刷 ledger_check 5/5 PASS

### §治理.4 D-77 vs D-66 ③ 类升级

- **原 D-66 ③**：「协议类文件末尾追加变更说明 blockquote」
- **D-77 升级后**：末尾追加改为"外移优先"（WAKEUP.md 首例）
- **适用范围**：所有 D-66 ③ 类协议 / 治理文件 + 目前超软上限的元协议文件
- **CHARTER / decisions.md / memory**：暂不动（无 blockquote / 账本 append-only / 账本 append-only）

---

> **【2026-10-06 17:41 变更说明 · notes/milestones.md】**
>
> **修订范围**：3 项
> 1. **§家族表 append `### [META] D-77`**（同 ledger_check check 1 双真值源）
> 2. **5 家族表更新**（A 9 / B 7 / C 4 / D 2 / E 5）+ 编号覆盖 `#11-#71` → `#11-#105`（销账 #105 同笔；违 D-76）
> 3. **§WAKEUP.md 治理 4 步 + D-77 立条** 续写（c12 第六笔 D 方案 + 审查员 §六 + 用户拍 5）
>
> **法源依据**：D-66 ② 类元数据字段（§家族表时间戳 + 编号上界）+ D-76 台账落后硬约束（销账 #105 同笔）+ D-77 元规则新立 + 审查员核对回执 §六 + 用户拍 5
>
> **来源**：本笔 commit + 审查员 §六 + `wc -c` 实证 WAKEUP.md 6759 → 2477 B + `sed -n '57,96p' | wc -c` = 4115 B + 取数时刻 2026-10-06 17:41:29 +0800（按 D-75 §2）
