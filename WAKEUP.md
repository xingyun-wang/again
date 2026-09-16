# WAKEUP.md — 唤醒后固定读取清单

> **用途**：每次 reset 后唤醒载曜，**首先读这 4 项**，然后第一句话汇报："上次停在 X，下一步 Y，开放问题 Z"（不复述内容）。
> **维护**：剪枝触发时立即更新本文档。
> **最后更新**：2026-09-14

---

## 4 项固定读取

1. **产品定义** → `docs/产品定义-v0.5.md`
2. **最近 3 天项目日志** → `memory/2026-09-12.md`、`memory/2026-09-13.md`、`memory/2026-09-14.md`（不存在的跳过）
3. **进度** → `STATE.md`
4. **宪法** → `docs/PROJECT-CHARTER.md`

读完后第一句（不复述）：「上次停在 X，下一步 Y，开放问题 Z」

---

## 剪枝触发（任一超限 → 立即剪）

| 文件 | 软上限 | 超出动作 |
|---|---|---|
| `docs/产品定义-v0.5.md` | 15KB | v0.5 已定稿基本不增；v0.6 另起新文件 |
| `memory/YYYY-MM-DD.md`（单日） | 100 行 | 次日收工时压缩为要点 |
| `STATE.md` | 3KB | 移到 `notes/milestones.md` |
| `docs/PROJECT-CHARTER.md` | 5KB | 改 = 大事件，需用户确认 |

---

## 收工后必须做的事

1. 更新今天的 `memory/YYYY-MM-DD.md`（写今天做了什么 / 下一步）
2. 改 `STATE.md`（如有进展）
3. 跑 `bash ~/zaiyao-memory/backup.sh`（自动同步 + 推送 Gitee）
4. 报告 push 成功/失败

---

## 灾难恢复

- **执行者**：`~/zaiyao-memory/backup.sh`
- **远端**：`git@gitee.com:wang-xingyun1021/zaiyao-memory.git`
- **本项目备份位置**：`projects/tiered-homework-platform/`（zaiyao-memory 仓内）
- **备份内容**：WAKEUP.md / STATE.md / 产品定义 v0.5 / 宪法 / 最近 3 天日志

---

**最后更新**：2026-09-14（v0.5 §0-§5 定稿 + 4 项唤醒机制建立）
