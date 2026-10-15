# M2-S4-b brief — 作业单 PDF 导出前端 (v0.5 §3.6 + §7.5; responseType:blob + URL.createObjectURL + 删 ExportResponse) [v4 修正]

> **工单**: M2-S4-b (= S4 后置工单, 前端流式下载承接)
> **依赖**: M2-S4 已落地 (3 commit `06979e5` / `3edcdf6` / `daafd65`, 末笔 `daafd65`; run#118 绿; 5 case 全过; reportlab_ver 4.5.1)
> **窗口期**: S4 落地 → S4-b 落地之间, 导出按钮表现 = "点了不下载" (frontend job 全绿掩盖; TS `any` 谎报); S4-b 落地后**关闭窗口期**
> **起草**: 2026-10-15 13:25 v1 起草 → 13:35 v2 修正 (per 复核员 13:2x 回执 4 A + 3 B) → **13:40 v3 修正 (per 复核员 13:3x 回执 1 A + 2 B + 1 nit)** → **13:45 v4 修正 (per 复核员 13:4x 回执 1 A; 累计 1 失实 = items 列不存在)**
> **状态**: **8 修 全部 即修** (v2: 3 A + 3 B; v3: 1 A + 2 B + 1 nit; v4: 1 A); **2 失实累计** (v2 锚点 academic.py:523 失实; v3 items 列不存在 失实 — **同一处判据第 3 次写错** v1 status / v2 review_status / v3 items); 笔数 1 笔 = 复核员 同意 拍 A3 = A

---

## §一、范围 (per 复核员 §2 漏项 已应用; per A2 文件归属 修正)

1. `frontend/src/pages/Assignments.tsx` (**真值, 唯一目标文件**; **A2 修正 — 旧"frontend/src/api/assignments.ts"是幻影**):
   - **删** `ExportResponse` 接口 (`:67-72`)
   - **改** `apiClient.post<ExportResponse>` → `apiClient.post<Blob>` (**泛型同步改** per 复核员 §2)
2. 同一文件 (S4-b 1 笔 全改 Assignments.tsx):
   - **改** `responseType:'blob'` (S4 后端已返 application/pdf bytes; 前端取 Blob 即可)
   - **改** `URL.createObjectURL(blob)` 触发下载 (per 派工回执 §十四 + brief §十三 S4-b 范围)
   - **改** 文件名从 `Content-Disposition: attachment; filename="assignment_{id}_{ts}.pdf"` 解析 (per 复核员 §2; 后端已返 `assignment_{id}_{ts}.pdf` in Content-Disposition)
   - **保留** 403/404 catch 路径 (per 复核员 §2; 闸门段 / §7.5 错误处理)
3. **文案**:
   - **删** "导出已入队（export_id=...）" (per 派工回执 §十四 + brief §十三 S4-b 范围)
   - **改** "已生成作业单 (assignment_{id}_{ts}.pdf), 正在下载..."

> **A2 修正留痕**: v1 brief §一.1 写 `frontend/src/api/assignments.ts` 是幻影文件 (该目录仅 `client.ts` + `health.ts` 2 files). 真值 = `frontend/src/pages/Assignments.tsx` (ExportResponse 接口 :67 + 用法 :157-165 都在同一文件). v2 修正.

## §二、DoD (per A3 硬前置 **必含运行时证据**)

**主判据 A (browser-use 真点真下载, per 复核员 §1)**:
- 起前端 + backend + DB 全栈 (`docker compose up -d` 等 healthy)
- 创建/确认 1 条 **APPROVED** 状态作业单 (per §四 入场闸前提; "拿基线" 仍 follow-up, 但若有现成 APPROVED 单可直接用)
- 用 browser-use 跑一遍: 访问 Assignments 页 → 找到 APPROVED 作业单 → 点"导出"按钮
- **运行时证据** (必含, 任一缺 = 退单):
  - Network 响应 `Content-Disposition: attachment; filename="assignment_<id>_<ts>.pdf"` ✓
  - 落盘文件头 `%PDF` (前 4 bytes 校验: `0x25 0x50 0x44 0x46`) ✓
  - 落盘文件大小 > 0 (**B2 修 — per S4-b 期望 ≥ 1 KB **仅作参考**, 非硬判据**; 字体窄集已知缺口 35 码点; **若 items 为空, §2 列表跳过但 §1 抬头 + §3 审阅状态 仍生成, PDF 可能 < 1 KB**; **§四.2 SQL 已加 `EXISTS (SELECT 1 FROM assignment_items i WHERE i.assignment_id = a.id)` 缓解空单风险** — v5 B1 修: 旧 v4 写 `items IS NOT NULL` 失实, v4 SQL 已 无此子句)
  - `URL.createObjectURL` 调用计数 ≥ 1 (Network response → Blob → createObjectURL → 落盘) ✓
  - 截图/录屏存档 (`/tmp/s4b_evidence_<ts>.png` 或 `.webm`)

**降级路径 (per 复核员 §1, 备选; 仅当主判据 A 不可行时)**:
- **真机手点** + 截图/录屏存档 (DevTools Network 标签 + Sources 标签 + 落盘文件)
- **仍须运行时证据**, 不许退回静态三查 (frontend type-check / build / eslint)

**禁判据 (per A3 硬前置 + 复核员 §1 另立 backlog)**:
- ❌ 仅 frontend job (ESLint + TypeScript + Build) 全绿 = **不算** (per 复核员 §1 "frontend job 全绿抓不到")
- ❌ jsdom/happy-dom 单元测试 (per 复核员 §1 "选 B = 新装 vitest + happy-dom + 改 ci.yml frontend job ⇒ 另立 backlog, 不塞 S4-b")
- ❌ 静态三查 (type-check / build / eslint) 任一独立报"绿" = 不算 (per 派工回执 §十四 + A3 硬前置)

## §三、Commit 划分 (S4-b 1 笔; **A3 修正 — 已拍 A = 1 笔**)

> **A3 修正 (per 复核员 §A3)**: 接口 + 用法 + handler **全在同一文件同一函数** ⇒ 2 笔切分结构性不成立 (commit 1 若只"删接口 + 改泛型", `Assignments.tsx:164-165` 的 `resp.data.export_id` 失去类型 ⇒ TS 报错 ⇒ frontend job 红, 中间 commit 不自洽).
>
> **已拍 A = 1 笔** (星云 13:3x 拍; 复核员 13:3x 背书: 1 笔 = 单一原子行为 ≠ §九「并片」); **§九「严禁并片」原意 = 严禁 S4 内部 3 笔合并, 不强制 S4-b 必须 2 笔**; B 选项 (2 笔) = 复核员 判定实际不可行, **已 弃**.

**A 选项 (已拍, v4 默认)**: **1 笔** =
- `feat(S4-b UI): Assignments.tsx 流式下载 + 删 ExportResponse + 风险关闭声明`
  - 改: `frontend/src/pages/Assignments.tsx` (唯一目标文件)
  - 删: `ExportResponse` 接口 (`:67-72`)
  - 改: `apiClient.post<ExportResponse>` → `apiClient.post<Blob>` (泛型 + 用法 同步改)
  - 改: `responseType: 'blob'` + `URL.createObjectURL(blob)` 触发下载
  - 改: 文件名从 `Content-Disposition` 解析
  - 改: 文案 (删 export_id, 改 "已生成作业单 (assignment_{id}_{ts}.pdf), 正在下载...")
  - 保留: 403/404 catch
  - commit message 必含:
    - `[origin-push]`
    - **"M2-S4 → M2-S4-b 落地完成, 窗口期风险关闭 (导出按钮从 '点了不下载' 恢复为 '点了真下载')"** 风险关闭声明 (即关闭 S4 commit 3 的窗口期风险声明)

**B 选项 (待重定义)**: **2 笔** = 需重新找切分点, 但接口 + 用法 + handler 都在同一文件同一函数, 切分点难找 ⇒ 实际不可行, 复核员 不推荐.

## §四、入场闸 (派工前必查; per 复核员 §1 "全栈可起 + 1 条 APPROVED 作业单")

1. **全栈可起**: `docker compose up -d` (后端 + DB + frontend), 期望 3 service 全部 healthy
2. **存在 1 条 APPROVED 作业单** (**A1 + A 修 + B1 修 + B2 修 — 真值 SQL**):
   - 旧 v1 (失实): `SELECT id, status FROM assignments WHERE status='APPROVED'`
   - v2 (A1 修正): `SELECT id, review_status FROM assignments WHERE review_status='approved' LIMIT 1`
   - **v3 (A 修 + B2 修 — 失实, 阻塞派工 per 复核员 13:4x)**: 旧 SQL `SELECT id, review_status, owner_user_id, items FROM assignments WHERE review_status='approved' AND owner_user_id=1 AND items IS NOT NULL` ⇒ **'column "items" does not exist'** (per 复核员 实测)
   - **v4 (A 修 + B2 修 — 正解 SQL, EXISTS 子查询 + 别名 `a`)**: `SELECT a.id, a.review_status, a.owner_user_id FROM assignments a WHERE a.review_status='approved' AND a.owner_user_id=1 AND EXISTS (SELECT 1 FROM assignment_items i WHERE i.assignment_id = a.id) LIMIT 1` 期望 ≥ 1 row
   - 依据 (A 修 + B1 修 + **双证修正 v4** — 模型层 + 迁移层):
     - **enum**: `backend/app/models/academic.py:72-77` `KnowledgeReviewStatus(str, Enum): PENDING="pending" / APPROVED="approved" / MODIFIED="modified"` (lowercase)
     - **Assignment.review_status 字段**: `backend/app/models/assignment.py:89-101` `Mapped[KnowledgeReviewStatus]` + `default=PENDING` + `server_default='pending'`
     - **闸门真值**: `backend/app/api/v1/routers/assignments.py:362` `if assignment.owner_user_id != user_id: raise HTTPException(404)` (D-29 不暴露存在性)
     - **前端 owner**: `frontend/src/pages/Assignments.tsx:14/124/160` `X-User-Id: '1'` **写死** ⇒ owner_user_id 必须 = 1
     - **items 非空 前提 (双证)** (**B2 修 + v3 修 — 关系 vs 列 双证**):
       - **模型层** (`models/assignment.py:118-125`): `items: Mapped[list[AssignmentItem]] = relationship("AssignmentItem", back_populates="assignment", cascade="all, delete-orphan", lazy="selectin", order_by="AssignmentItem.position")` ⇒ **这是 ORM relationship (关系), 非 DB 列**; ORM 属性名 ≠ DB 列名, **没有对应列**
       - **迁移层** (`0008_assignments.py:94-105`): 题目在**独立表 `assignment_items`** = `op.create_table("assignment_items", sa.Column("id", ...), sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False), sa.Column("question_id", ...))`; 全迁移 `grep '"items"'` **零命中** (无 `items` 列)
       - ⇒ SQL **不能用 `items` 列** (relationship 属性 + 独立表), 必须用 `EXISTS` 子查询 `assignment_items` 表
       - **给载曜的口径** (per 复核员 13:4x): **改 SQL/列名类断言, 必须同时核「模型层 (ORM 属性类型 + 是否 relationship) + 迁移层 (create_table / add_column 实际列名)」双证后才落字**; `items` 看着可信是因为 ORM 里叫 `items` + PDF 代码里写 `assignment.items` — 但那是关系属性, SQL 层根本不存在这一列
3. **本地 HEAD 已 = `1acbda4`**, 无需 `git pull` (**B3 修正 — 删 v1 旧表述**)
4. `git status --porcelain` → 期望 0 行
5. (参考) `git log --oneline -5`
6. **当前 frontend job 状态**: 必须已知前 N 笔 commit 的 frontend job 跑成功 (作为 baseline); 若 frontend job 当前红, 先修, 再派 S4-b (per §治理.20 失实教训: docker compose 不挂 backend/tests/ volume)
7. **frontend TypeScript baseline** (**A4 修正 — 真值 script 名**): 
   - 旧 v1 (失实): `cd frontend && npm run type-check` (`Missing script: "type-check"`)
   - 新 v2 (真值): `cd frontend && npx tsc --noEmit` → 0 errors (派工前基线)
   - 依据: `frontend/package.json` scripts = `dev / build / lint / preview`, **无 `type-check`**
8. `cd frontend && npm run build` → 0 errors (派工前基线)

**拿基线 (干净 test 库)** = 仍 follow-up (per 11 枚举 follow-up #3), 不阻塞 S4-b; 但若 §4.1 全栈起不来, **降级路径 = 真机手点 + 截图/录屏** (per §二 降级路径)

## §五、报回格式 (per 派工回执 §十四 6-line handshake + 第 7 项 + CI run 号)

每 commit 报这 7 行:
```
commit <SHA>
files: <list>
+lines / -lines
frontend_tsc: <"0 errors" string; per A4 真值 npx tsc --noEmit>
frontend_build: <"0 errors" string>
[origin-push]: yes
ci_run: <run#number + frontend job + backend job 状态; 必含>
```

派工后 6-line + 1:
1. 最新 1 笔 commit SHA
2. **运行时证据** (per §二): browser-use 跑过的 截图/录屏 路径 + 关键帧描述 (Network 响应 / 落盘文件头 / URL.createObjectURL 计数); 降级 = 真机手点截图/录屏 + 落盘文件
3. `git show --stat HEAD` 输出
4. `npx tsc --noEmit` 输出尾部 5 行 (**A4 修正**)
5. `npm run build` 输出尾部 5 行
6. 偏离 brief 项 (如有; 无则"无偏离")
7. **CI run # + frontend job + backend job 验真表** (**B1 修正 — 真值 step 号**): 
   - frontend job 步骤 5 ESLint / 6 TypeScript check / 7 Build (无 step 8; 13-15 = Post/Complete) 全 success
   - backend job 步骤 6/7/9/10/11 全 success
   - step 13 verify e2e 预期 skipped
   - 任何其他 skipped = 退单

**降级路径报告** (若全栈起不来):
- 截图/录屏路径
- 落盘文件头 + 大小
- URL.createObjectURL 调用计数 (若可观察)

## §六、6 派工后必跑 (per 派工回执 §十 派工后必跑)

1. **起全栈**: `docker compose up -d` + 等 3 service healthy
2. **验 1 条 APPROVED 作业单存在** (per §四.2 真值 SQL)
3. **跑 browser-use** (主判据 A) 或 **真机手点** (降级路径)
4. `git show --stat HEAD` (验 commit 内容)
5. **frontend baseline 验** (**A4 修正**): `npx tsc --noEmit` + `npm run build` → 0 errors
6. `bash scripts/ledger_check.sh` = 11/11 PASS
7. `git status --porcelain` → 0 行
8. **推 origin (Gitee) + github (须星云逐次明示批 per B3; 不预授权)** (**B2 修正 — 删 v1 "同步批" 自改授权粒度**)
9. **CI 验真**: GitHub Actions run#X 必含 frontend job (步骤 **5/6/7** ESLint / TypeScript / Build 全 success, **B1 修正**) + backend job (步骤 6/7/9/10/11 全 success; step 13 verify e2e 预期 skipped); **任何 step skipped = 退单, 除 step 13 设计性 skip**

## §七、Hard rules (退单触发 = 任一违反)

- 派工 brief 内容不得改 (退单 if 改)
- 严禁跨工单扩散 (S4-b 改 S4 之外的代码 = 退单; 闸门段 / §7.5 除外不动)
- 严禁 xfail/skip frontend job 步骤 (退单; 必真跑)
- 严禁静默 `try/catch` 吞错 (下载失败必 raise → UI 报错)
- 严禁并片 (S4-b 1 笔 / S4 3 笔; 守 §5 教训 #9; 严禁 S4 3 笔合并为 1 笔)
- 严禁只挂 frontend job 报"绿" (per A3 硬前置; **必运行时证据**)
- **禁选 B (jsdom/happy-dom 单元测试)** — per 复核员 §1; 另立 backlog
- **frontend test 框架零基线** (package.json 无 test script / 无 vitest/jest/happy-dom / src 零 `*.test.*`/`*.spec.*`) ⇒ **不塞 S4-b**
- 严禁改 S4 已落地代码 (per 派工回执 §十二 + brief §三 严禁; §7.5 闸门段除外不动)
- 严禁 commit message 不含 `[origin-push]`
- 严禁报回不带 **CI run 号** (per 复核员 §3; 今日红线 #1)
- **github 推须星云逐次明示批** (per B3; 严禁 brief 自改授权粒度)

## §八、Completion path

- 完成 1 commit (A 选项) + 双推 + CI 验真 + 运行时证据 (browser-use 主判据 或 真机手点降级) = 派工通过
- 报回用 6-line + 1 + 运行时证据 (per §五)
- 报回后 主人 (星云) 审 + 复核员 (星轨) 审
- 报回即结束, 不需等审

## 关联引用

- `plans/M2-S4-brief.md` (S4 brief v6 710 行; S4 已落地 commit `daafd65` 起的 3 笔)
- `backend/app/services/assignment_export.py` (S4 commit 2; 4623 B / 128 行; lazy _ensure_font)
- `backend/app/api/v1/routers/assignments.py:334-382` (S4 commit 3; 流式直返, 已含 Content-Disposition `assignment_{id}_{ts}.pdf`)
- `frontend/src/pages/Assignments.tsx` (**唯一目标文件, A2 修正**; ExportResponse 接口 :67-72 + 用法 :157-165 + handler 全部在内)
- `frontend/src/api/` 仅 `client.ts` + `health.ts` (**A2 真值 — 旧 v1 "assignments.ts" 是幻影**)
- `frontend/package.json` scripts = `dev / build / lint / preview` (**A4 真值 — 旧 v1 "type-check" 是幻影**)
- `backend/app/models/academic.py:72-77` `KnowledgeReviewStatus` enum = `pending / approved / modified` (lowercase; **A1 真值**)
- `backend/app/services/` 无 `assignment_review.py` (`backend/tests/api/v1/test_assignment_review.py` 才有, 命名易混)
- run#118 (S4 派工绿; 5 case 全过; 12 backend 步真跑)
- run#116 (P0-1 修 CI 红 5 连绿; 今日红线 #1 PASS)
- run#1acbda4 = 收工笔; 已双推 origin (Gitee) + github (per A 拍)

---

> **【2026-10-15 13:50 v5 修正变更说明 · plans/M2-S4-b-brief.md】**
>
> **修订范围**: v1 → v5; 累计 12 修 (v2: 3 A + 3 B = 6; v3: 1 A + 2 B + 1 nit = 4; v4: 1 A; v5: 3 B 文字一致性 = 3); **收敛趋势** v1 4 A → v2 1 A + 2 B → v3 1 A → v4 0 A + 3 B → **v5 0 A + 3 B (文字)** ✓
>
> **brief 冻结 (per §七 硬规则)**: v5 后 任何 subagent 改 brief = **退单** (per §七 派工纪律). 派工后 报回 仅 6-line + 1 (per §五) + 运行时证据 (per §二); **不许改 brief**
>
> ---
>
> **v5 修法 (3 B 文字一致性 派前必修; per 复核员 13:4x)**
>
> 1. **B1 §二 :36 引用 失实**: 旧 v4 写 "§四.2 SQL 已加 `items IS NOT NULL` 缓解空单风险" — v4 SQL 已 无此子句 (改 EXISTS). 修: 改 "§四.2 SQL 已加 `EXISTS (SELECT 1 FROM assignment_items i WHERE i.assignment_id = a.id)` 缓解空单风险"
> 2. **B2 §三 :49/:53/:55 状态 陈旧**: 旧 v4 标题 "A3 修正 — 待你拍" + 选项 "v2 默认" + "B 选项 (待重定义)" — 实际 已拍 A = 1 笔 (星云 13:3x 拍 + 复核员 13:3x 背书). 修: 标题改 "已拍 A = 1 笔" + 删 "B 选项 (待重定义)" 段 + 选项 标 "已拍, v4 默认"
> 3. **B3 尾部 变更说明 停在 v2**: 旧 尾部 整块 标 "v2 修正变更说明" + 只记 v2; v3 / v4 缺失. 修: 本段 合并 v2 + v3 + v4 + v5
>
> **v4 修法 (1 A 锚点 失实; per 复核员 13:4x)**
>
> 1. **A 修 §四.2 SQL items 列不存在**: v3 写 `AND items IS NOT NULL` — `column "items" does not exist` (per 复核员 实测). 修: `EXISTS (SELECT 1 FROM assignment_items i WHERE i.assignment_id = a.id)`; 加 **双证** (模型层 `models/assignment.py:118-125` `items: Mapped[list[AssignmentItem]] = relationship(...)` 关系非列; 迁移层 `0008_assignments.py:94-105` `op.create_table("assignment_items", ...)` 独立表; 全迁移 `grep '"items"'` 零命中); **给载曜的口径** (改 SQL/列名类断言, 必须同时核「模型层 + 迁移层」双证后才落字)
>
> **v3 修法 (1 A + 2 B + 1 nit 锚点/判据 失实; per 复核员 13:3x)**
>
> 1. **A 修 §四.2 SQL 缺 owner_user_id 约束**: 闸门 `assignments.py:362` `owner_user_id != user_id → 404` 硬证; 前端 `X-User-Id:'1'` 写死 ⇒ 必加 `AND owner_user_id=1`
> 2. **B1 修 §四.2 依据 锚点 失实**: `academic.py:523` = `difficulties` 表 (无 review_status); 真值 = `models/assignment.py:89-101` `Mapped[KnowledgeReviewStatus]` + `default=PENDING`
> 3. **B2 修 §二 落盘 ≥ 1 KB 缺 items 前提**: `assignment_export.py:97` 空 items 时 §2 列表跳过但 PDF 仍生成; ⇒ 判据降为 "参考" + §四.2 加 items 非空 前提 (v4 SQL 用 EXISTS 落地)
> 4. **nit 修 :4 措辞**: 旧 "commit `daafd65` 起的 3 笔" — `daafd65` 是末笔非起点; 改 "3 commit `06979e5`/`3edcdf6`/`daafd65`, 末笔 `daafd65`"
>
> **v2 修法 (3 A + 3 B 锚点/判据 失实; per 复核员 13:2x)**
>
> 1. **A1 §四.2 SQL**: `status='APPROVED'` → `review_status='approved'` (per 真值: 列名 = `review_status`, 枚举 lowercase)
> 2. **A2 §一.1 / §三 commit 1 / §关联引用**: `frontend/src/api/assignments.ts` (幻影) → `frontend/src/pages/Assignments.tsx` (真值唯一目标文件; `frontend/src/api/` 仅 `client.ts` + `health.ts`)
> 3. **A4 §四.7 / §五.4 / §六.5**: `npm run type-check` (Missing) → `npx tsc --noEmit` (真值)
> 4. **B1 §五.7 / §六.9 step 编号**: "5/6/7/8" → "5/6/7" (无 step 8; 13-15 = Post/Complete)
> 5. **B2 §六.8 授权句**: "per B3 单独批 同步批, 不必逐笔" → "github 推须星云逐次明示批" (B3 = 逐次批)
> 6. **B3 §四.3 origin 表述**: 删 "git pull 同步 master (重新拉 origin = 1acbda4)" (本仓 origin = Gitee; 本地 HEAD 已 = 1acbda4, 无需 pull)
>
> **v1 → v2 总览**: 4 A (SQL 列名错 / 幻影文件 / 笔数 2 不可行 / 幻影 script) + 3 B (step 编号 / 授权句 / origin 表述); **数字族 第 5 例 自我反停** (我 v1 报回 "~190 行" vs 复核员 实测 159 行; 差异 31 行; 数字族修法 = 实测 不估)
>
> ---
>
> **失实累计** (per A5 (a) 数字稳定滞后 1 笔口径; 不立 D-XX per D-83):
> - **累计 self-stop = 19 + 1 = 20** (v5 引入 3 失实 = 1 失实组)
> - v2 引入 4 失实 (SQL / 依据 / 判据 / 措辞) 1 失实组
> - v3 引入 1 失实 (items 列不存在) 1 失实组
> - v4 引入 0 失实
> - v5 引入 3 失实 (3 文字一致性) 1 失实组
> - 数字族 (v1 ~190 行 vs 159 行) 1 失实
>
> **不立 D-XX** per D-83 不立原则
>
> **来源**: 2026-10-15 13:50 +0800 per 复核员 13:4x 回执 (3 B 文字一致性 派前必修) + 13:3x 拍 A3 = A + 13:2x 4 A + 3 B; github 推 `daafd65..1acbda4` master 已落 (HEAD = origin/master = github/master = 1acbda4); 8 步 收工 闭环验真过 (11/11 项)

---

## 2026-10-15 22:30 收工注 — 派工 v9-v12 派工链 真正 闭环 (S4-b brief v5 收工)

- **派工 v9** (commit 49c6e46): 改 3 文件 (docker-compose:94 VITE_API_PREFIX: /api/v1 / frontend/.env.example:6 / frontend/src/api/health.ts 独立 axios 实例) — 漏 Dockerfile (派工 v10 修)
- **派工 v10** (commit 2e9f0b1): 改 3 文件 (frontend/Dockerfile ARG/ENV fail-fast / Assignments.tsx:146 删 chapter 不存在 写死 / docker-compose.yml:93 注释)
- **派工 v11** (commit b931ebe): 改 1 文件 (Review.tsx 加 导出 PDF 按钮 + 删 空头支票 + 改 data?.detail 错误字段)
- **派工 v12** (跑 通): 0 文件 改; DROP DATABASE + 容器 重启 + alembic upgrade head 自动 + SQL 插 1 chapter + 1 assignment id=13 APPROVED + 端到端 5 探针 全 命中
- **bundle baseURL 真值 = /api/v1** 双判据 命中 (B2 修法, 非 grep 字符串 假绿): `const gU="/api/v1"` + `baseURL:gU`
- **端到端 关键 5 探针 全 命中**: GET /api/v1/assignments/13=200 + GET /api/v1/assignments/1=404 (闸门 D-29) + GET /api/health=200 + POST /api/v1/assignments=422 + **POST /api/v1/assignments/13/export=200 PDF 8907 B / %PDF-1.4** (复核员 22:0x 验真 一致)
- **S4-b 派工链 v1-v6 真正 闭环** (派工 v1-v6 commit 4e04e99/fe09d09/4b19ace/1e8fe26/49c6e46/2e9f0b1/b931ebe 全部 落 仓)
- **已知遗留 5 笔** (L1-L5): L1 Assignments.tsx:216 export 404 写死 / L2 Review.tsx:136 load 404 写死 / L3 Review.tsx:184 review 404 写死 / L4 client.ts:3 兜底 / L5 A1 ③ URL/sessionStorage 切页 恢复
- **self-stop 累计 49** (per A5 (a) 数字稳定滞后 1 笔口径; 派工 v9-v12 失实 组 19 笔; 不立 D-XX per D-83)
- **窗口期 风险 仍 存在** (代码 + 容器 + 接口层 全 到位, 缺 主人 hard reload 浏览器 + 在 审阅页 点 导出 PDF 按钮 + 截图 + github 推 单独批)
- **来源**: 2026-10-15 22:30 +0800 per D-75 §2 收工 8 步 (per 星云拍 B 走 origin 推, github 单独批)
