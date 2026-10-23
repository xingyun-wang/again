# STATE.md — 差异化作业工作台

> **最后更新**: 2026-10-23 22:5x (**星轨代码审查批 1 的 2 个 P1 已返工完** — 写块校验 image_id 归属 + 6 端点跨用户网)
> **1a-2 状态 = ✅ 完成**（M3-1a-2-1 迁移+模型 `e736e17` / M3-1a-2-2 API `ba7874a`；
>   缺陷修复 `4531fa8`；证据 `a7a9a12`/`08432e0`；门禁修复 `03843de`；机制 `1afc733`/`45da5b2`）
>   - **3 张新表**：`question_groups` / `group_knowledge_points` / `content_blocks`（0013 迁移）
>   - **questions 加 2 列**：`group_id`（FK CASCADE NULL）+ `group_order`（+ UNIQUE(group_id, group_order)）
>   - **question_images 改约束**：`question_id` NOT NULL→NULL + 加 `group_id` +
>     **XOR CHECK**（`(question_id IS NULL) <> (group_id IS NULL)` —— 互斥，不是"至少一个非空"）
>   - **10 个端点**：题组 CRUD 6 + 组侧图片 4（`MAX_IMAGES_PER_GROUP=10` 另立常量，
>     落盘 `{chapter_id}/group_{group_id}/` 带前缀不撞题目目录）
>   - **D2(a) 难度派生**：组是唯一写入源，`_sync_group_difficulty` 一处两个调用点
>   - **D3(a) 题量**：`small_question_count` + `total_points`（小题之和，材料不计分）
>   - **删组二次确认**（星云 10-23 拍板）：无 `?force=true` ⇒ 409 + **三个计数在 message**
>     （`core/errors.py:121-124` 会吞 `details` ⇒ 只能进 detail 字符串）
>   - **门禁**：ruff ✅ mypy ✅ **pytest 368 passed, 16 skipped**（基线 352 + 新增 16，零破坏）
>   - **🔴 三个真 bug（B 笔实测抓出，已修）**：
>     ① JSON 列默认 `none_as_null=False` ⇒ Python `None` 存成 JSON 字面量 `null` ≠ SQL NULL
>        ⇒ CHECK 的 `IS NULL` 判据恒 false ⇒ **建表能过、写入全炸**（PG 同因）→ 修 `4531fa8`
>     ② 删组用 `db.delete(group)` ⇒ ORM 因 `Question.images` 的 `delete-orphan`
>        先 UPDATE 子行 `group_id=NULL` ⇒ 撞 XOR CHECK → 改 **bulk delete**，交给 DB CASCADE
>        （⚠️ **偏离补遗 §乙-2 步骤 6 原文**，产物语义相同，待星轨确认）
>     ③ 迁移 revision id **长度上限 32**（`alembic_version.version_num` 是 varchar(32)）
>        ⇒ 超长在 UPDATE alembic_version 炸 + 容器 entrypoint 循环跑 upgrade ⇒ 崩溃重启循环
>        ⇒ **下一个迁移编号前先数字符**
>   - **判据已验**：SQLite（pytest 16 条）+ **真 PG**（正向 17 + 反向 9 条）
>   - **未覆盖**：判据 8 未单独逐字段对比 `GET /questions` 的 total（归 1b）；
>     正式 pytest 用例**未在 PG 上跑过**（conftest 的 PG 分支待 CI 验）；页面级 0 条（前端零改动）
> - **🔴 星轨打回返工（2026-10-23 15:00 审阅「不签收」，差两件 —— 已返工完）**：
>   - **第一件（完全属实）**：`group_knowledge_points` **只有读没有写** ⇒ **判据 3 在 API 上做不到**，
>     我那条 `PASS 判据3` 是**插库**造的 ⇒ 不算数。
>     **已修**：两处加 `knowledge_point_ids` + `Read` 返回 + 复用 `_check_knowledge_point_ownership`
>     （题目的那一个，不另写）+ 2 条 pytest **全走 API**（F9 判据 3 / F10 替换+归属守卫）。
>     **判据 3 的真正走法已验**（真 uvicorn + 真 PG + 真 curl，scratch 库，**不碰 dev/test 库**）：
>     POST 建组 201 响应含 `[1,2]` → `GET ?knowledge_point_id=1` / `=2` **都筛出该组** ✅
>     → 关联表实查 `1|1` / `1|2` → 不存在的 KP ⇒ 404 → extra 字段 ⇒ 422
>     → PUT 整体替换 ⇒ 旧关联被清、按旧 KP 筛返回空
>   - **第二件（前提偏了，但结论对）**：星轨说「门禁没改」—— 实际 `03843de` **就是**改门禁那笔
>     且排在 B 笔**之前**（他的 `git log 03843de..HEAD` 范围恰好把改门禁那笔自己排除了）。
>     **但旧版确实有两个真缺口**（我核出来的）：
>     ① 期望值取自 `docker exec alembic heads` ⇒ 读的是**容器副本**（`/app/alembic` 是**镜像烤进去的**，
>     只有 `data/uploads` 是 bind mount）⇒ 仓库加迁移没重建容器时**门禁看不见** ⇒ 失守；
>     ② `alembic heads | tail -1` **只取最后一个 head** ⇒ 分叉时**静默取一个**。
>     **已修**：新增 `scripts/alembic_head.py`（`ast` 静态解析**仓库工作树** revision 图求唯一 head，
>     退出码 0/2/3/4）+ 门禁加 **head 唯一性**分支。
>     **⭐ 3 条反向实测**（星轨点名要的「人为制造落后必须 ❌」）：
>     落后 ⇒ ❌ exit=1 ｜ 分叉 ⇒ ❌ exit=1 ｜ **旧门禁在同一场景下 ✅ 假绿 vs 新门禁 ❌ 抓出**。
>   - **门禁**：ruff ✅ mypy ✅ **pytest 370 passed, 16 skipped**（基线 368 + 2，零破坏）
>   - **CI**：run #39915426855 @ `717fc7f`（待回填结论）
>   - **探针环境已清理**：`thp-kp-probe` 容器 + `thp_kp_probe` 库已删、假迁移零残留、dev/test 库未动
>   - **未覆盖**：页面级 0 条（仍零前端改动）；判据 8 仍归 1b；
>     正式 pytest 在 PG 上的持续验证**仍依赖 CI**（本地 PG 跑在 scratch 库，因 conftest teardown 会 drop_all）
> - **🔴 星轨代码审查批 1（2026-10-23 22:00）的 P1 修复 —— 2 个 P1 已返工完**：
>   - 审查结论：**0 × P0 ｜ 2 × P1 ｜ 5 × P2 ｜ 1 × P3**（范围 `ab02079..e11de97`）。
>     P1 星轨要求「**在 1c-2 commit2 之前修**」⇒ 已修完。
>   - **P1-1（完全属实）**：`_replace_group_blocks` 把 `b.image_id` **原样写库**
>     ⇒ 读/删端点都有交叉校验，**只有写路径 0 处** ⇒ 用户可跨组/跨实体引用图
>     ⇒ **材料破图 + A 的材料块被 B 删图时静默带走**（FK CASCADE，链已逐层核过）。
>     **已修**：`_check_group_image_ownership` —— ① 比对 `group_id == group.id`
>     （**不看 block_type**：FK CASCADE 挂在 `content_blocks.image_id` 上，与 block_type 无关
>     ⇒ **我扩大了星轨的建议范围**）② 同一条 SQL 挡住「填题图」③ 不存在与跨组**同码同文案**。
>     ⭐⭐ **校验先于删除**（否则校验不过时**旧块已被删** ⇒ 那是数据破坏不是校验失败）。
>     ⭐⭐ **PUT 改两阶段**（先全校验再统一应用）—— 原顺序 difficulty→KP→blocks 每步都 flush，
>     422 时前面已 flush；生产靠 `close()` 侥幸兜住，**测试的共享会话不兜** ⇒ 22:00 之前没意识到。
>   - **P1-2（完全属实）**：新增 6 个端点**没有跨用户用例** ⇒ 补 R11（PUT）/ R12（POST 小题）/
>     R13（4 个组图端点），口径一律 **404**。
>     ⭐⭐⭐ **R12 第一版是「假网」**：用 user1 的题 ⇒ 404 是被**题归属**守卫拦的，
>     **组归属守卫轮不到执行** ⇒ fail-open 实测时它**照样通过** ⇒ 抓出后改用
>     **user2 自己的题** ⇒ 第 2 次 fail-open **3 条全 FAIL**。
>     ⇒ **「测试通过」≠「测试守得住边界」**，只有 fail-open 实测能分辨。
>   - **P2 × 5 + P3 × 1 已登记 `docs/review-debt.md`**（每条带**触发时机**）。
>     ⭐ **修正星轨一处计数**：P2-2「共 9 处」⇒ **实测 15 处** `status_code=500` 含 `{e}`，
>     另有 4 处非 500 码（400/422/502×2）也拼 `{e}`。
>     ⚠️ **不改 `docs/tech-debt.md`** —— 那是门禁第 10 项双向核对的靶子，
>     行号指向代码位置写进去必让门禁红 ⇒ 另起文件 + `notes/changelog/review-debt.md`（D-77）。
>   - **门禁**：ruff ✅ mypy ✅ **pytest 376 passed, 16 skipped**（基线 370 + 6，零破坏）
>   - **⚠️ 环境坑**：宿主 **Python 3.8 + SQLAlchemy 2.0.53** 跑 pytest **必炸**
>     （`Mapped[list[Question]]` 里的 `list[...]` 是 PEP 585，3.9+ 才支持）—— **不是本轮改动炸的**。
>     门禁一直在**容器内**跑（`docker exec thp-backend`），宿主只跑 `alembic_head.py`（纯 ast）。
>     ⇒ 待星轨定：要不要在 `WAKEUP.md` 里写死「pytest 只能在容器内跑」。
>   - **三笔**：`d3621a1`（P1 修复+测试）/ `606435a`（欠账台账）/ `f3f3f51`（证据）
> - **S4 状态 = **字体 ✅ / 选项 ✅**（沉淀式 32/32 PASS, 2026-10-16 15:29 收工; font 真 17.7MB variable TTF / 选项 120 = 30 题 x 4 全对 / 无答案泄漏)** (3 commit 06979e5/3edcdf6/daafd65 + run#118 绿 + 5 case 全过 + ledger 11/11 + 双推 origin (Gitee) 0/0; **github 已推** per B3 硬前置 (星云 15:29 授权 github 单独批, 17.7MB binary 已入仓 + 5 笔同步推 github master)); **S4-b 状态 = 派工链 真正 闭环** (派工 v9 改 3 文件 = docker-compose:94 + frontend/.env.example:6 + frontend/src/api/health.ts 独立 axios 实例 + 派工 v10 改 3 文件 = Dockerfile ARG/ENV fail-fast + Assignments.tsx:146 + docker-compose.yml:93 注释 + 派工 v11 改 1 文件 = Review.tsx 加 导出 PDF 按钮 + 删 空头支票 + 改 data?.detail 错误字段; 派工链 v1-v6 commit 4e04e99/fe09d09/4b19ace/1e8fe26/49c6e46/2e9f0b1/b931ebe 全部 落 仓; **bundle baseURL 真值 = /api/v1** 双判据 命中 [B2 修法]; **派工 v12 跑 通 = dev 库 19 user_tables 复原 + 1 chapter + 1 assignment id=13 APPROVED**; **端到端 关键 5 探针 全 命中**: GET /api/v1/assignments/13=200 + GET /api/v1/assignments/1=404 (闸门 D-29) + GET /api/health=200 + POST /api/v1/assignments=422 + **POST /api/v1/assignments/13/export=200 PDF 8907 B / %PDF-1.4** [复核员 22:0x 验真 一致]; **派工 v9-v12 累计 4 关键 fact**: tsc 0 / build 0 / pytest 切 test 库 323 passed 9 skipped 0 failed 164.64s / ledger 11/11 / git status clean); **11 枚举 follow-up 留明日起点** (per 复核员 B2 修法 = 写枚举不写总数): 1. **S4-b 前端导出 UI** (P0-1 紧急, 派工 v11 修 A1 部分 落地; L1/L2/L3 已知遗留 仍 留 另立 工单 跟进) / 2. S4.5 字体扩集 ≥3000 码点 (google/fonts ofl/notosanssc/) / 3. 拿基线 (干净 test 库 + `tee` 日志, 治 6+ 次 cut-off) / 4. worktree 清理 10 个 / 5. B3 test_pg_alembic_round_trip 独立工单 / 6. ledger 11/11 持续 / 7. CI B1 持续 / 8. B2 worktree 持续 / 9. B3 zaiyao-memory 9p 持续 / 10. 5 修法 v6 持续 / 11. 决策室违规 自我反停 持续 / 12. ~~选项渲染缺失~~ → **CLOSED** (per 沉淀式 32/32 PASS, 2026-10-16 15:29; commit 69367e3 修; 30 题 A→B→C→D 顺序全对; 无答案泄漏; S4 整体 = 字体 ✅ / 选项 ✅); **窗口期 风险 仍 存在** (代码 + 容器 + 接口层 全 到位, 缺 主人 hard reload 浏览器 + 在 审阅页 点 导出 PDF 按钮 + 截图 + github 推 单独批); **不立新 D-XX** per D-83 不立原则
> **今日详记**：`memory/2026-10-23.md` (新; **1a-2 题组模型+块表+API 全线落地** + 交付物/ 运行时证据机制建立 + 三个真 bug 定位 + 推翻 brief §5.4 旧基线 349→352) + `memory/2026-10-16.md` (S4 字体修复 ✅ + 选项渲染 ✅ + 沉淀式 32/32 PASS + 12th follow-up CLOSED + push origin/Gitee + github 单独批推) + `memory/2026-10-14.md` 压 202→≤100 行 (priority 1, per 复核员 B1) + `memory/2026-10-13.md` 压 119→≤100 行 (priority 2, per D-75/D-76)
> **详细历史**：见 `notes/milestones.md`（一页纸摘要 / 硬约束 / 工作约定 / 链接索引 / session 启动清单 / §10 排期快照 / 反思与元规则 / 收口轨迹 / 收口决策书接住 + 接受率 backlog / 文件末变更说明）
> **承载体**：本工作区 + `WAKEUP.md`（4 项唤醒清单）+ `zaiyao-memory` 仓（每日 push）+ `notes/milestones.md`（一页纸）+ `notes/changelog/STATE.md`（D-77 承接）
> **维护规则**：每节定稿 / W 阶段 commit 后 / 用户明确要求时更新（主体已迁出至 notes/milestones.md；变更说明见 `notes/changelog/STATE.md`）
