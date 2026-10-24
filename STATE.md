# STATE.md — 差异化作业工作台

> **更新**: 2026-10-24 23:5x（**1c-2 欠账 P2/P3 修完 + 批 1 六条欠账全清**）
> **1a-2 ✅ ｜ commit1 ✅ ｜ T1 P1 ✅ ｜ commit2 ✅ ｜ 批 1 全清**
> **详史** ⇒ `notes/milestones.md` **§15**（本轮）/ §14 / §13 / §12

## 一、当前状态

| 项 | 状态 | 关键事实 |
|---|---|---|
| **1a-2 题组+块表+API** | ✅ 完成 | 3 新表 + 10 端点 |
| **审查批 1** | ✅ **2×P1 + 5×P2 + 1×P3 全清** | 0×P0 |
| **1c-2 commit1 前端材料层** | ✅ 星轨已签收 | C/H 过 |
| **1c-2 T1 P1（取消⇒孤儿图）** | ✅ 星轨已核（双绿） | 取消后 `GET /images`=0 |
| **1c-2 commit2** | ✅ 代码落地，**页面级待星轨** | 内联小题 + 题组行 + 删组确认；379 passed |
| **1c-2 欠账 P2/P3** | ✅ 代码落地，**页面级待星轨** | P2 列表刷新 + P3 裁 `?force=true`；383 passed |
| **P2 欠账** | ✅ **批 1 六条全清** | `docs/review-debt.md` |

## 二、硬约束（全文见 §15）

1. **未知 `block_type` 绝不能写回** —— `PUT` 的 blocks 是**整体替换** ⇒ 写回 = **静默改写数据**。
2. **pytest 只能在容器内跑** —— 宿主 py3.8 因 PEP 585 在**收集期**炸，**报错在 `app/models/`** ⇒ 长得像「我炸了**。
3. **删材料图前先看服务端有没有块引用它** —— `content_blocks.image_id` 有 **FK CASCADE** ⇒ 删被引用的图 = **连带删掉已落库材料块**。
4. **清理测试数据只删本次记录下来的 id** —— 不按列表全量删（星轨 #4 事故 ⇒ `review-debt.md` 规则 5）。
5. **组内小题：前端不传 `group_order`/`chapter_id`/`difficulty`** —— 后端 `max+1` + 从组继承 ⇒ 多传任一个 = **422**；算 `max+1` 前**锁组行**。
6. **5xx 对外只回固定文案** —— `INTERNAL_ERROR_MESSAGE`；异常细节只进 `logger.exception`。
7. **ORM 关系集合可能是陈旧缓存** —— `lazy="selectin"` + `expire_on_commit=False` ⇒ 回收资源前用**显式 query** 取路径，**别读 `q.images`**。

## 三、下一步（Y）

1. **等星轨的页面级结论**（commit2 + 欠账 P2/P3）⇒ 我已自检 17/17 + 2/2，**结论仍归星轨**。
2. **第 2 步可开**：P2 欠账已修完 ⇒ 星轨原话「P2 必须在第 2 步开始用题组数据之前修完」**已满足**。
3. **未压测** FOR UPDATE 并发路径；**未复跑** P2-1 在真 PG 上（回归网跑 SQLite）。
4. **星云**：`docs/PROJECT-CHARTER.md` 超限属大事件 ⇒ **我没动，待拍板**。

## 四、开放问题（Z）

- **题组 >500 行一次性渲染会慢**（裁决③ 接受）；**`GET /question-groups` 的 response_model 未改**（改 `{items,total}` 破坏性）。
- **`ContentBlockRead.block_type` 是裸 `str`** ⇒ 前端已兜；建议后端改 Literal。

## 五、承载体

`WAKEUP.md`｜`notes/milestones.md`（§12–§15）｜`notes/changelog/STATE.md`｜`docs/review-debt.md`
｜`交付物/运行时证据-*.md`（L1–L4）｜`zaiyao-memory`
