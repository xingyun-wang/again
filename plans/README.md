# plans/ — active subagent briefs

> **最后更新**：2026-09-23（与 N-3 处置同步建立）
> **维护**：工地 commit 时负责；决策室不动

## 用途

短期活跃 brief（subagent 任务 brief）的暂存区，commit 后归档到 `docs/reviews/<date>-<name>-archived.md`。

## 命名规则

`<milestone>-<task>-brief.md`

- `milestone`：当前 v0.5 §10 里程碑（M0 ~ M7）+ 内部子里程碑（M2-A.0 等）
- `task`：单条 subagent 任务的简述
- `brief`：固定后缀，标识这是 subagent brief 而非审查报告

## 何时归档

- **commit merged 之后**：brief 对应的 commit 已 merge 到 master → 移到 `docs/reviews/<commit-date>-<name>-archived.md`
- **commit 被弃用**：brief 对应的 commit 被 force push 移除或回滚 → 同样归档（保留审计 trail）
- **commit 长期未交付（> 14 天）**：决策室决定是继续推进还是归档

## 归档责任

- 工地 subagent 在 commit 完成后立即归档自己的 brief
- 决策室不直接动 `plans/` 内容（除 README 本身外）
- 归档 = `git mv` + `git commit`（与 commit 同一笔，或紧接 commit 下一笔）

## 当前活跃 brief

| 文件 | 对应 commit | 状态 |
|---|---|---|
| `m2-a0-question-crud-brief.md` | `3ccdf29` (M2-A.0) | 已落地（commit merged），待归档 |

## 与 reviews 目录关系

| 目录 | 内容 | 时效 |
|---|---|---|
| `plans/` | 活跃 brief（commit 未落地或刚落地） | 短期 |
| `docs/reviews/` | 已归档审查 + 已归档 brief | 长期（审计 trail） |

## 未来警惕

- **未跟踪 = 下次报告丢失**：plans/ 必须 git add 跟踪，不要 .gitignore 屏蔽
- **未归档 = 漂移堆积**：commit 后不归档 → plans/ 越长越乱，未来载曜不知道哪些还活跃
- **与 D-39-X 关系**：brief 归档到 `docs/reviews/` 后，brief 文件路径成为审查报告可引用的 baseline 类资源

## 来源

外部核源回执 2026-09-23 §N-3。