# M3-B1 brief: IA-1 一级导航 + 9 路由归位

> **派工人**：载曜｜**派工日**：2026-10-19｜**批准**：星云（"B1, B2, D2 可以起"）
> **阻塞**：无（与 A2/C1 不冲突；可立即起）
> **回执 commit message 必带**：`[origin-push]`（WAKEUP 8 步授权机制）

---

## §1 任务

- **新建** `frontend/src/components/Layout.tsx`（含 **4 项一级导航** = 备课 / 出作业 / 学情 / 设置）
- **9 路由归位** = 把现有 9 路由**全部**包到 Layout 下（用 `<Outlet />`）
- **不动** 现有 9 路由的具体内容（保持 placeholder；不删 / 不改 children）

## §2 一级导航 4 项（4 法核源 + 行为）

| 4 项 | 跳到 | 理由 |
|------|------|------|
| **备课** | `/import` | 外部题库导入 = 教师备课辅助（M2 已有；最近可用入口） |
| **出作业** | `/assignments` | 作业生成 + 审阅 + PDF（M2 已有；核心入口） |
| **学情** | `/`（首页 + tooltip "M3 不做学情"）| 交接书 §7 第 3 条 = 不动学情页 |
| **设置** | `/questions` | 题库 CRUD = 老师个人设置（M2 已有；题库 = 老师资产） |

**Layout 形态**：左侧 Sidebar 含 4 项导航；右侧主区 `<Outlet />` 显示当前路由。

**不动**的事项（4 边界）：

- 不动学情页（不新建 `/learning` 路由；首页占位）
- 不动 API（不改任何后端）
- 不改后端路由 / 模型 / 迁移
- 不动 batch 业务（0012 迁移 = A2 工作；不抢跑）

## §3 4 法核源（必跑 + 必报）

| 项 | 文件 / 实际 | 4 法核源结果 |
|----|------|---------------|
| 现有 router | `frontend/src/router/index.tsx:24-34` 9 路由 | 已核源（9 行 `{ path, element }`） |
| 现有 Layout / Sidebar / Menu / Nav | `find frontend/src -type f \( -name "*Sidebar*" -o -name "*Menu*" -o -name "*Layout*" -o -name "*Nav*" \)` | **空 = 无现有 layout 文件 = Layout 是新建** |
| 现有 9 pages | `frontend/src/pages/{Home,Questions,Import,Tiering,AntiMatthew,TierOverride,Assignments,Review}.tsx` | 已存在 8 个（M1/M2 期间） |
| Layout 用什么 | React Router v6 的 `Outlet` + `react-router-dom` 已用（router/index.tsx:1）| OK |

## §4 必报项（per D-43-X = 4 法核源 + 运行时证据）

1. **CI run #**（lint + tsc + build）+ commit SHA
2. **Layout.tsx 实际行数** + 4 项导航项 grep 截图
3. **9 路由仍在**（`grep -c "{ path:" frontend/src/router/index.tsx` = 9）
4. **Outlet 包裹证据**（grep `<Outlet />` 在 Layout.tsx）
5. **运行时证据**（dev 启动 + 4 项导航可见 / React DevTools 截图 / 浏览器 HTML 渲染）
6. **git status + diff stat**（期望 ≥ 1 新文件 Layout.tsx + 1 改 router/index.tsx；**不动 9 路由 children**）

## §5 派工回执必带（**不写 = 拒收**）

- commit SHA
- CI run #（lint + tsc + build + 已有 test）
- Layout.tsx 实际行数 + 4 项 grep 输出
- 9 路由 grep 输出（期望 9 条 `{ path:`）
- Outlet grep 输出
- 运行时证据（dev 启动 + 4 项导航可见 / React DevTools 截图 / 浏览器 HTML 渲染）
- 4 边界自查清单（不动学情 / 不动 API / 不改后端 / 不动 batch）
- 报告命令用 4 法核源（**不写"我以为"**）

## §6 同步说明（**不需要 subagent 做**）

- A1+1 commit `f032607` 已落；P3-3 修了"§3.2 D2 = 无依赖"
- D2 (W5 PDF 嵌图) 现在可立即起（与本 brief 独立；不抢跑）
- A2 (0012 brief) 排在 A1 批后；本 brief 不抢 A2 工作

---

> **【2026-10-19 14:4x 变更说明 · plans/M3-B1-IA1-brief.md】**
>
> **修订**：新建（M3 派工 brief；A1+1 后可起；星云 14:37 批 "B1, B2, D2 可以起"）
> **内容**：1 任务 / 2 4 项 / 3 4 法核源 / 4 必报项 / 5 派工回执 / 6 同步
> **法源依据**：
> - 交接书 §4（IA-1 排在并行段；不阻塞切片）
> - A1+1 commit `f032607` P3-3 修了 D2 依赖（与 B1 独立）
> - 决策记录 §七 决策 1-20（IA-1 不抢 0012 工作）
> - D-17（subagent 写代码 / 主聊天不写大段）
> - D-43-X（4 法核源 + 运行时证据；拒收"已支持"字样）
> - §治理.19（容器 pytest 显式切测试库；前端无 dev 库污染问题）
> **派工范围**：仅前端 Layout + router 改；其他文件不动
> **来源**：A1+1 commit `f032607` + 核源 exec 输出（router/index.tsx 9 路由 + 无现有 layout）
