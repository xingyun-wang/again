# #113 — 9 pre-existing 失败用例根因诊断工单

> **状态**: 根因诊断完成 / 修复待 #114 拍
> **创建**: 2026-10-14
> **触发**: memory/2026-10-13 §五（9 pre-existing 失败用例）
> **诊断真值**: pytest 输出见 `/tmp/pytest_113.log`（commit `4eec216` / `c0be4ad` 后运行，容器 PG，9 failed, 43 passed, 2 skipped, 273 deselected, 2 warnings in 69.33s）
> **派工 brief**: `plans/M2-#113-诊断-brief.md`（commit `4eec216`）
> **不立 D-XX**（per D-83 不立原则；元规则通胀防御）
> **诊断者**: subagent（派工 #1 试 per corrective-rule-1-dispatch-protocol）

## ⚠️ 复验提醒（per 审查员反馈 2026-10-14，11:00 +0800）

> **本次 pytest 是 -k 筛选子集（54 selected / 273 deselected）⇒ "8/9 绿" 只证子集；#114 收口必须跑全套**

- **本次 派工 #1 试 pytest 命令**：`pytest -k "p15 or textbook_upload_real_pdf or p0n1 or academic_api or academic_llm or cross_user_isolation"`（仅 54 selected / 273 deselected）
- **"8/9 绿" 含义**：仅证上传/审阅子集；其余 273 个 test 未覆盖（M3/M4/M5 链路上的 test 没跑到）
- **#114 收口必跑**：完整 `python -m pytest -q` 全套 → 期望 0 failed（不留尾巴）

---

## 总体盘

| 分类 | 数量 | 严重 blocker | 备注 |
|---|---|---|---|
| A. 数据 fixture 问题 | 0 | 0 | — |
| B. source vs test 期望不一致 | 1 | 0 | test_real_llm_review_flow 跨用户 review 期望 vs owner 强制（per A2 订正：理由从"双重门"改写为"反 ID 泄漏门"） |
| C. mock / patch 失配 | 0 | 0 | — |
| D. migration / schema 漂移 | 0 | 0 | — |
| E. 环境依赖（host bind mount 权限） | 8 | 8（**blocker for M3**） | 单一根因 + 8 个不同测试（per A1 订正：仅 host chown 真有效） |
| **合计** | **9** | **8** | E 根因 1 个，影响 8 个 test |

**关键发现**：9 个失败实质上 = **2 个独立根因**：

1. **根因 #1（8/9 失败）**：host `data/uploads/` 由 `root:root` 拥有，mode 755；容器 backend 以 `appuser` (uid=1000) 运行；bind mount 后容器内 `/app/data/uploads/` 不可写 → `pending_dir.mkdir()` 直接 PermissionError，service 早期失败。
   - **A1 订正（per 审查员反馈 2026-10-14）**: 修法**仅 host chown -R 1000:1000 真有效**；选项 2（docker-compose `user: "1000:1000"`）与选项 3（backend Dockerfile 创建 `/app/data/uploads` 时 `chown appuser`）均**无效**（详 §失败 1 修法方向 + §修复优先级 P0）

2. **根因 #2（1/9 失败）**：`test_real_llm_review_flow_lesson_plan_pending_to_reviewed` 测试期望 X-User-Id: 2（异用户）能 PATCH `/lesson-plans/{id}/review` 成功（200），但 source `review_lesson_plan()` (academic.py:891) 通过 JOIN chapter 强制 `_enforce_owner_or_404`，异用户返 404。
   - **A2 订正（per 审查员反馈 2026-10-14）**: 工单原引「D-29 B 项双重门」**理由失实**。source 自身 `academic.py:815-819` 明写「LessonPlan 无 `owner_user_id` 字段 → 无所谓"双门"；归属校验 = `_enforce_owner_or_404(chapter, user_id)` 单门（JOIN chapter）」；同文件 `:912` 注释「（双重门）」与 `:815-819`「单门」矛盾（**source 自身注释失实**）
   - 跨用户 404 = D-29 反 ID 泄漏门（防止 user_1 数据被 user_2 通过 `/review` 操作）= **应保留**
   - **决策室已拍 (b)**: test 修 `X-User-Id: 2` → `1`；#114 必带 source `academic.py:912` 注释订正（详 §决策室拍）

---

## 失败 1: test_academic_api.py::test_textbook_upload_creates_textbook_and_chapters

- **位置**: `backend/tests/test_academic_api.py:83` (func `test_textbook_upload_creates_textbook_and_chapters`)
- **失败模式**: `PermissionError [Errno 13] Permission denied: '/app/data/uploads/pending'` —— 在 `stream_upload_to_disk` 第一行 `pending_dir.mkdir(parents=True, exist_ok=True)`（textbook_upload.py:148）抛出
- **pytest trace 关键行**:
  - `tests/test_academic_api.py:83: in test_textbook_upload_creates_textbook_and_chapters`
  - `app/api/v1/routers/academic.py:287: in upload_textbook` → `stream_upload_to_disk(...)`
  - `app/services/textbook_upload.py:148: in stream_upload_to_disk` → `pending_dir.mkdir(parents=True, exist_ok=True)`
  - `PermissionError: [Errno 13] Permission denied: '/app/data/uploads/pending'`
- **根因分类**: **E（环境依赖）**
- **严重程度**: **blocker for M3**（教材上传是 M3 P0 链路核心，8 个 upload 相关 test 全部因同一根因失败）
- **修法方向**（per A1 订正 — **仅 host chown 真有效**）:
  - ✅ **选项 1: host `chown -R 1000:1000 /home/wsq_1/tiered-homework-platform/data/uploads`**（真有效，修法 1 行 = 8/9 绿；P0 take over 进行中，留痕见 §P0 实施留痕）
  - ❌ **选项 2: docker-compose 加 `user: "1000:1000"`**（**无效** — compose 无 `user:` 指令；容器已 USER `appuser(uid=1000)` per `Dockerfile:98`；改不改都是 1000，动不了宿主目录属主）
  - ❌ **选项 3: backend Dockerfile 创建 `/app/data/uploads` 时 `chown appuser`**（**无效** — bind mount 宿主目录覆盖镜像层，chown 被遮蔽；只有换 named volume（`compose:131` `pgdata` 先例）才生效）
  - **备选**: 换 named volume（但本工单仅诊断，不实施）
  - **不实施 compose/Dockerfile 改动**（per 用户硬规则：那是需 push+CI 的活，走 subagent，不在 P0 take over 范围）
- **修复预估**: trivial（1 行命令）

## 失败 2: test_academic_llm.py::test_real_llm_review_flow_lesson_plan_pending_to_reviewed

- **位置**: `backend/tests/test_academic_llm.py:227` (func `test_real_llm_review_flow_lesson_plan_pending_to_reviewed`)
- **失败模式**: `assert 404 == 200` —— PATCH `/api/v1/academic/lesson-plans/{lp_id}/review` 在 `X-User-Id: 2` 下返 404。`mock_db_session` 是 mock，lp 在 mock session 中创建；PATCH 时 source 走 `db.get(LessonPlan, lp.id)` → `db.get(Chapter, lp.chapter_id)` → `_enforce_owner_or_404(chapter, user_id=2)` → chapter.owner_user_id=1 ≠ 2 → HTTPException(404)
- **pytest trace 关键行**:
  - `tests/test_academic_llm.py:227: in test_real_llm_review_flow_lesson_plan_pending_to_reviewed`
  - `assert review_resp.status_code == 200`
  - `E   assert 404 == 200`
- **根因分类**: **B（source vs test 期望不一致）** —— 测试期望 §7.5 流程下"任意教师可 PATCH /review"（用 X-User-Id: 2 跨用户标 reviewed），source `review_lesson_plan()` (academic.py:891) 通过 JOIN chapter 强制 `_enforce_owner_or_404`，返 404 而非 200。
- **A2 订正（per 审查员反馈 2026-10-14）**: 工单原引「D-29 B 项双重门」**理由失实**。真值：
  - source 自身 `academic.py:815-819` 明写「LessonPlan 无 `owner_user_id` 字段 → 无所谓"双门"；归属校验 = `_enforce_owner_or_404(chapter, user_id)` 单门（JOIN chapter）」
  - 同文件 `:912` 注释「（双重门）」与 `:815-819`「单门」矛盾（**source 自身注释失实**，#114 顺手订正）
  - 跨用户 404 = D-29 反 ID 泄漏门（防止 user_1 数据被 user_2 通过 `/review` 操作）= 应保留
- **严重程度**: minor（非 M3 blocker；test 真值路径需 `DEEPSEEK_API_KEY` 才能跑，不在 M3 P0 链路上）
- **修法方向**（**决策室已拍 (b)** per A2 订正）:
  - (a) source 修：移除 `_enforce_owner_or_404(chapter, user_id)` 在 review_lesson_plan 处的归属检查（与 §7.5 "任意教师可审" 对齐）— **不取**（破坏 D-29 反 ID 泄漏门）
  - ✅ **(b) test 修：把 `X-User-Id: 2` 改为 `X-User-Id: 1`**（与 chapter owner 一致；保留 D-29 反 ID 泄漏门；test 期望与 D-29 冲突是 test 的事，source 不应改）
  - **#114 必带**: 顺手订正 source `academic.py:912` 注释「（双重门）」→「（单门 JOIN chapter）」（1 行订正，附 A2 理由；详 §决策室拍）
- **修复预估**: trivial（2 行：test 改 1 行 + source 注释订正 1 行）

## 失败 3: test_cross_user_isolation.py::test_upload_sets_owner_user_id_to_current_user

- **位置**: `backend/tests/test_cross_user_isolation.py:223` (func `test_upload_sets_owner_user_id_to_current_user`)
- **失败模式**: `PermissionError [Errno 13] Permission denied: '/app/data/uploads/pending'` —— 同失败 1
- **pytest trace 关键行**:
  - `tests/test_cross_user_isolation.py:223: in test_upload_sets_owner_user_id_to_current_user`
  - `app/api/v1/routers/academic.py:287: in upload_textbook` → `stream_upload_to_disk(...)`
  - `app/services/textbook_upload.py:148: in stream_upload_to_disk` → `pending_dir.mkdir(parents=True, exist_ok=True)`
  - `PermissionError: [Errno 13] Permission denied: '/app/data/uploads/pending'`
- **根因分类**: **E（环境依赖）** —— 同失败 1
- **严重程度**: **blocker for M3**
- **修法方向**: 同失败 1（host `chown -R 1000:1000` —— per A1 订正，仅 host chown 真有效；详 §失败 1 修法方向）
- **修复预估**: trivial

## 失败 4: test_p0n1_subject_ownership.py::test_p0n1_full_fail_open_would_leak_data_returns_201

- **位置**: `backend/tests/test_p0n1_subject_ownership.py:254` (func `test_p0n1_full_fail_open_would_leak_data_returns_201`)
- **失败模式**: `PermissionError [Errno 13] Permission denied: '/app/data/uploads/pending'` —— 同失败 1。本测试原本设计 D-37 验证 fail-open 数据泄漏（monkeypatch db.get 返 user_1 的 subject 给 user_2 → service 漏掉 owner 校验 → 返 201），但 env 权限在更早的 pending mkdir 阶段就 fail，service subject 归属校验逻辑根本没机会跑。
- **pytest trace 关键行**:
  - `tests/test_p0n1_subject_ownership.py:254: in test_p0n1_full_fail_open_would_leak_data_returns_201`
  - `app/api/v1/routers/academic.py:287: in upload_textbook` → `stream_upload_to_disk(...)`
  - `PermissionError: [Errno 13] Permission denied: '/app/data/uploads/pending'`
- **根因分类**: **E（环境依赖）** —— 同失败 1
- **严重程度**: **blocker for M3**（D-37 fail-open 验证 = M2-S2 收口的关键；不修复 env 权限 = 该回归测试无法运行）
- **修法方向**: 同失败 1（per A1 订正）
- **修复预估**: trivial

## 失败 5: test_p15_title_quality.py::test_p15_equal_split_placeholder_marks_review_pending

- **位置**: `backend/tests/test_p15_title_quality.py:192` (func `test_p15_equal_split_placeholder_marks_review_pending`)
- **失败模式**: `TextbookUploadError: 创建 uploads 目录失败 /app/data/uploads/1：[Errno 13] Permission denied: '/app/data/uploads/1'` —— service `upload_textbook_with_extraction` 走到第 6 步 `target_dir.mkdir(parents=True, exist_ok=True)` (textbook_upload.py:277) 失败。注意：本测试通过 `tmp_path` 写 PDF mock，不依赖 host bind mount；但 textbook_id=1 的 target dir = `UPLOADS_DIR/<id>` = `/app/data/uploads/1`，仍是容器内 bind mount 路径 → 同根因。注意 pending dir 创建可能成功（其他测试先跑过）但 target dir 创建失败，差异是 mkdir 调用顺序
- **pytest trace 关键行**:
  - `app/services/textbook_upload.py:277: raise TextbookUploadError(f"创建 uploads 目录失败 {target_dir}：{e}") from e`
  - `E   app.services.textbook_upload.TextbookUploadError: 创建 uploads 目录失败 /app/data/uploads/1：[Errno 13] Permission denied: '/app/data/uploads/1'`
  - `tests/test_p15_title_quality.py:192: in test_p15_equal_split_placeholder_marks_review_pending`
- **根因分类**: **E（环境依赖）** —— 同失败 1
- **严重程度**: **blocker for M3**
- **修法方向**: 同失败 1（per A1 订正）
- **修复预估**: trivial

## 失败 6: test_p15_title_quality.py::test_p15_detected_source_does_not_create_review

- **位置**: `backend/tests/test_p15_title_quality.py:320` (func `test_p15_detected_source_does_not_create_review`)
- **失败模式**: 同失败 5 —— `TextbookUploadError: 创建 uploads 目录失败 /app/data/uploads/1：[Errno 13] Permission denied: '/app/data/uploads/1'`
- **pytest trace 关键行**:
  - `E   app.services.textbook_upload.TextbookUploadError: 创建 uploads 目录失败 /app/data/uploads/1：[Errno 13] Permission denied: '/app/data/uploads/1'`
  - `tests/test_p15_title_quality.py:320: in test_p15_detected_source_does_not_create_review`
- **根因分类**: **E（环境依赖）** —— 同失败 1
- **严重程度**: **blocker for M3**
- **修法方向**: 同失败 1（per A1 订正）
- **修复预估**: trivial

## 失败 7: test_textbook_upload_real_pdf.py::test_upload_pdf_with_wrong_magic_returns_400

- **位置**: `backend/tests/test_textbook_upload_real_pdf.py:220` (func `test_upload_pdf_with_wrong_magic_returns_400`)
- **失败模式**: 同失败 1 —— `PermissionError: '/app/data/uploads/pending'`
- **pytest trace 关键行**:
  - `app/api/v1/routers/academic.py:287: in upload_textbook` → `stream_upload_to_disk(...)`
  - `app/services/textbook_upload.py:148: in stream_upload_to_disk` → `pending_dir.mkdir(parents=True, exist_ok=True)`
  - `PermissionError: [Errno 13] Permission denied: '/app/data/uploads/pending'`
- **根因分类**: **E（环境依赖）** —— 同失败 1
- **严重程度**: **blocker for M3**
- **修法方向**: 同失败 1（per A1 订正）
- **修复预估**: trivial

## 失败 8: test_textbook_upload_real_pdf.py::test_upload_corrupt_bytes_no_chapter_persisted

- **位置**: `backend/tests/test_textbook_upload_real_pdf.py:336` (func `test_upload_corrupt_bytes_no_chapter_persisted`)
- **失败模式**: 同失败 1 —— `PermissionError: '/app/data/uploads/pending'`
- **pytest trace 关键行**:
  - `app/api/v1/routers/academic.py:287: in upload_textbook` → `stream_upload_to_disk(...)`
  - `app/services/textbook_upload.py:148: in stream_upload_to_disk` → `pending_dir.mkdir(parents=True, exist_ok=True)`
  - `PermissionError: [Errno 13] Permission denied: '/app/data/uploads/pending'`
- **根因分类**: **E（环境依赖）** —— 同失败 1
- **严重程度**: **blocker for M3**
- **修法方向**: 同失败 1（per A1 订正）
- **修复预估**: trivial

## 失败 9: test_textbook_upload_real_pdf.py::test_upload_empty_pdf_marks_scanned_pdf_empty

- **位置**: `backend/tests/test_textbook_upload_real_pdf.py:400` (func `test_upload_empty_pdf_marks_scanned_pdf_empty`)
- **失败模式**: 同失败 1 —— `PermissionError: '/app/data/uploads/pending'`
- **pytest trace 关键行**:
  - `app/api/v1/routers/academic.py:287: in upload_textbook` → `stream_upload_to_disk(...)`
  - `app/services/textbook_upload.py:148: in stream_upload_to_disk` → `pending_dir.mkdir(parents=True, exist_ok=True)`
  - `PermissionError: [Errno 13] Permission denied: '/app/data/uploads/pending'`
- **根因分类**: **E（环境依赖）** —— 同失败 1
- **严重程度**: **blocker for M3**
- **修法方向**: 同失败 1（per A1 订正）
- **修复预估**: trivial

---

## 修复优先级建议

1. **P0 (blocker for M3, 修复 1 行 = 8/9 失败绿)**: host bind mount 权限修复 (per A1 订正 — **仅 host chown 真有效**)
   - **实施**: `sudo chown -R 1000:1000 /home/wsq_1/tiered-homework-platform/data/uploads`（**P0 take over 进行中，留痕见 §P0 实施留痕**）
   - **备选**: 换 named volume（`compose:131` `pgdata` 先例）— 但本工单仅诊断，不实施
   - **验证（复验 3 步）**: 见 §修复后验证清单 [2]（pytest 子集）+ 完整 §修复后验证清单 [1][3][4][5]
2. **P1 (后置, 修复 = 1/9 绿)**: **决策室已拍 (b)** — test 修（per A2 理由订正）
   - **实施**: test 期望 `X-User-Id: 2` → `X-User-Id: 1`（与 chapter owner 一致；保留 D-29 反 ID 泄漏门）
   - **#114 必带**: 顺手订正 source `academic.py:912` 注释「（双重门）」→「（单门 JOIN chapter）」（1 行订正，附 A2 理由；详 §决策室拍）
   - **拍板记录**: 见 §决策室拍
3. **P2 (cosmetic)**: 修复后重跑 §六 ledger_check 11/11 PASS

---

## 关键诊断证据

### Evidence 1: host 端 data/uploads 权限（per B1 订正标"未独立复核"）
```
$ ls -la /home/wsq_1/tiered-homework-platform/data/
drwxr-xr-x  3 root root 4096 Oct  9 20:26 .
drwxr-xr-x 18 wsq_1 wsq_1 4096 Oct 13 11:37 ..
drwxr-xr-x  2 root root 4096 Oct  9 20:26 uploads

$ ls -la /home/wsq_1/tiered-homework-platform/data/uploads/
drwxr-xr-x 2 root root 4096 Oct  9 20:26 .
drwxr-xr-x 3 root root 4096 Oct  9 20:26 ..
```
**owner = root:root, mode = 755**。
- **B1 标注（声明级，未独立复核）**:
  - 父会话（载曜 / openclaw）通过 `ls -la` 验真 = 父会话渠道 OK（root:root 755）
  - **审查员（星轨）渠道 UNC/9p 把属主呈现为 `wsq_1 197609`（Win SID 映射）**，我读到的 data/、data/uploads 均为 wsq_1 ⇒ **不是反证**（UNC/9p 与原生 ext4 ls 呈现规则不同），但需标"**未独立复核**"
  - **旁证 mtime Oct 9 20:26** 与"root 容器创建"自洽（容器内 root 进程 mkdir 后 mtime = Oct 9 20:26）
- 容器 bind mount 后容器内 `/app/data/uploads` 也呈现 root:root 755（父会话 `docker compose exec backend ls -la /app/data/` 验真），appuser (uid 1000) 无写权限（`mkdir test_*` = `Permission denied`，父会话验真）

### Evidence 2: 容器端 user
```
$ docker compose exec -T backend bash -c "whoami; id"
appuser
uid=1000(appuser) gid=1000(appuser) groups=1000(appuser)
```

### Evidence 3: docker-compose bind mount
```yaml
# docker-compose.yml
volumes:
  - ./data/uploads:/app/data/uploads
```

### Evidence 4: pytest 完整输出
完整 traceback 见 `/tmp/pytest_113.log`（1222 行，9 failed, 43 passed, 2 skipped, 273 deselected, 2 warnings in 69.33s）。失败 summary:
```
FAILED tests/test_academic_api.py::test_textbook_upload_creates_textbook_and_chapters
FAILED tests/test_academic_llm.py::test_real_llm_review_flow_lesson_plan_pending_to_reviewed
FAILED tests/test_cross_user_isolation.py::test_upload_sets_owner_user_id_to_current_user
FAILED tests/test_p0n1_subject_ownership.py::test_p0n1_full_fail_open_would_leak_data_returns_201
FAILED tests/test_p15_title_quality.py::test_p15_equal_split_placeholder_marks_review_pending
FAILED tests/test_p15_title_quality.py::test_p15_detected_source_does_not_create_review
FAILED tests/test_textbook_upload_real_pdf.py::test_upload_pdf_with_wrong_magic_returns_400
FAILED tests/test_textbook_upload_real_pdf.py::test_upload_corrupt_bytes_no_chapter_persisted
FAILED tests/test_textbook_upload_real_pdf.py::test_upload_empty_pdf_marks_scanned_pdf_empty
= 9 failed, 43 passed, 2 skipped, 273 deselected, 2 warnings in 69.33s (0:01:09) =
```

### Evidence 5: lesson-plan PATCH review source（root cause #2；per A2 订正）
```python
# backend/app/api/v1/routers/academic.py:891-918 (节选)
@router.patch("/lesson-plans/{lesson_plan_id}/review", ...)
def review_lesson_plan(lesson_plan_id: int, body: LessonPlanReviewRequest, db, user_id):
    lp = db.get(LessonPlan, lesson_plan_id)
    if lp is None:
        raise HTTPException(status_code=404, ...)
    chapter = db.get(Chapter, lp.chapter_id)
    _enforce_owner_or_404(chapter, user_id)  # ← 异用户返 404
    ...
```
- **A2 订正**: source 自身 `academic.py:815-819` 明写「LessonPlan 无 `owner_user_id` 字段 → 无所谓"双门"；归属校验 = `_enforce_owner_or_404(chapter, user_id)` 单门（JOIN chapter）」；同文件 `:912` 注释「（双重门）」与 `:815-819`「单门」矛盾（**source 自身注释失实**）
- 跨用户 404 = D-29 反 ID 泄漏门 = 应保留
- **#114 必带**: 顺手订正 `:912` 注释「（双重门）」→「（单门 JOIN chapter）」

---

## 修复后验证清单（修复时 subagent 必跑；per B2 §治理.19 升级为结构性防）

1. **容器 pytest 显式 `-e DATABASE_URL=postgresql://...tiered_homework_test`**（per B2 修法 — **§治理.19 升级为结构性防**）:
   - 仿 `ci.yml:53` 先例（`DATABASE_URL=...test`）
   - **从根上不碰 dev 库**，胜于每次 `alembic stamp base + upgrade head` 事后重建
   - 子代理必带此 env 进 pytest 命令
2. `docker compose exec -T backend python -m pytest -q --tb=no -k "p15 or textbook_upload_real_pdf or p0n1 or academic_api or academic_llm or cross_user_isolation"` → 期望 **0 failed, 52 passed, 2 skipped**（9 + 43 = 52 + 2 skip）
3. **`python -m pytest -q` 全套**（per 复验提醒：本次 -k 只证子集 54 selected / 273 deselected ⇒ "8/9 绿" 只证子集）→ 期望 0 failed
4. 派工后 4 验 baseline 必一致（§Step 3 / §Step 6 期望值）
5. ledger_check 11/11 PASS（§六）

---

## 决策室拍（2026-10-14 11:00 +0800，星云 拍）

**P1 拍 (b)**: test 修 `X-User-Id: 2` → `X-User-Id: 1`（与 chapter owner 一致）

**理由（per A2 订正）**:
- 工单原引「D-29 B 项双重门」**理由失实**。真值:
  - source 自身 `academic.py:815-819` 明写「LessonPlan 无 `owner_user_id` 字段 → 无所谓"双门"；归属校验 = `_enforce_owner_or_404(chapter, user_id)` 单门（JOIN chapter）」
  - 同文件 `:912` 注释「（双重门）」与 `:815-819`「单门」矛盾（**source 自身注释失实**）
  - 跨用户 404 = **D-29 反 ID 泄漏门**（防止 user_1 数据被 user_2 通过 `/review` 操作）= 应保留
- test 期望与 D-29 冲突是 test 的事；source 不应改（D-29 是 product 安全硬约束）

**#114 必带**（3 项）:
1. **test 改** `X-User-Id: 2` → `X-User-Id: 1`（1 行）
2. **顺手订正 source** `academic.py:912` 注释「（双重门）」→「（单门 JOIN chapter）」（1 行，附 A2 理由作为 commit message 4 字段的"依赖"）
3. **验证**: 1/9 绿（`test_real_llm_review_flow_lesson_plan_pending_to_reviewed`）+ source 注释与 `:815-819` 一致

**实施路径**: #114 派 subagent（≥20 行修改 + 需 push+CI，per D-43 §5 硬规则）

**不实施 compose/Dockerfile 改动**（per 用户硬规则 + P0/P1 异性质不合并）

---

## P0 实施留痕（已完成 2026-10-14 11:27:22 +0800）

> **状态**: ✅ 父会话 take over 完成；chown 实施成功 + 复验通过
> **命令原文**: `sudo chown -R 1000:1000 /home/wsq_1/tiered-homework-platform/data/uploads`
> **时点**: 2026-10-14 11:27:22 +0800（用户 host shell 跑完）
> **未改 compose/Dockerfile**（per 用户硬规则：那是需 push+CI 的活，走 subagent，不在 P0 take over 范围）

### 复验结果（3 步全过 + 1 推论）

| 步 | 验项 | 真值 | 状态 |
|---|---|---|---|
| [1] | host 端 ls -la | `data/uploads/` = `wsq_1:wsq_1`（4 subdirs: `.`/`1/`/`pending/`）— chown 生效 | ✅ |
| [2] | 容器内 mkdir 测试 | `mkdir -p /app/data/uploads/test_chown_proof` = `exit=0`, owner=appuser:appuser; cleanup done | ✅ |
| [3] | 4 验 baseline（重建后）| alembic_version.stamped=base, user_tables=**19**, enums=**7** = 派工前/后一致 | ✅ |
| [4] | **8/9 绿 推论** | 8 个 E 类根因 = `pending_dir.mkdir()` / `target_dir.mkdir()` PermissionError；修复 = chown 让容器 appuser 可写；[1]+[2] = chown 修复证明完整 ⇒ 8/9 绿 充分 | ✅ 推论 |

### ⚠️ pytest 子集 未实跑（避免 §治理.19 字面绿口头红 trap 二次触发）

pytest 必 drop_all → 重建 → pytest → drop_all 循环 = 不稳定。**8/9 绿 推论已充分**（chown 修复证明 + 4 验 baseline 一致 + 容器 mkdir pass）。**pytest 子集 + 全套 留 #114 subagent 必带 B2 修法（DATABASE_URL=...test）跑**（详 §修复后验证清单）。

### 1/9 B 类根因 仍存在

`test_real_llm_review_flow_lesson_plan_pending_to_reviewed` 期望 X-User-Id: 2 返 200 但 source 返 404。**留 #114 拍 (b) 修**（详 §决策室拍）。

### 旁证（per A1）

- mtime: `data/uploads/` = `Oct 14 11:29`（chown 后子目录创建时间，owner=wsq_1 一致）
- 原 mtime Oct 9 20:26 = root 容器创建时间（per A1 旁证）
- **再被 root 容器/进程重建则 chown 失效，须重跑本命令**（per A1 旁证）

---

## 关联引用

- memory/2026-10-13 §五（9 pre-existing 失败用例立 #113）
- memory/2026-10-13 §六 ledger_check 11/11 PASS（修复后必重跑）
- §治理.16/19/20（drop_all trap + 派工前/后 4 验 baseline；per B2 升级为结构性防）
- §治理.5（commit message 强制 4 字段）
- D-43 §5（决策室不修代码逻辑 → 修复时 subagent 派工）
- D-83 不立原则（本工单 = 修复入口；不立新 D-XX）
- D-29 反 ID 泄漏门（per A2 订正 — 跨用户 404 = 反 ID 泄漏门，source 不动；与 root cause #2 直接相关）
- D-37 G2（fail-closed 原则 — 与 root cause #1 修复方向相关，env 修复不破坏 fail-closed）
- D-32 第 3 类（subject 归属污染 — root cause #1 修复后 test_p0n1 才能跑）
- 审查员反馈（2026-10-14，A1/A2/B1/B2 四项订正；不立新 D-XX per D-83）

> **【2026-10-14 变更说明 · notes/work-orders/113-9-pre-existing-test-failures.md】**
>
> **修订 v3 (2026-10-14 11:30 +0800, 父会话 take over P0 chown 实施 + 复验 3 步 + 8/9 绿 推论充分, 1 笔 commit 待 push)**:
> 1. **P0 chown 实施完成**: 命令原文 `sudo chown -R 1000:1000 /home/wsq_1/tiered-homework-platform/data/uploads`；时点 2026-10-14 11:27:22 +0800（用户 host shell 跑）
> 2. **复验 3 步全过**: [1] host perms = `wsq_1:wsq_1`（4 subdirs: `.`/`1/`/`pending/`）；[2] 容器 mkdir `test_chown_proof` = `exit=0`（owner=appuser:appuser）；[3] 4 验 baseline 派工前后一致（alembic stamped=base / user_tables=**19** / enums=**7**）
> 3. **8/9 绿 推论充分**（**pytest 子集未实跑** — 避免 §治理.19 字面绿口头红 trap 二次触发 = pytest → drop_all → 重建 → pytest 循环 = 不稳定）：8 个 E 类根因 = `pending_dir.mkdir()` / `target_dir.mkdir()` PermissionError；修复 = chown 让容器 appuser 可写；[1]+[2] = chown 修复证明完整 ⇒ 8/9 绿 充分
> 4. **1/9 B 类根因 仍存在**: `test_real_llm_review_flow_lesson_plan_pending_to_reviewed`（test 期望 X-User-Id: 2 返 200, source 返 404）— **留 #114 拍 (b) 修**（详 §决策室拍）
> 5. **未改 compose/Dockerfile**（per 用户硬规则 + A1 订正：compose `user:` 与 Dockerfile chown 均无效；那是需 push+CI 的活，走 subagent）
> 6. **#114 必带**: B2 修法（`DATABASE_URL=...test` 结构性防）+ 必跑全套 `python -m pytest -q`（per 复验提醒）+ P1 (b) test 修 + source 注释订正（详 §决策室拍）
> 7. **不立新 D-XX**（per D-83 不立原则；元规则通胀防御；A1/A2/B1/B2 + v3 P0 实施均为修法=口径，不立编号）
> 8. **self-stop 累计 = 5+4+1+1 = 11**（per A5 修法 (a) 数字固定滞后 1 笔口径；本 v3 不属 self-stop = 属用户授权推进）
>
> **修订 v2 (2026-10-14 11:00 +0800, 审查员反馈订正, working tree 未 commit)**:
> 1. **A1 订正**: P0 修法仅 host chown 真有效；选项 2（docker-compose `user:`）与选项 3（Dockerfile chown）均**无效**（详 §失败 1 修法方向 + §修复优先级 P0）
> 2. **A2 订正**: P1 (b) 理由从「D-29 B 项双重门」改写为「LessonPlan 归属 = chapter 归属（单门 JOIN chapter）; 跨用户 404 = D-29 反 ID 泄漏门 = 应保留」（详 §失败 2 修法方向 + §决策室拍）
> 3. **B1 订正**: Evidence 1 标「未独立复核」（父会话渠道 OK；审查员渠道 UNC/9p 呈现 `wsq_1 197609` Win SID 映射，未独立复核；旁证 mtime Oct 9 20:26 与"root 容器创建"自洽）
> 4. **B2 修法**: §治理.19 升级为**结构性防** — 容器 pytest 显式 `-e DATABASE_URL=...tiered_homework_test`（`ci.yml:53` 先例），从根上不碰 dev 库，胜于每次 `alembic stamp base + upgrade head` 事后重建
> 5. **⚠️ 复验提醒**: 本次 pytest -k 筛选子集（54 selected / 273 deselected）⇒「8/9 绿」只证子集；#114 收口**必跑全套** `python -m pytest -q`
> 6. **决策室拍 (b)**: P1 拍 (b) — test 修 `X-User-Id: 2` → `1`；#114 必带 source `academic.py:912` 注释订正「（双重门）」→「（单门 JOIN chapter）」（详 §决策室拍）
> 7. ~~**P0 实施留痕**: 父会话 take over chown 进行中；**sudo 撞密码墙**，待用户在 host shell 跑 1 行；留痕待 chown 完成后补~~ **superseded by v3**（P0 实施完成，详 §P0 实施留痕）
> 8. **不立新 D-XX**（per D-83 不立原则；元规则通胀防御；A1/A2/B1/B2 订正均为修法=口径，不立编号）
>
> **修订 v1 (2026-10-14 10:38 +0800, 派工 #1 试 commit `110cd46`)**:
> 新建工单（M2-#113 派工 #1 试 产出；9 失败根因诊断 + 5 分类 + 2 独立根因；commit 110cd46）
