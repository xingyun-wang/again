# Tech Debt — mypy pre-existing errors（M2 启动期清查）

> **最后更新**：2026-10-08 17:30（§十七 配套；S0-4 修 3 P1 后的 tech-debt 完整登记）
> **维护规则**：每次 ruff / mypy 跑前必先 grep `tech-debt` 是否过期；过期未登记 = 失实
> **关联元规则**：D-43 §5（决策室不修代码逻辑） / D-49（narrowing cast 实证类） / D-44（mypy strict 模式要求）

---

## 1. mypy pre-existing 5 处（容器内 Python 3.11 实测；2026-10-07 收工时已存在；S0-4 修法范围外）

| # | 文件:行 | 错误类型 | 范围 | 修复方向 |
|---|---|---|---|---|
| 1 | `backend/app/services/textbook_upload.py:264` | `"Subject" has no attribute "owner_user_id"` [attr-defined] | 仅 `textbook_upload.py` | Subject 模型加 `owner_user_id` 字段 + migration（影响 Subject schema） |
| 2 | `backend/app/api/v1/routers/academic.py:259` | `Missing named argument "owner_user_id"` [call-arg] | 仅 `academic.py` | 调用点传 `owner_user_id` |
| 3 | `backend/app/api/v1/routers/academic.py:293` | `Argument "extraction_source" incompatible type "str"; expected "Literal[...]"` [arg-type] | 仅 `academic.py` | 类型注解收紧（str → Literal） |
| 4 | `backend/app/api/v1/routers/academic.py:336` | 同 #3 | 仅 `academic.py` | 同 #3 |
| 5 | `backend/app/api/v1/routers/academic.py:547` | `Argument "extraction_source" incompatible type "str"; expected "Literal[...]"` [arg-type]（ChapterDetailResponse） | 仅 `academic.py` | 同 #3 |

**实证命令**（@取数时刻 2026-10-08 17:25；docker exec thp-backend）：

```bash
$ docker exec thp-backend bash -c "cd /app && python3 -m mypy app/ 2>&1 | tail -20"
app/services/textbook_upload.py:264: error: "Subject" has no attribute "owner_user_id"  [attr-defined]
app/api/v1/routers/academic.py:259: error: Missing named argument "owner_user_id" for "upload_textbook_with_extraction"  [call-arg]
app/api/v1/routers/academic.py:293: error: Argument "extraction_source" to "ChapterSummary" has incompatible type "str"; expected "Literal['detected', 'pdfplumber_fallback', 'equal_split_placeholder', 'scanned_pdf_empty']"  [arg-type]
app/api/v1/routers/academic.py:336: error: Argument "extraction_source" to "ChapterSummary" has incompatible type "str"; expected "Literal['detected', 'pdfplumber_fallback', 'equal_split_placeholder', 'scanned_pdf_empty']"  [arg-type]
app/api/v1/routers/academic.py:547: error: Argument "extraction_source" to "ChapterDetailResponse" has incompatible type "str"; expected "Literal['detected', 'pdfplumber_fallback', 'equal_split_placeholder', 'scanned_pdf_empty']"  [arg-type]
Found 5 errors in 2 files (checked 31 source files)
```

---

## 2. 状态

- **不在 M2 启动路径** = M0 / M1 残留（pre-existing 2026-09-28 前后；review2 baseline B1 修正模式后仍未消）
- **未触碰** = 5 处均在 S0-4 修法范围外（S0-4 只动 twain.py + schemas/twain.py + test_twain_mock.py）
- **影响范围**：
  - `mypy app/api/v1/schemas/twain.py app/api/v1/routers/twain.py`（2 新文件 + transitive textbook_upload）= **1 error**（textbook_upload.py:264；新文件本身 mypy-clean）
  - `mypy app/`（全 app）= **5 errors**（上述）
  - **入场闸 `ruff check app tests && mypy app` = 不可能绿**
  - **关键洞察**：`mypy 2 source files` 报告"0 errors"是误导——transitive imports 会让 textbook_upload.py 一起被检查；下次应直接 `mypy app/` 拿全仓真值

---

## 3. 处置方案

| 选项 | 何时 | 范围 | 推荐 |
|---|---|---|---|
| (a) **修** | M2-S1 启动前 | 重构 `textbook_upload` Subject schema + `academic` 类型注解 | ✅ |
| (b) **跟踪** | M3 上传+评分 阶段 | mypy strict 模式要求时再修 | (fallback) |
| (c) **忽略** | — | 不推荐（持续累积 + 入场闸永久红） | ❌ |

**默认**：(a) 修；S1 启动 brief `plans/M2-A.1-brief.md` 应包含 mypy 残留修复子任务（per 决策书 §6 启动清单第 4 项）。

---

## 4. 关联

- **决策书**：`docs/M2-kickoff-decision.md §7.2 拍板记录（D-M2-2）` 拍板 = (a) CSV 导入
- **D-49**：narrowing cast 实证类（review2 baseline B1 修正模式）
- **D-44**：mypy strict 模式要求
- **S0-4 链路**：本笔 tech-debt 与 S0-4 TWAIN mock 无关；S0-4 修法 4 files 全 mypy 绿（容器内）

---

## 5. 修复参考

- `textbook_upload.py:264`：Subject 模型加 `owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))` + Alembic 迁移
- `academic.py:259`：调用点补 `owner_user_id=current_user.id`
- `academic.py:293/336/547`：类型注解收紧（`str` → `Literal["detected", "pdfplumber_fallback", ...]`）
- 推荐改法 = 重构 + 类型签名收紧；不要用 `# type: ignore` 掩盖

---

**变更说明**（D-77 元规则）：见 `notes/changelog/tech-debt.md`（变更说明不与文件同体）
