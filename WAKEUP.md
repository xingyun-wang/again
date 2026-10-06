# WAKEUP.md — 唤醒后固定读取清单

> **用途**：每次 reset 后唤醒载曜，**首先读这 4 项**，然后第一句话汇报："上次停在 X，下一步 Y，开放问题 Z"（不复述内容）。
> **维护**：剪枝触发时立即更新本文档。
> **最后更新**：2026-10-06 17:41（D-77 治理 4 步落地；销账 #98-#104；详见 `docs/changelog/WAKEUP.md`）

---

## 4 项固定读取 + 1 项核源动作

1. **产品定义** → 摘要页 `docs/产品定义-v0.5-summary.md`（D-78 首次落地；c18）+ 全文按需展开 `docs/产品定义-v0.5.md`
2. **最近 3 天项目日志** → `memory/` 下按文件名字符序（YYYY-MM-DD.md）取最新 3 个文件
3. **进度** → `STATE.md`
4. **宪法** → `docs/PROJECT-CHARTER.md`（§7 流程外移至 `docs/PROJECT-CHARTER-protocol.md`；按 D-79）
5. **核源动作**（防御"凭印象报告"硬护栏；D-43-X 系列实战失实催生）→ `git -C <repo> rev-parse HEAD` + `git log --oneline -5` + `git status --porcelain`

读完后第一句（不复述）：「上次停在 X，下一步 Y，开放问题 Z」

---

## 剪枝触发（任一超限 → 立即剪）

| 文件 | 软上限 | 超出动作 |
|---|---|---|
| `docs/产品定义-v0.5.md` | 15KB | v0.5 已定稿基本不增；v0.6 = 产品定义修订轮（D-65） |
| `memory/YYYY-MM-DD.md`（单日） | 100 行 | 次日收工时压缩为要点 |
| `WAKEUP.md` | 6144 B | 软上限；超限即剪（D-77：变更说明外移到 `docs/changelog/WAKEUP.md`） |
| `STATE.md` | 3KB | 移到 `notes/milestones.md` |
| `docs/PROJECT-CHARTER.md` | 5KB | 改 = 大事件，需用户确认 |

---

## 收工后必须做的事

1. 更新今天的 `memory/YYYY-MM-DD.md`（写今天做了什么 / 下一步）
2. 改 `STATE.md`（如有进展）
3. 跑 `bash scripts/ledger_check.sh`（自动核验台账；**失败即拒收**；D-76 立条 + 5 条检查项：台账增量 / 失实入家族表 / W-A-U-P.md 错拼 / notes-memory 对齐 / dirty 收口）
4. 跑 `bash ~/zaiyao-memory/backup.sh`（自动同步 + 推送 Gitee；D-14）
5. 报告 push 成功/失败
6. **剪枝自检**：`wc -c` 各文件比软上限（详见 §剪枝触发）

---

## 灾难恢复

- **执行者**：`bash ~/zaiyao-memory/backup.sh`
- **远端**：`git@gitee.com:wang-xingyun1021/zaiyao-memory.git`
- **本项目备份位置**：`projects/tiered-homework-platform/`（zaiyao-memory 仓内）
- **备份内容**：WAKEUP.md / STATE.md / 产品定义 v0.5 / 宪法 / 最近 3 天日志

---

**变更说明**：见 `docs/changelog/WAKEUP.md`（D-77 元规则；变更说明不能和它所描述的文件同体）
