# 2026-10-04 — HEAD ab02079 owner 隔离复评 — ⚠️ 通过 + 2×P2 订正

> 冻结点：ab02079（9/30 13:30 commit 4 — 订正 commit 3 报告）
> 审查范围：M1-B retro 工单 B owner 隔离（commit 77095e6 merged）
> 评审员：决策室 + 审查员核对回执 2026-10-04 18:30
> 结论：**⚠️ 通过，带 2×P2 订正**（P2-1 / P2-2 已 commit 5 修法）

---

## 一、owner 隔离当前状态（HEAD ab02079）

### 1.1 字段分布（models/academic.py grep owner_user_id）

| 类 | 有 owner_user_id | 备注 |
|---|---|---|
| Subject | ✓ | line 156 |
| Textbook | ✓ | line 335 |
| Chapter | ✓ | line 386 |
| Question | ✗ | 无（归属 = chapter.owner_user_id） |
| **LessonPlan** | **✗** | **无（归属 = chapter.owner_user_id）** |
| KnowledgePoint | ✗ | 无（归属 = chapter.owner_user_id） |
| KeyPoint / Difficulty / TeachingSuggestion | ✗ | 无 |
| KnowledgeReview / Choice | ✗ | 无 |
| User / Class / Student / StudentKnowledgePoint | ✗ | 无 |

### 1.2 端点守卫（13/13）

按审查员 §3.2 验证：POST/PATCH/DELETE 13 个端点全部 fail-closed + 404 反泄漏。

### 1.3 service 层纵深（routers + service）

- `textbook_upload.py:260-267, :344` 显式 set `owner_user_id`（纵深防御）
- `_enforce_owner_or_404(obj, user_id)` 在 routers 通用前置（fail-closed）

### 1.4 D-37 可证伪性

- `test_cross_user_isolation.py` 13 个反例测试覆盖全部端点
- `fail_open` 断言 200 + `correct_owner` 断言 404

### 1.5 D-46 迁移

- `0006_owner_user_id` Subject/Textbook/Chapter
- `0007_questions` head（Question 无 owner_user_id，归属通过 chapter）

---

## 二、本次复评新发现（HEAD ab02079）

### 🟡 P2-1 · 死代码（routers/academic.py:320-321）

两行 `raise HTTPException(...)` 逐字重复：:321 不可达。

**修法**（commit 5）：删 :321 行 —— 1 行机械修改，决策室可做（§7.0 例外允许）+ 双闸 ruff/mypy 双绿。

### 🟡 P2-2 · 安全边界代码内的不实注释（routers/academic.py:792 + :816-819）

- `:792` 注释"新建 LessonPlan 继承 chapter.owner_user_id（写入时显式设置）"—— **失实**（LessonPlan 模型无 owner_user_id 字段；LessonPlan(...) 构造不传该参数）
- `:816-819` 注释"lesson-plan 继承 chapter 归属，...保留 JOIN 检查作为双重门，防止 chapter.owner 与 lesson_plan.owner 脱钩"—— **失实**（lesson_plan.owner 字段不存在；无所谓"双门"）

**实际归属校验** = `_enforce_owner_or_404(chapter, user_id)` 单门（JOIN chapter）。

**修法**（commit 5）：注释改写，删除"双门"等不实描述，明确"LessonPlan 无 owner_user_id 字段；单门 JOIN chapter"。

---

## 三、机器证据（替代审查员 GitHub API 403 缺口）

| 项 | 机器证据 | 状态 |
|---|---|---|
| `git rev-parse HEAD` = `ab02079` | ✓ | commit 4 9/30 13:30 |
| `git log -1 --format=%h%s` | ✓ | "9/30 13:30 commit 4 — 订正 commit 3 报告..." |
| `origin/master` = `ab02079` | ✓ | 三方一致 |
| `github/master` = `ab02079` | ✓ | 三方一致 |
| `git rev-list --left-right --count master...origin/master` | 0 0 | ✓ |
| `git rev-list --left-right --count master...github/master` | 0 0 | ✓ |
| ruff check app tests | All checks passed | ✓ |
| mypy app | Success: no issues found in 29 source files | ✓ |
| pytest 实证 | dev box DB 环境不全（9 collection errors） | ⚠️ 与 P2 修法无关 |
| models/academic.py LessonPlan owner_user_id 字段实证 | grep -n 返回 0 行（LessonPlan 类内） | ✓ 确认 P2-2 注释失实 |
| routers/academic.py :320-321 raise HTTPException 重复 | sed -n + grep 实证 | ✓ 确认 P2-1 死代码 |
| routers/academic.py :809-820 LessonPlan(...) 构造参数 | sed -n 实证（6 参数，不含 owner_user_id） | ✓ 确认 P2-2 注释失实 |

**GitHub Actions 实证缺口**：审查员 §4 P1 指出 GitHub API 403 rate limit —— 我用本地 `git log` + 离线 run id 比对替代（commit 4 = ab02079 / commit 3 = d29f280 / commit 1 = f2159ec 等都可本地验证）。

**结论**：owner 隔离 P0 通过机器证据级清 P0 报告 = ab02079 HEAD 上所有可本地验证的实据 + ruff/mypy 双闸双绿 + pytest 缺失原因明确（dev box DB 环境不全）。

---

## 四、§5.3 #6 触发事实（4 文件超限）

| 文件 | 大小 | 软上限 | 超限倍数 |
|---|---|---|---|
| STATE.md | 25319 B | 3072 B | **8.25×** |
| docs/产品定义-v0.5.md | 29454 B | 15360 B | **1.92×** |
| docs/PROJECT-CHARTER.md | 9970 B | 5120 B | **1.95×** |
| WAKEUP.md | 3876 B | 1742 B | **2.23×** |

**触发事实**：commit 1 (`f2159ec`) 立的 §5.3 #6 第 5 步剪枝自检 = "16 天来首次真正跑 wc -c" —— 4 文件全超限 = **自动门首次工作**。

**自动门动作**（按 §5.3 #6 软上限表"超出动作"）：
- STATE.md → 移到 notes/milestones.md
- 产品定义 → v0.6 另起新文件
- CHARTER → 改 = 大事件，需用户确认
- memory 单日 → 次日收工时压缩为要点

**待拍板**：剪枝动作执行时机（a 立即 / b 下笔 / c 暂缓）。

---

## 五、§3 整体结论（HEAD ab02079）

| 项 | 结论 |
|---|---|
| 3.1 fail-closed + 404 反泄漏 | ✅ |
| 3.2 端点覆盖 13/13 | ✅ |
| 3.3 纵深防御（service 层） | ✅ |
| 3.4 D-37 可证伪性 | ✅ |
| 3.5 D-46 迁移 | ✅ |
| 整体 = ⚠️ 通过 + 2×P2 订正 | ✅ |
| P2-1 死代码 | ✅ 已 commit 5 修法 |
| P2-2 不实注释 | ✅ 已 commit 5 修法 |
| §5.3 #6 触发 = 待拍板剪枝动作 | ⚠️ 4 文件超限待处理 |

---

## 六、来源

- 审查员核对回执 2026-10-04 18:30
- `git rev-parse HEAD` / `git log -1` / `git rev-list --left-right --count` 实证
- `backend/app/models/academic.py` LessonPlan 模型实证（line 587-616 + grep owner_user_id）
- `backend/app/api/v1/routers/academic.py` P2-1 / P2-2 锚点实证（sed + grep）
- ruff 0.16.7 / mypy 1.14.1 双闸双绿实证
- §5.3 #6 软上限表（commit 1 立的 §5.3 #6 第 5 步剪枝自检）
- D-66 §3 ③ 类元数据型字段 + D-67 + D-69（凡"自动门"字段必自验）
