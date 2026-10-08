# Tech Debt — mypy pre-existing errors（M2 启动期清查）

> **最后更新**：2026-10-08 21:55（§十九 配套；N2 判决 + bulk sync 后 HEAD 真值 = 0 errors；审计员预测 ≈0 验证）
> **维护规则**：每次 ruff / mypy 跑前必先 grep `tech-debt` 是否过期；过期未登记 = 失实
> **关联元规则**：D-43 §5（决策室不修代码逻辑） / D-49（narrowing cast 实证类） / D-44（mypy strict 模式要求）

---

## 1. 当前状态

**0 pre-existing mypy errors** as of 2026-10-08 21:55（`git rev-parse HEAD` = `<待 commit>` 验证）

**实证**（@取数时刻 2026-10-08 21:55；bulk sync 后）：

```bash
$ docker exec thp-backend bash -c "cd /app && python3 -m mypy app/ 2>&1" | tail -2
Success: no issues found in 31 source files

$ docker exec thp-backend bash -c "cd /app && python3 -m mypy app/ 2>&1" | grep -E ':[0-9]+: error:' | wc -l
0
```

**check 10 v3 双向核对**（多文件树哈希 + tech-debt.md ↔ mypy 真值）：
- 树哈希：容器 backend/app/  ==  HEAD backend/app/ ✓
- doc 引用：0 个 == mypy 真值：0 个 ✓

---

## 2. 历史（已修）

### 2.1 2026-10-08 17:30-21:30 期间曾登记的 11 errors（**全部为镜像陈旧假阳**）

按根因分 5 类（11 errors）—— **均已确认为陈旧镜像 docker cp 漏文件导致的假阳**（N2 判决）：

| # | 文件:行 | 错数 | 根因 | 真值（HEAD 验证） |
|---|---|---|---|---|
| 1 | `backend/app/services/textbook_upload.py:264` | 1 | Subject 缺 `owner_user_id` | **假阳**：HEAD 真值在 `models/academic.py:156` 有 `owner_user_id: Mapped[int] = mapped_column(...)` |
| 2 | `backend/app/api/v1/routers/academic.py:37` | 6 | `schemas.academic` 缺 6 个 Question* 定义 | **假阳**：HEAD 真值在 `schemas/academic.py:380/389/433/442/458/475` 都有 |
| 3 | `backend/app/api/v1/routers/academic.py:66` | 2 | `app.models` 缺 Choice + Question | **假阳**：HEAD 真值在 `models/__init__.py:12/21` 都 re-export |
| 4 | `backend/app/api/v1/routers/academic.py:81` | 1 | `app.models` 缺 QuestionDifficulty | **假阳**：HEAD 真值在 `models/__init__.py:22/40` re-export |
| 5 | `backend/app/api/v1/routers/academic.py:84` | 1 | `app.models` 缺 QuestionType | **假阳**：HEAD 真值在 `models/__init__.py:23/41` re-export |

**N1 → N2 → bulk sync → HEAD 真值 = 0 errors**（详见 §十八 + §十九）

### 2.2 陈旧镜像那批 extraction_source errors

`academic.py:293/336/547` 的 `extraction_source str vs Literal` errors —— **HEAD 已用 `cast(Literal[...])` 修掉**（:343/:388/:603 实测都有 cast；N1 判决前的容器是 09-21 旧版，未含 cast 修复）

---

## 3. 关联

- **N1 判决**（§十八）：tech-debt.md 行号与 HEAD 差 ≈50 行 ⇒ 镜像陈旧
- **N2 判决**（§十九）：11 errors 全部为镜像陈旧假阳；HEAD 真值 = 0 errors
- **check 10 v3**（§十九）：多文件树哈希 + 双向核对（防单文件 cp 漏文件）

---

## 4. 状态历史

| 日期 | HEAD mypy 真值 | 触发原因 |
|---|---|---|
| 2026-10-07 收工 | 5 pre-existing | 镜像陈旧（M0/M1 残留）|
| 2026-10-08 17:30 (§十七) | 5 pre-existing | 同上；技术债登记 |
| 2026-10-08 21:30 (§十八) | 11 pre-existing | N1 判决后容器 sync 2 文件；HEAD 仍含未 cp 文件的 stale import |
| 2026-10-08 21:55 (§十九) | **0 pre-existing** | N2 判决后 bulk sync backend/app/ → /app/app/；HEAD 真值验证 |

---

**变更说明**（D-77 元规则）：见 `notes/changelog/tech-debt.md`（变更说明不与文件同体）
