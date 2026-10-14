# #113 — 9 pre-existing 失败用例根因诊断工单

> **状态**: 根因诊断完成 / 修复待 #114 拍
> **创建**: 2026-10-14
> **触发**: memory/2026-10-13 §五（9 pre-existing 失败用例）
> **诊断真值**: pytest 输出见 `/tmp/pytest_113.log`（commit `4eec216` / `c0be4ad` 后运行，容器 PG，9 failed, 43 passed, 2 skipped, 273 deselected, 2 warnings in 69.33s）
> **派工 brief**: `plans/M2-#113-诊断-brief.md`（commit `4eec216`）
> **不立 D-XX**（per D-83 不立原则；元规则通胀防御）
> **诊断者**: subagent（派工 #1 试 per corrective-rule-1-dispatch-protocol）

## 总体盘

| 分类 | 数量 | 严重 blocker | 备注 |
|---|---|---|---|
| A. 数据 fixture 问题 | 0 | 0 | — |
| B. source code bug | 1 | 0 | test_real_llm_review_flow 跨用户 review 期望 vs owner 强制 |
| C. mock / patch 失配 | 0 | 0 | — |
| D. migration / schema 漂移 | 0 | 0 | — |
| E. 环境依赖（host bind mount 权限） | 8 | 8（**blocker for M3**） | 单一根因 + 8 个不同测试 |
| **合计** | **9** | **8** | E 根因 1 个，影响 8 个 test |

**关键发现**：9 个失败实质上 = **2 个独立根因**：
1. **根因 #1（8/9 失败）**：host `data/uploads/` 由 `root:root` 拥有，mode 755；容器 backend 以 `appuser` (uid=1000) 运行；bind mount 后容器内 `/app/data/uploads/` 不可写 → `pending_dir.mkdir()` 直接 PermissionError，service 早期失败。
2. **根因 #2（1/9 失败）**：`test_real_llm_review_flow_lesson_plan_pending_to_reviewed` 测试期望 X-User-Id: 2（异用户）能 PATCH `/lesson-plans/{id}/review` 成功（200），但 source `review_lesson_plan()` (academic.py:891) 通过 JOIN chapter 强制 `_enforce_owner_or_404`，异用户返 404（D-29 B 项设计）。

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
- **修法方向**: 修复 host bind mount 权限 —— `chown -R 1000:1000 /home/wsq_1/tiered-homework-platform/data/uploads`（让容器内 appuser 可写）；或 docker-compose 加 `user: "1000:1000"`；或在 backend Dockerfile 创建 `/app/data/uploads` 时 `chown appuser`。**不实施**（本工单仅诊断）
- **修复预估**: trivial（1 行命令）

## 失败 2: test_academic_llm.py::test_real_llm_review_flow_lesson_plan_pending_to_reviewed

- **位置**: `backend/tests/test_academic_llm.py:227` (func `test_real_llm_review_flow_lesson_plan_pending_to_reviewed`)
- **失败模式**: `assert 404 == 200` —— PATCH `/api/v1/academic/lesson-plans/{lp_id}/review` 在 `X-User-Id: 2` 下返 404。`mock_db_session` 是 mock，lp 在 mock session 中创建；PATCH 时 source 走 `db.get(LessonPlan, lp.id)` → `db.get(Chapter, lp.chapter_id)` → `_enforce_owner_or_404(chapter, user_id=2)` → chapter.owner_user_id=1 ≠ 2 → HTTPException(404)
- **pytest trace 关键行**:
  - `tests/test_academic_llm.py:227: in test_real_llm_review_flow_lesson_plan_pending_to_reviewed`
  - `assert review_resp.status_code == 200`
  - `E   assert 404 == 200`
- **根因分类**: **B（source code bug）** —— 测试期望 §7.5 流程下"任意教师可 PATCH /review"（用 X-User-Id: 2 跨用户标 reviewed），但 source `review_lesson_plan()` (academic.py:891) 通过 JOIN chapter 强制 `_enforce_owner_or_404`，返 404 而非 200。这与 §7.5 "review_status 只允许 pending → reviewed / modified" 的流程硬约束语义不冲突，但 source 多加了"必须是 chapter owner"的归属门。
- **严重程度**: minor（非 M3 blocker；test 真值路径需 DEEPSEEK_API_KEY 才能跑，不在 M3 P0 链路上）
- **修法方向**（决策室拍 — 二选一）:
  - (a) source 修：移除 `_enforce_owner_or_404(chapter, user_id)` 在 review_lesson_plan 处的归属检查（与 §7.5 "任意教师可审" 对齐）；或
  - (b) test 修：把 `X-User-Id: 2` 改为 `X-User-Id: 1`（与 chapter owner 一致），符合 D-29 "跨用户返 404" 设计
- **修复预估**: trivial（1-2 行）

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
- **修法方向**: 同失败 1（chown host dir / docker-compose user:）
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
- **修法方向**: 同失败 1
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
- **修法方向**: 同失败 1
- **修复预估**: trivial

## 失败 6: test_p15_title_quality.py::test_p15_detected_source_does_not_create_review

- **位置**: `backend/tests/test_p15_title_quality.py:320` (func `test_p15_detected_source_does_not_create_review`)
- **失败模式**: 同失败 5 —— `TextbookUploadError: 创建 uploads 目录失败 /app/data/uploads/1：[Errno 13] Permission denied: '/app/data/uploads/1'`
- **pytest trace 关键行**:
  - `E   app.services.textbook_upload.TextbookUploadError: 创建 uploads 目录失败 /app/data/uploads/1：[Errno 13] Permission denied: '/app/data/uploads/1'`
  - `tests/test_p15_title_quality.py:320: in test_p15_detected_source_does_not_create_review`
- **根因分类**: **E（环境依赖）** —— 同失败 1
- **严重程度**: **blocker for M3**
- **修法方向**: 同失败 1
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
- **修法方向**: 同失败 1
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
- **修法方向**: 同失败 1
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
- **修法方向**: 同失败 1
- **修复预估**: trivial

---

## 修复优先级建议

1. **P0 (blocker for M3, 修复 1 行 = 8/9 失败绿)**: host bind mount 权限修复
   - `sudo chown -R 1000:1000 /home/wsq_1/tiered-homework-platform/data/uploads`（或 host `data/`）
   - 验证：8 个 upload 相关 test 全绿；其余 43 passed 保持；2 skipped (real_pdf skipif) 保持
2. **P1 (后置, 修复 = 1/9 绿)**: 决策室拍 test_real_llm_review_flow 走 (a) source 修 还是 (b) test 修
3. **P2 (cosmetic)**: 修复后重跑 §六 ledger_check 11/11 PASS

---

## 关键诊断证据

### Evidence 1: host 端 data/uploads 权限
```
$ ls -la /home/wsq_1/tiered-homework-platform/data/
drwxr-xr-x  3 root root 4096 Oct  9 20:26 .
drwxr-xr-x 18 wsq_1 wsq_1 4096 Oct 13 11:37 ..
drwxr-xr-x  2 root root 4096 Oct  9 20:26 uploads

$ ls -la /home/wsq_1/tiered-homework-platform/data/uploads/
drwxr-xr-x 2 root root 4096 Oct  9 20:26 .
drwxr-xr-x 3 root root 4096 Oct  9 20:26 ..
```
**owner = root:root, mode = 755**。容器 bind mount 后容器内 `/app/data/uploads` 也呈现 root:root 755，appuser (uid 1000) 无写权限。

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

### Evidence 5: lesson-plan PATCH review source（root cause #2）
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
注释明确："M1-B retro 工单 B（D-29 B 项）：JOIN chapter 检查归属（双重门）" —— 是有意设计。

---

## 修复后验证清单（修复时 subagent 必跑）

1. `docker compose exec -T backend python -m pytest -q --tb=no -k "p15 or textbook_upload_real_pdf or p0n1 or academic_api or academic_llm or cross_user_isolation"` → 期望 **0 failed, 52 passed, 2 skipped**（9 + 43 = 52 + 2 skip）
2. `python -m pytest -q` 全套 → 期望 0 failed
3. 派工后 4 验 baseline 必一致（§Step 3 / §Step 6 期望值）
4. ledger_check 11/11 PASS（§六）

---

## 关联引用

- memory/2026-10-13 §五（9 pre-existing 失败用例立 #113）
- memory/2026-10-13 §六 ledger_check 11/11 PASS（修复后必重跑）
- §治理.16/19/20（drop_all trap + 派工前/后 4 验 baseline）
- §治理.5（commit message 强制 4 字段）
- D-43 §5（决策室不修代码逻辑 → 修复时 subagent 派工）
- D-83 不立原则（本工单 = 修复入口；不立新 D-XX）
- D-29 B 项（owner enforcement 双重门 — 与 root cause #2 直接相关）
- D-37 G2（fail-closed 原则 — 与 root cause #1 修复方向相关，env 修复不破坏 fail-closed）
- D-32 第 3 类（subject 归属污染 — root cause #1 修复后 test_p0n1 才能跑）

> **【2026-10-14 变更说明 · notes/work-orders/113-9-pre-existing-test-failures.md】**
> 新建工单（M2-#113 派工 #1 试 产出）。commit 时补 changelog footer。
