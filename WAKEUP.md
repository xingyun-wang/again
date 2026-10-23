# WAKEUP.md — 唤醒后固定读取清单

> **用途**：每次 reset 后唤醒载曜，**先读第 0 步信箱 + 下面 4 项**，然后第一句话汇报："上次停在 X，下一步 Y，开放问题 Z"（不复述内容）。
> **维护**：剪枝触发时立即更新本文档。
> **最后更新**：2026-10-23 23:4x（信箱第 0 步 + Windows 侧备份入清单 + 剪枝；详见 `docs/changelog/WAKEUP.md`）

---

## 4 项固定读取 + 1 项核源动作

0. **⭐ 读信箱（2026-10-23 立；星轨《约定-信箱与回执》）**：`/mnt/c/Users/wsq_1/WorkBuddy/我的DA系统/交付物/OUTBOX-星轨致载曜.md`
   - 有新序号 ⇒ **先回 INBOX**（`INBOX-载曜致星轨.md`，整份覆盖，首行必须 `已读 OUTBOX #N @ 时间`）再动手
   - 无新序号 ⇒ 继续原流程
   - 约定全文：同目录 `约定-信箱与回执（2026-10-23）.md`（**只读**）

1. **产品定义** → 摘要页 `docs/产品定义-v0.5-summary.md`（D-78 首次落地；c18）+ 全文按需展开 `docs/产品定义-v0.5.md`
2. **最近 3 天项目日志** → `memory/` 下按文件名字符序（YYYY-MM-DD.md）取最新 3 个文件
3. **进度** → `STATE.md`
4. **宪法** → 摘要页 `docs/PROJECT-CHARTER-summary.md`（D-78 二次落地；c19）+ 全文按需展开 `docs/PROJECT-CHARTER.md`（§7 流程外移至 `docs/PROJECT-CHARTER-protocol.md`；按 D-79）
5. **核源动作**（防御"凭印象报告"硬护栏；D-43-X 系列实战失实催生）→ `git -C <repo> rev-parse HEAD` + `git log --oneline -5` + `git status --porcelain`；**第一句 X/Y/Z 的取值以 `STATE.md` 为准**，当日日志只作过程参考（含旧段，会过期）

读完后第一句（不复述）：「上次停在 X，下一步 Y，开放问题 Z」

---

## 剪枝触发（任一超限 → 立即剪）

| 文件 | 软上限 | 超出动作 |
|---|---|---|
| `docs/产品定义-v0.5.md` | 15KB | 已定稿；v0.6 = 修订轮（D-65） |
| `memory/YYYY-MM-DD.md`（单日） | 100 行 | 次日收工时压缩为要点 |
| `WAKEUP.md` | 6144 B | 软上限；超限即剪（D-77：变更说明外移到 `docs/changelog/WAKEUP.md`） |
| `STATE.md` | 3KB | 移到 `notes/milestones.md` |
| `docs/PROJECT-CHARTER.md` | 5KB | 改 = 大事件，需用户确认 |

---

## 收工后必须做的事

> **本节 = 项目内收工流程唯一真值源**（D-79）
> **链序**：落盘 → 固化 → 核 → 推；**当前步骤数**：9
> **2026-10-23 新增**：第 4 步 = 运行时证据落盘（星云 09:57「机制立」）

1. **更新 memory**：`memory/YYYY-MM-DD.md`（写今天做了什么 / 下一步）
2. **改 STATE**：`STATE.md`（如有进展）
3. **剪枝自检（含压缩昨日日志）**：
   - `wc -c` 各文件比软上限（详见 §剪枝触发）
   - **压缩昨日日志**（按 WAKEUP.md:26「memory 单日 100 行 → 次日收工时压缩」；D-75/D-76）
4. **写运行时证据**：落 `交付物/运行时证据-<短sha>.md`；未覆盖声明/更正落 `交付物/未覆盖声明-<主题>-<短sha>（<日期>）.md`
   - **必须在 commit 之前写** —— 命令原始输出事后无法重建（L1 不可追认）
   - **证据分级 L1–L4 必标**（原始输出 / 事后可重放 / 事后转述 / 未留存）；**L4 一律写「未留存」**；L3 必须标出
   - **页面级证据永远为 0**（无浏览器，截图就是伪造）⇒ 一律写「归星轨 Playwright + Edge」
   - 机制全文：`交付物/README.md`
5. **commit**：本笔改动落到项目仓（commit message 写明类型 + 范围 + D-XX 引用）
6. **跑 ledger_check**：`bash scripts/ledger_check.sh`（**失败即拒收**；D-76；失败 → 立即补 fix commit，**且不得执行第 8 步 push**）
7. **跑 backup**：`bash ~/zaiyao-memory/backup.sh`（自动同步 + 推送 Gitee；D-14）
8. **推 origin**（需授权）：`git push origin <branch>`
   - **授权机制** = 本笔 commit message 显式含 `[origin-push]` 标记；**无标记** = 不推
   - **机器核验** = `git log -1 --format=%B | grep -q '\[origin-push\]'`（第 6 步前自检）
9. **报告 push**：报告 backup + origin push 成功/失败

---

## 灾难恢复（与日常备份分开；仅在项目仓丢失/不可用时执行）

- **执行者**：手动（`git clone` + `cp`）；**触发**：项目仓 `git status` 不可用 / 工作树不可恢复 / 备份快照整体失联
- **远端**：`git@gitee.com:wang-xingyun1021/zaiyao-memory.git`；**本项目位置**：`projects/tiered-homework-platform/`（zaiyao-memory 仓内）
- **备份内容**：**以 `backup.sh` 实际同步为准**（脚本里是清单式配置，勿在本文复制清单）
  - 项目侧：`WAKEUP.md` / `STATE.md` / `docs/产品定义-v0.5.md` / `docs/PROJECT-CHARTER.md` /
    `scripts/ledger_check.sh` / `memory/*.md`（最近 3 天）/ `plans/*.md` / `notes/**/*.md`
  - **Windows 侧 `我的DA系统/`**（2026-10-23 加）→ `projects/da-system/`：
    `交付物/`（242 个 .md，**含信箱**）+ `.workbuddy/memory/` + `工具/` + `归档/` + 两个根级 .md
    —— 那侧 `git remote -v` 为空（**零异地副本**）；代码仓 `交付物/` 已双端推 ⇒ 不重复备份
- **代码不在备份内**：项目代码（backend/ frontend/ tests/ 等）靠 origin 仓；本备份不含代码。
- **步骤**：
  1. `git clone git@gitee.com:wang-xingyun1021/zaiyao-memory.git ~/zaiyao-memory`
  2. 从 `~/zaiyao-memory/projects/tiered-homework-platform/` 拷回项目根（同上清单）
  3. 项目仓 `git status` + `git diff` 验证恢复结果
- **与日常备份区别**：日常备份（收工第 7 步）= `backup.sh` **推**出去；灾难恢复（本节）= **拉**回来

---

**变更说明**：见 `docs/changelog/WAKEUP.md`（D-77 元规则；变更说明不能和它所描述的文件同体）
