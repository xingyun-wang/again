# M3-B2 brief: W1 ORDER BY (生成可复现) + 回归测试

> **派工人**：载曜｜**派工日**：2026-10-19｜**批准**：星云（"B1, B2, D2 可以起"）
> **阻塞**：无（与 C1 / D3 不冲突；可立即起；并入 S-3 之前）
> **回执 commit message 必带**：`[origin-push]`（WAKEUP 8 步授权机制）

---

## §1 任务

- `backend/app/services/question_generator.py:199-204` 加 `.order_by(Question.id)`
- **目的**：抽题顺序可复现（同输入 = 同输出 = 同一学生拿同一份）
- **写回归测试** = 新建 `backend/tests/services/test_question_generator.py`（现有没直接测 generator 的文件）

## §2 ORDER BY 列选择（4 法核源）

| 选项 | 评估 | 决定 |
|------|------|------|
| `Question.id` | 主键；最稳的复现方式 | ✅ **采用** |
| `Question.created_at` | 有同秒入库可能；不稳 | ❌ 不用 |
| `Question.difficulty` | 业务字段；可能被改 | ❌ 不用（虽然分桶前 ORDER BY 也行，但 id 即可） |

**结论**：`.order_by(Question.id.asc())`（asc = 主键升序）

## §3 4 法核源（必跑 + 必报）

| 项 | 文件 / 实际 | 4 法核源结果 |
|----|------|---------------|
| 实际修改位置 | `backend/app/services/question_generator.py:199-204` | 199 = `# 1. 查题库(按 owner + chapter 过滤)` 注释；200-203 = `db.query(Question).filter(...).all()` 查询 |
| Query 上下文 | `from app.models import Assignment, AssignmentItem, Question`（:201）| OK |
| 测试文件 | `find backend/tests -name "test*question*" -o -name "test*generator*"` | 现有 = `test_question_image.py`（model）/ `test_question_pool_fixture.py`（fixture）— **没有直接测 generator 的文件** = 新建 `test_question_generator.py` |
| 数据库 | 容器内 `tiered_homework_test`（per §治理.19）| 显式 `-e DATABASE_URL=postgresql+psycopg://...tiered_homework_test` |

## §4 必报项（per D-43-X = 4 法核源 + 物理可达证据）

1. **CI run #**（ruff + mypy + pytest）+ commit SHA
2. **ORDER BY 列 + 升降**（期望 `Question.id ASC`）
3. **加 ORDER BY 前后**抽题顺序是否变化（**基线对比**：同 seed 跑 2 次 = 顺序一致）
4. **pytest 跑测试库** = 全绿 + **不污染 dev 库**（per §治理.19 显式切 test 库）
5. **回归测试 case 数** + 覆盖什么（建议：同输入 → 同输出 / 抽题顺序可复现 / diff 难度不变 / ORDER BY 列名）
6. **git status + diff stat**（期望 2 文件：1 改 question_generator.py + 1 新建 test_question_generator.py）

## §5 派工回执必带（**不写 = 拒收**）

- commit SHA
- CI run #（ruff + mypy + pytest）
- pytest 输出（**测试库**，全绿，**显式 -e DATABASE_URL** = 不污染 dev 库）
- 同 seed 跑 2 次顺序一致证据（diff 列表 = 空）
- 回归测试 case 数 + 覆盖项
- 报告命令用 4 法核源（**不写"我以为"**）

## §6 同步说明（**不需要 subagent 做**）

- 与本 brief **独立**：
  - B1 (IA-1 导航) = 前端；本 brief = 后端
  - D2 (W5 PDF 嵌图) = 后端 PDF；本 brief = 后端 ORDER BY
- A2 (0012 迁移) 排在 A1 批后；本 brief 不抢 A2 工作
- A1+1 commit `f032607` §3.1 D3 依赖改"C1 + C2"——**本 brief 仍可立即起**（ORDER BY 与 0012 schema 无关）

## §7 4 边界（**禁止触碰**）

- 不改 0012 迁移（属 A2）
- 不改 Question model（除非 ORDER BY 必须改 index；当前不需要）
- 不动 batch 业务（属 A2）
- 不动 Choice / AssignmentItem model

---

> **【2026-10-19 14:4x 变更说明 · plans/M3-B2-W1-ORDER-BY-brief.md】**
>
> **修订**：新建（M3 派工 brief；A1+1 后可起；星云 14:37 批 "B1, B2, D2 可以起"）
> **内容**：1 任务 / 2 ORDER BY 列 / 3 4 法核源 / 4 必报项 / 5 派工回执 / 6 同步 / 7 4 边界
> **法源依据**：
> - 交接书 §4（W1 ORDER BY 排在并行段；不阻塞切片；并入 S-3 之前）
> - A1+1 commit `f032607` §3.1 D3 依赖改 "C1 + C2"（本 brief 不抢 A2 工作）
> - D-17（subagent 写代码 / 主聊天不写大段）
> - D-43-X（4 法核源 + 物理可达证据）
> - §治理.19（容器 pytest 显式切测试库）
> **派工范围**：仅 `question_generator.py` 1 行 + 新建 1 测试文件；其他文件不动
> **来源**：A1+1 commit `f032607` + 核源 exec 输出（question_generator.py 199-204 + 无直接测 generator 的文件）
