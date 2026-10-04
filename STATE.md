# STATE.md — 差异化作业工作台

> **最后更新**：2026-10-04 21:18 — commit 6（修 §5.3 #6 触发后动作：STATE.md 主体移到 `notes/milestones.md` + reviews/2026-10-04-ab02079-owner-isolation.md :19/:43 Question 行双推归档修订 + 失实 #24/#25/#26/#27 落字 + D-70 立条 + sessions_spawn 核源更彻底）；本笔锚点 = 含本行的 commit，回查 `git log -1 --format=%h -- STATE.md`
> **详细历史**：见 `notes/milestones.md`（一页纸摘要 / 硬约束 / 工作约定 / 链接索引 / session 启动清单 / §10 排期快照 / 反思与元规则 / 收口轨迹 / 收口决策书接住 + 接受率 backlog / 文件末变更说明）
> **承载体**：本工作区 + `WAKEUP.md`（4 项唤醒清单） + `zaiyao-memory` 仓（每日 push，含本项目 4 项快照） + `.bak.2026-09-10/` 备份（**仅作载曜了解工程参考用，不接旧进度**）
> **维护规则**：每节定稿 / W 阶段 commit 后 / 用户明确要求时更新（主体已迁出至 notes/milestones.md；本文件后续仅做指针更新 + 变更说明 blockquote 追加）

---

> **【2026-10-04 21:18 变更说明 · STATE.md】**
>
> **修订范围**：1 项结构重组 + 失实 #24-#27 落字
> 1. **STATE.md 主体 → 迁出至 `notes/milestones.md`**（D-66 ② 类元数据字段；§5.3 #6 触发后动作按审查员核对回执 2026-10-04 21:18 §七 α 修正"不需用户确认"提前做；STATE.md 超 8.25× → 瘦身到 ~3 KB 范围）
> 2. **失实 #24-#27 落字**（D-43-X-3 段 append；commit 6 同步）
>
> **法源依据**：
> - **D-70**（2026-10-04 立，本笔同落）= 双口径类数字必带右端锚点 + STATE.md 重组 + 失实 #24 双推归档修订
> - **D-69**（2026-09-30 立）= 凡"锚点/指针"字段只能写回查式
> - **D-67**（2026-09-30 立）= §2① STATE.md 病根修法（commit 3 落地）
> - **D-43-X-3**（2026-09-27 立）= 实战失实落字
> - **审查员核对回执 2026-10-04 21:18 §三 订正 1+2+3 + §七 α 修正**
>
> **影响范围**：
> - **失实 #11/#24/#25/#26 物理病根修复路径闭环**：双护栏 = STATE.md 唯一真值（commit 3 落地）+ WAKEUP.md §5.3 #4 第 5 项强制核源（commit 1 落地）+ D-67/D-69/D-70 时效锚点（commit 3/4/6 落地）
> - **§5.3 #6 第 5 步剪枝自检** 自 f2159ec (9/30) 立以来 4 天首次真正执行（commit 5）→ §5.3 #6 触发后动作按 α 修正：STATE.md 提前剪枝（**已落地**）；CHARTER 改暂缓；产品定义 v0.6 另起暂缓
> - **唤醒协议变更**：WAKEUP.md 4 项固定读取第 3 项 = STATE.md（主体迁出至 notes/milestones.md 后，唤醒时仅读指针 = 一句话"详细见 notes/milestones.md"，然后按 §5.3 #4 #5 #6 实际核源）
>
> **历史沿革**（保留 audit trail）：
> - `notes/milestones.md` 已承接 commit 3 + commit 4 两次变更说明（原 STATE.md 文件末）
> - 本笔 commit 6 落地：`notes/milestones.md` 文件末追加本笔变更说明（§五来源同段）
> - 后续若 STATE.md 仍有改动（罕见，因主体已迁出），仅需在 STATE.md 头部"最后更新" + 文件末追加变更说明，notes/milestones.md 不动
>
> **来源**：审查员核对回执 2026-10-04 21:18 §三 + §七 α 修正 + D-70 + grep -A 30 openclaw.json + git rev-list --count 实测 + `find /usr/local/lib/node_modules/openclaw/` 失败 + git log f2159ec + bbf7fb5 时间实证
