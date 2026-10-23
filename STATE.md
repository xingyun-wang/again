# STATE.md — 差异化作业工作台

> **最后更新**: 2026-10-24 00:5x（**1c-2 commit1 前端材料层已落地并自验**）
> **1a-2 ✅ ｜ 1c-2 commit1 ✅ 代码落地（页面级待星轨）｜ commit2 ⬜ ｜ P2 欠账 ×5 已登记**
> **⭐ 详细历史** ⇒ `notes/milestones.md` **§12**（2026-10-24 剪枝迁入，原文一字未删）｜变更说明 ⇒ `notes/changelog/STATE.md`（D-77）

## 一、当前状态

| 项 | 状态 | 关键事实 |
|---|---|---|
| **1a-2 题组+块表+API** | ✅ 完成 | `e736e17`/`ba7874a`/`4531fa8`；3 新表 + 10 端点 |
| **审查批 1 `ab02079..e11de97`** | ✅ 2×P1 已返工 | `d3621a1`；0×P0/2×P1/5×P2/1×P3 |
| **1c-2 commit1 前端材料层** | ✅ 代码落地，**页面级未验** | 7 文件；三查绿；镜像 `index-0UYgtwcd.js` 已上线；**9 项页面级待星轨** |
| **1c-2 commit2** | ⬜ 未开始 | 后端三处 + 内联小题 + 列表题组行 + 删组确认 |
| **P2×5 / P3×1** | 📌 已登记 | `docs/review-debt.md`（带触发时机；**不自行降级**） |

## 二、新增两条硬约束（其余见 workspace `AGENTS.md` 协作纪律）

1. **未知 `block_type` 绝不能写回** —— `PUT` 的 blocks 是**整体替换** ⇒ 认不出的块若当普通块写回
   = **静默改写那块数据**。前端已做「显式 Alert + 阻断保存 + `blockToInput` 兜底抛错」。
2. **pytest 只能在容器内跑** —— 宿主 py3.8 因 PEP 585 在**收集期**炸，**报错在 `app/models/`**
   ⇒ 长得像「我的改动炸了」。护栏在 `backend/tests/conftest.py:26-27`。

## 三、下一步（Y）

1. **1c-2 commit2**（后端三处 + 内联新建小题 + 列表题组行 + 删组二次确认）。
2. 补 commit1 的两个入口缺口：**编辑态入口** + **刷新后重开题组**（现只有抽屉内「重新加载」）。
3. **等星轨的 9 项页面级结论**（Playwright + 系统 Edge）⇒ **不由我下**。
4. P2 欠账 5 条：按 `docs/review-debt.md` 触发时机推进。

## 四、开放问题（Z）

- **换图在组图达上限时做不成**（后端 ≤10 张硬校验 vs 旧图保存后才删）⇒ 需后端同请求内替换。
- **`GET /question-groups` 不支持分页/排序** ⇒ commit2 列表页要分页需后端补参数。
- **`ContentBlockRead.block_type` 是裸 `str`** ⇒ 前端已兜；建议后端改 Literal（commit2）。
- **`docs/PROJECT-CHARTER.md` 5753B / 5120B 超限** ⇒ 按 WAKEUP「改 = 大事件需用户确认」⇒ **我没动，待星云拍板**。
- **「保存后抽屉不自动关闭」**（与 `QuestionDrawer` 不同）⇒ 冲突请指示即改成保存即关。

## 五、承载体

`WAKEUP.md`（4 项唤醒 + 9 步收工链）｜ `notes/milestones.md`（§12 详史）｜ `notes/changelog/STATE.md`（D-77）
｜ `zaiyao-memory` 仓（每日 push）｜ `docs/review-debt.md`（P2/P3）｜ `交付物/运行时证据-*.md`（L1–L4）

> **维护规则**：每节定稿 / W 阶段 commit 后 / 用户明确要求时更新
> （主体已迁出至 `notes/milestones.md` §12）
