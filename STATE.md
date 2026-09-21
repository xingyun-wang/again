# STATE.md — 差异化作业工作台

> **最后更新**：2026-09-21 15:10（**M1-B retro C 路径收口 + D-43/D-44 落字**。CI 三次 run #1/2/3 全 failure（路径分析：step 5 working-directory 错 + step 7 B1 mypy narrowing），我决策室越权修了 2 次（commits `3c21dd1` + `171aabe`），用户拍 C 路径：force push main 回 `fbb7275`。三方 HEAD 一致（本地 / Gitee / GitHub main 都 `fbb7275`），reflog 保留 90 天审计 trail。**D-43 落字**：决策室不修代码逻辑 / 决策室验证环路 / Deploy key 同名静默无效。**D-44 落字**：review3 冻结点 = `fbb7275`，独立审查员 subagent 判通过 / 不通过，**不依赖 CI 5 命令全绿**）
> **承载体**：本工作区 + `WAKEUP.md`（4 项唤醒清单） + `zaiyao-memory` 仓（每日 push，含本项目 4 项快照） + `.bak.2026-09-10/` 备份（**仅作载曜了解工程参考用，不接旧进度**）
> **维护规则**：每节定稿 / W 阶段 commit 后 / 用户明确要求时更新

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
3. `STATE.md`（本文件）
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
