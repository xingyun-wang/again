# Tech Debt — mypy pre-existing errors（M2 启动期清查）

> **最后更新**：2026-10-08 22:00（§十九 配套；N2 判决后 HEAD 真值 = 0 errors）
> **维护规则**：每次 ruff / mypy 跑前必先 grep `tech-debt` 是否过期；过期未登记 = 失实
> **关联元规则**：D-43 §5（决策室不修代码逻辑） / D-49（narrowing cast 实证类） / D-44（mypy strict 模式要求）

---

## 1. 当前状态

**0 pre-existing mypy errors** as of 2026-10-08 22:00（`git rev-parse HEAD` 验证）

**实证**（@取数时刻 2026-10-08 22:00；bulk sync 后）：

```bash
$ docker exec thp-backend bash -c "cd /app && python3 -m mypy app/ 2>&1" | tail -2
Success: no issues found in 31 source files

$ docker exec thp-backend bash -c "cd /app && python3 -m mypy app/ 2>&1" | grep -E ':[0-9]+: error:' | wc -l
0
```

**check 10 v3.2 双向核对**：tree hash match + doc 引用 0 == mypy 真值 0 ✓

---

## 2. 历史 audit trail（已修；详见 commit log）

| 日期 | HEAD mypy 真值 | 触发原因 | 关联 commit |
|---|---|---|---|
| 2026-10-07 收工 | 5 pre-existing | 镜像陈旧（M0/M1 残留）| (历史 commit) |
| 2026-10-08 17:30 (§十七) | 5 pre-existing | 同上；技术债登记 | `90c72f1` |
| 2026-10-08 21:30 (§十八) | 11 pre-existing (假阳) | N1 判决后容器 sync 2 文件；HEAD 仍含未 cp 文件的 stale import | `b8369e9` |
| 2026-10-08 22:00 (§十九) | **0 pre-existing** | N2 判决后 bulk sync backend/app/ → /app/app/；HEAD 真值验证 | `a8388b9` + `12b4ed2` |

### 2.1 11 errors 假阳溯源

- 全部为镜像陈旧 docker cp 漏文件导致（schemas/academic.py + models/__init__.py + models/academic.py 未 cp）
- HEAD 实际**全部存在** = 假阳：
  - Subject `owner_user_id` ✓（见 models/academic.py 中 Subject 定义）
  - schemas.academic 6 个 Question* ✓（见 schemas/academic.py 中 Question* 类）
  - app.models Choice / Question / QuestionDifficulty / QuestionType ✓（见 models/__init__.py re-export）
- 详见外部审计员反馈 2026-10-08 21:34（user pasted external content）+ commit `a8388b9` commit message

---

## 3. 关联

- **N1 判决**（§十八）：tech-debt.md 行号与 HEAD 差 ≈50 行 ⇒ 镜像陈旧
- **N2 判决**（§十九）：11 errors 全部为镜像陈旧假阳；HEAD 真值 = 0 errors
- **check 10 v3.2**（§十九）：多文件树哈希（md5s-only path-strip）+ 双向核对（防单文件 cp 漏文件 = N1/N2 类错根除）

---

**变更说明**（D-77 元规则）：见 `notes/changelog/tech-debt.md`（变更说明不与文件同体）
