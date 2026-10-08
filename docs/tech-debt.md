# Tech Debt — mypy pre-existing errors（M2 启动期清查）

> **最后更新**：2026-10-08 21:40（§十八 配套；N1 判决后从陈旧镜像的 5 errors 修正为 HEAD 真值 11 errors）
> **维护规则**：每次 ruff / mypy 跑前必先 grep `tech-debt` 是否过期；过期未登记 = 失实
> **关联元规则**：D-43 §5（决策室不修代码逻辑） / D-49（narrowing cast 实证类） / D-44（mypy strict 模式要求）

---

## 1. mypy pre-existing 11 errors（HEAD 真值；2026-10-07 收工时已存在；S0-4 修法范围外）

按根因分 5 类 / 11 errors：

| # | 文件:行 | 错误数 | 错误类型 | 根因 | 修复方向 |
|---|---|---|---|---|---|
| 1 | `backend/app/services/textbook_upload.py:264` | 1 | `"Subject" has no attribute "owner_user_id"` [attr-defined] | Subject 模型缺 `owner_user_id` 字段 | Subject schema 加 `owner_user_id: Mapped[int]` + Alembic 迁移 |
| 2 | `backend/app/api/v1/routers/academic.py:37` | 6 | `Module "app.api.v1.schemas.academic" has no attribute "Question{Create,Difficulty,ListResponse,Read,Type,Update}"` [attr-defined] | `schemas/academic.py` 缺 Question* 系列定义 | 补齐 schemas（per D-M2-2 拍板 (a) CSV 导入） |
| 3 | `backend/app/api/v1/routers/academic.py:66` | 2 | `Module "app.models" has no attribute "{Choice,Question}"` [attr-defined] | `app/models/__init__.py` 或 `academic.py` 模型文件缺 Choice + Question 导出 | 补模型定义 + `__init__.py` 导出 |
| 4 | `backend/app/api/v1/routers/academic.py:81` | 1 | `Module "app.models" has no attribute "QuestionDifficulty"` [attr-defined] | 同 #3 | 同 #3 |
| 5 | `backend/app/api/v1/routers/academic.py:84` | 1 | `Module "app.models" has no attribute "QuestionType"` [attr-defined] | 同 #3 | 同 #3 |

**实证命令**（@取数时刻 2026-10-08 21:35；docker exec thp-backend = HEAD 同步）：

```bash
$ docker exec thp-backend bash -c "cd /app && python3 -m mypy app/ 2>&1" | grep -E ":\d+: error:"
app/services/textbook_upload.py:264: error: "Subject" has no attribute "owner_user_id"  [attr-defined]
app/api/v1/routers/academic.py:37: error: Module "app.api.v1.schemas.academic" has no attribute "QuestionCreate"  [attr-defined]
app/api/v1/routers/academic.py:37: error: Module "app.api.v1.schemas.academic" has no attribute "QuestionDifficulty"  [attr-defined]
app/api/v1/routers/academic.py:37: error: Module "app.api.v1.schemas.academic" has no attribute "QuestionListResponse"  [attr-defined]
app/api/v1/routers/academic.py:37: error: Module "app.api.v1.schemas.academic" has no attribute "QuestionRead"  [attr-defined]
app/api/v1/routers/academic.py:37: error: Module "app.api.v1.schemas.academic" has no attribute "QuestionType"  [attr-defined]
app/api/v1/routers/academic.py:37: error: Module "app.api.v1.schemas.academic" has no attribute "QuestionUpdate"  [attr-defined]
app/api/v1/routers/academic.py:66: error: Module "app.models" has no attribute "Choice"  [attr-defined]
app/api/v1/routers/academic.py:66: error: Module "app.models" has no attribute "Question"  [attr-defined]
app/api/v1/routers/academic.py:81: error: Module "app.models" has no attribute "QuestionDifficulty"  [attr-defined]
app/api/v1/routers/academic.py:84: error: Module "app.models" has no attribute "QuestionType"  [attr-defined]
Found 11 errors in 2 files (checked 31 source files)
```

---

## 2. 状态

- **HEAD 真值 = 11 errors**（不是陈旧镜像的 5 errors；§十七登记的 5 基于 N1 判决前的陈旧镜像，已修正）
- **不在 M2 启动路径** = M0 / M1 残留（pre-existing；M1-B B.0/B.1/B.2/B.3 收口前 M1-B 末段加入但未清；review2 baseline B1 修正模式后仍未消）
- **未触碰** = 11 errors 均在 S0-4 修法范围外（S0-4 只动 twain.py + schemas/twain.py + test_twain_mock.py）
- **影响范围**：
  - `mypy app/api/v1/schemas/twain.py app/api/v1/routers/twain.py`（2 新文件 + transitive textbook_upload）= **1 error**（textbook_upload.py:264；新文件本身 mypy-clean）
  - `mypy app/`（全 app）= **11 errors**（5 unique file:line）
  - **入场闸 `ruff check app tests && mypy app` = 不可能绿**

---

## 3. 处置方案

| 选项 | 何时 | 范围 | 推荐 |
|---|---|---|---|
| (a) **修** | M2-S1 启动前 | 补 `schemas/academic.py` + `models/` + Subject schema | ✅ |
| (b) **跟踪** | M3 上传+评分 阶段 | mypy strict 模式要求时再修 | (fallback) |
| (c) **忽略** | — | 不推荐（持续累积 + 入场闸永久红 + N1 类错）| ❌ |

**默认**：(a) 修；S1 启动 brief `plans/M2-A.1-brief.md` 应包含 mypy 残留修复子任务（per 决策书 §6 启动清单第 4 项）。

---

## 4. 关联

- **决策书**：`docs/M2-kickoff-decision.md §7.2 拍板记录（D-M2-2）` 拍板 = (a) CSV 导入
- **D-49**：narrowing cast 实证类
- **D-44**：mypy strict 模式要求
- **N1 判决**（§十八）：`tech-debt.md` 行号必须与 HEAD mypy 真值一致；本笔已用 ledger_check check 10 机器化（双向核对）

---

## 5. 修复参考

- `textbook_upload.py:264`：Subject 模型加 `owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))` + Alembic 迁移
- `academic.py:37`：补 `schemas/academic.py`（QuestionCreate / QuestionDifficulty / QuestionListResponse / QuestionRead / QuestionType / QuestionUpdate）
- `academic.py:66/81/84`：补 `models/academic.py` 或 `app/models/__init__.py`（Choice / Question / QuestionDifficulty / QuestionType）
- 推荐改法 = 重构 + 类型签名收紧；不要用 `# type: ignore` 掩盖

---

**变更说明**（D-77 元规则）：见 `notes/changelog/tech-debt.md`（变更说明不与文件同体）
