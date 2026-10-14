# Task: M2-#113 根因诊断 + 立独立工单

> **派工 #1 试**（修正规则 #1 第 1 次试；D-43 §5 + corrective-rule-1-dispatch-protocol）
> **工作分支**：master（直接 1 刀 commit；非实施 = 不需 worktree）
> **预期输出**：1 笔 commit + `notes/work-orders/113-9-pre-existing-test-failures.md`（NEW，≥20 行 = 9 失败 × 3-5 行 = 50+ 行）

---

## 派工前 4 验 baseline（父会话已跑，2026-10-14 10:30 +0800）

| # | 项 | 真值 | 状态 |
|---|---|---|---|
| 1 | alembic current | `0011_question_images (head)` | ✓ |
| 2 | pytest -k "p15 or textbook_upload_real_pdf or p0n1 or academic_api or academic_llm or cross_user_isolation"（容器 PG）| `exec failed: pytest: executable file not found in $PATH` | ⚠ **subagent 必探正确 pytest 命令** |
| 3 | user_tables count | 19 | ✓ |
| 4 | enum count | 7 | ✓ |

**3 步 + 1 警告**：3 项绿，pytest 探命令 subagent 接手处理（详 §Step 2）。

---

## 全局硬约束（6 项）

1. **6-line env handshake FIRST**（per subagent-env-handshake）—— 任何写操作前必跑
2. **禁动文件清单**（见下）—— 6 失败 test 文件 + backend/app/ 全部 source + alembic + conftest + meta 文件 = 全部 READ ONLY
3. **4-字段 commit message**（依赖/下游/预检/范围）—— 1 笔 commit 必带
4. **派工前/后 4 验 baseline 必一致** —— subagent 跑前 + 跑后必报回真值，父会话重验
5. **禁 drop dev 库**（per A. 禁 drop dev 库）：
   - pytest 后必 `alembic stamp base && alembic upgrade head` 二步重建（§治理.19 trap）
   - 禁 `alembic downgrade` / `alembic stamp <old>` / `Base.metadata.drop_all()` / 改 conftest teardown
6. **失败立即停手** + 详细诊断报回决策室（不擅自换根因 / 改测试期望 / 跳步骤）

---

## 严格禁止动文件清单

- **测试文件（READ ONLY）**：
  - `backend/tests/test_p15_title_quality.py`（2 失败）
  - `backend/tests/test_textbook_upload_real_pdf.py`（3 失败）
  - `backend/tests/test_p0n1_subject_ownership.py`（1 失败）
  - `backend/tests/test_academic_api.py`（1 失败）
  - `backend/tests/test_academic_llm.py`（1 失败）
  - `backend/tests/test_cross_user_isolation.py`（1 失败）
- **后端 source（READ ONLY）**：
  - `backend/app/**/*.py`（全部 source）
  - `backend/alembic/versions/*.py`（migration 链不动）
  - `backend/conftest.py` / `backend/tests/conftest.py`（含 drop_all trap = 不许动）
  - `backend/pytest.ini` / `backend/pyproject.toml`（pytest 配置不动）
- **元数据 / 治理文件（不动）**：
  - `STATE.md` / `memory/YYYY-MM-DD.md` / `notes/milestones.md` / `docs/decisions.md`
  - `AGENTS.md` / `WAKEUP.md` / `docs/PROJECT-CHARTER*.md` / `README.md` / `.env.example`
  - `Dockerfile` / `docker-compose.yml` / `.github/workflows/ci.yml`
- **可写文件（仅 1 项）**：
  - `notes/work-orders/113-9-pre-existing-test-failures.md`（NEW，本任务唯一产出）

---

## 工作环境

- **项目根**：`/home/wsq_1/tiered-homework-platform`
- **HEAD**：`c0be4ad`（复位前 2026-10-13 15:51 commit；c0be4ad1a94788d5b68d00657df5d6530f5e6b1e）
- **远程**：origin (Gitee) + github（双 remote 同步 = 0/0 ahead）
- **工作树**：clean（`git status --porcelain` 应 = 空）
- **容器 PG**：`docker compose exec -T backend <cmd>`（per memory/2026-10-13 §一）
- **分支策略**：在 master 上 1 刀 commit（**不 push** = 无 `[origin-push]` 标记；meta 工单 = 用户拍后另推）
- **历史坑**：
  - §治理.19 字面绿口头红 trap（pytest 跑完 dev 库被 drop_all 清空）
  - §治理.20 docker volume 不挂 `backend/tests/`（如需 `docker cp` 同步 = 仿 S3-frontend 模式）
  - pytest 路径不在默认 PATH（必探正确命令）

---

## Step 1: 6-line env handshake（FIRST action, before any write）

```bash
cd /home/wsq_1/tiered-homework-platform

echo "[H1] pwd: $(pwd)"
echo "[H2] toplevel: $(git rev-parse --show-toplevel)"
echo "[H3] git-dir: $(git rev-parse --absolute-git-dir)"
echo "[H4] HEAD: $(git rev-parse HEAD)"
echo "[H5] log -3:"
git log --oneline -3
echo "[H6] remote:"
git remote -v
echo "[H7] status:"
git status --porcelain
```

**父会话期望真值**（subagent 必逐项 cross-check，不符 = STOP）：

| 项 | 期望 |
|---|---|
| pwd / toplevel | `/home/wsq_1/tiered-homework-platform` |
| git-dir | `/home/wsq_1/tiered-homework-platform/.git` |
| HEAD | `c0be4ad1a94788d5b68d00657df5d6530f5e6b1e` |
| log -3 顶 | `c0be4ad chore(复位前 2026-10-13 15:51 ...` |
| remote | 2 行（origin + github）|
| status | 空 |

**Trap 签名**（≥2 of 3 命中 = STOP + 报回）：
- A: only 1 commit reachable
- B: 0 remotes
- C: HEAD message 陌生（不含 "tiered-homework" / "差异化作业" / "fixtures" / "复位前" 等项目词）

---

## Step 2: 探 pytest 正确命令（容器 PG）

父会话 baseline 跑 `docker compose exec -T backend pytest ...` 失败 (`pytest: not found in PATH`)。Subagent 必探出正确命令。

**优先级尝试**（按可能性排序）：

```bash
# 1. python -m pytest (最可能)
docker compose exec -T backend python -m pytest --version

# 2. 看 Dockerfile 找 pytest binary
docker compose exec -T backend bash -c "which pytest || find / -name 'pytest' -type f 2>/dev/null | head -5"

# 3. 看 entrypoint / cmd
cat docker-compose.yml | grep -A5 -E "(backend|app|command|entrypoint)"

# 4. 看 backend Dockerfile
cat backend/Dockerfile | grep -E "(pytest|PATH|VIRTUAL_ENV|poetry|pip)"
```

**最终 pytest 命令格式（找到后报回父会话）**：

```bash
# 例如（subagent 探到后用真实命令）:
docker compose exec -T backend python -m pytest -k "p15 or textbook_upload_real_pdf or p0n1 or academic_api or academic_llm or cross_user_isolation" --tb=short 2>&1 | tee /tmp/pytest_113.log
```

**报回必带**：
- 探到的 pytest 真实命令
- pytest 输出**完整 traceback**（不只 tail）
- 9 失败的 `FAILED <file>::<func> - <reason>` 列表

---

## Step 3: 派工前 4 验 baseline（subagent 重跑，**Step 2 pytest 成功后**）

```bash
# [1/4] alembic current
docker compose exec -T backend alembic current

# [2/4] pytest 9 失败 -q（用 Step 2 探到的命令）
docker compose exec -T backend python -m pytest -q --tb=no -k "p15 or textbook_upload_real_pdf or p0n1 or academic_api or academic_llm or cross_user_isolation"

# [3/4] user_tables
docker compose exec -T backend python -c "from sqlalchemy import create_engine, text; import os; eng = create_engine(os.environ['DATABASE_URL']); print(list(eng.connect().execute(text(\"SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name != 'alembic_version'\"))))"

# [4/4] enums
docker compose exec -T backend python -c "from sqlalchemy import create_engine, text; import os; eng = create_engine(os.environ['DATABASE_URL']); print(list(eng.connect().execute(text(\"SELECT count(*) FROM pg_type WHERE typtype='e'\"))))"
```

**报回必带**（父会话对照派工前 baseline）：

| # | 期望 |
|---|---|
| alembic current | `0011_question_images (head)` |
| pytest | 9 failed（同名同位置）|
| user_tables | 19 |
| enums | 7 |

**任何一项 ≠ 期望 = silent failure 模式 = 立即停手 + 报回**。

---

## Step 4: 读 source code + 分类 9 根因

**对每个失败**（按 9 失败顺序）：

1. **读测试函数**：`cat backend/tests/<file>:<line_range>`（失败 func + setup + assertion）
2. **读被测 source**：`cat backend/app/<source_file>:<line_range>`（被测函数 + 关键依赖）
3. **读 fixture**（如失败在 fixture 层）：`cat backend/tests/<fixture>:<line_range>`
4. **分类根因**（5 类）：
   - **A. 数据 fixture 问题**（fixture 缺数据 / 路径错 / 字段不匹配）
   - **B. source code bug**（assertion 真错 / exception 路径 / 边界条件）
   - **C. mock / patch 失配**（mock target 错 / 路径漂移 / LLM provider mock stale）
   - **D. migration / schema 漂移**（期望字段不在 / 类型变 / 索引丢）
   - **E. 环境依赖**（真实 PDF 缺 / 外部 API 不可达 / 时间窗口 / 随机种子）

**报回必带 9 个失败每个**：
- 失败位置（file:line:func）
- pytest trace 关键行号
- 根因分类（A/B/C/D/E）
- 严重程度（blocker for M3 / minor / cosmetic）
- 修法方向（1-2 句，**不实施**）

---

## Step 5: 写工单 `notes/work-orders/113-9-pre-existing-test-failures.md`

**先创建目录**（不存在）：

```bash
mkdir -p notes/work-orders
```

**工单格式模板**（subagent 必填齐 9 个失败 + 总览）：

```markdown
# #113 — 9 pre-existing 失败用例根因诊断工单

> **状态**: 根因诊断完成 / 修复待 #114 拍
> **创建**: 2026-10-14
> **触发**: memory/2026-10-13 §五（9 pre-existing 失败用例）
> **诊断真值**: <commit SHA> / <pytest output 引用 /tmp/pytest_113.log>
> **不立 D-XX**（per D-83 不立原则；元规则通胀防御）

## 总体盘

| 分类 | 数量 | 严重 blocker | 备注 |
|---|---|---|---|
| A. 数据 fixture 问题 | N | | |
| B. source code bug | N | | |
| C. mock / patch 失配 | N | | |
| D. migration / schema 漂移 | N | | |
| E. 环境依赖 | N | | |
| **合计** | **9** | **N** | |

## 失败 1: <test_file>::<func_name>
- **位置**: `backend/tests/<file>:<line>` (func `test_xxx`)
- **失败模式**: <assertion / exception / fixture setup error + 1 行 trace>
- **pytest trace 关键行**: <file:line: code>
- **根因分类**: A / B / C / D / E
- **严重程度**: blocker for M3 / minor / cosmetic
- **修法方向**: <1-2 句>
- **修复预估**: <trivial / small / medium / large>

## 失败 2: ...
...

## 失败 9: ...

## 修复优先级建议

1. **P0 (blocker for M3)**: ...
2. **P1 (后置)**: ...
3. **P2 (cosmetic)**: ...

## 关联引用

- memory/2026-10-13 §五（9 pre-existing 失败用例立 #113）
- memory/2026-10-13 §六 ledger_check 11/11 PASS（修复后必重跑）
- §治理.16/19/20（drop_all trap + 派工前/后 4 验 baseline）
- §治理.5（commit message 强制 4 字段）
- D-43 §5（决策室不修代码逻辑 → 修复时 subagent 派工）
- D-83 不立原则（本工单 = 修复入口；不立新 D-XX）

> **【2026-10-14 变更说明 · notes/work-orders/113-9-pre-existing-test-failures.md】**
> （commit 时补 changelog footer）
```

**报回必带**：
- 工单文件路径
- 工单总行数
- 9 失败根因分类表（5 类计数）
- P0/P1/P2 优先级
```

---

## Step 6: 派工后 4 验 baseline（subagent 必跑；§Step 3 期望对齐）

**pytest 必触发 drop_all（如 §治理.19 trap）= 派工后 baseline 必重建**：

```bash
# pytest 后必 alembic stamp base + upgrade head 重建（破坏性 alias 链切断）
docker compose exec -T backend alembic stamp base
docker compose exec -T backend alembic upgrade head

# [1/4] alembic current
docker compose exec -T backend alembic current
# [2/4] pytest -q 9 失败（验证 9 失败真值未变 = 修复前/后一致）
docker compose exec -T backend python -m pytest -q --tb=no -k "p15 or textbook_upload_real_pdf or p0n1 or academic_api or academic_llm or cross_user_isolation"
# [3/4] user_tables
docker compose exec -T backend python -c "from sqlalchemy import create_engine, text; import os; eng = create_engine(os.environ['DATABASE_URL']); print(list(eng.connect().execute(text(\"SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name != 'alembic_version'\"))))"
# [4/4] enums
docker compose exec -T backend python -c "from sqlalchemy import create_engine, text; import os; eng = create_engine(os.environ['DATABASE_URL']); print(list(eng.connect().execute(text(\"SELECT count(*) FROM pg_type WHERE typtype='e'\"))))"
```

**派工后 期望 = 派工前 baseline**（必逐项对齐）：

| # | 派工前 | 派工后 |
|---|---|---|
| alembic | 0011 (head) | 0011 (head) |
| pytest 9 失败 | 9 failed | 9 failed（同名同位置）|
| user_tables | 19 | 19 |
| enums | 7 | 7 |

**任何一项 ≠ = silent failure = 立即停手 + 报回决策室**。

---

## Step 7: 1 刀 commit（4 字段, no [origin-push]）

```bash
git add notes/work-orders/113-9-pre-existing-test-failures.md
git status --porcelain  # 必只含本文件 = 范围核源
git diff --stat HEAD  # 必 = "notes/work-orders/113-9-pre-existing-test-failures.md | N ++++"

git commit -m "chore(诊断 #113): 9 pre-existing 失败用例根因诊断 + 立独立工单

依赖: pytest trace (容器 PG) + 6 测试文件 source code 读懂
下游: 工单 = 修复 #113 的实施入口 (修复时直接对照本工单 9 失败根因)
预检: 仅读 pytest output + 写 1 markdown 文件, 不改 source/test/migration/conftest
范围: notes/work-orders/113-9-pre-existing-test-failures.md (NEW, N 行)"
```

**commit message 必含 4 字段**（依赖/下游/预检/范围）—— 父会话核源时 `git log -1 --format=%B | grep` 验。

**无 [origin-push]** = meta 工单，用户审过另推。

---

## 完成定义

1 刀 commit + 报回 4-source 核源 = subagent 完成。

**任何 1 步失败 / 4 验 baseline 不一致 / pytest 探命令失败 = 立即停手 + 详细诊断报回决策室**。

---

## 报回格式（必带，4-source 核源 + 9 失败根因表）

```markdown
## Step 1 完成
- pwd / toplevel: <真值>
- HEAD: <SHA>
- 6 项 cross-check: 全部 ✓ / <不符项>
- 状态: ✅ / ⚠️ / ❌

## Step 2 完成
- 探到的 pytest 命令: <真命令>
- 探测过程: <4 优先级尝试哪些命中>
- 状态: ✅ / ⚠️ / ❌

## Step 3 完成（派工前 4 验 baseline）
- alembic: 0011 ✓
- pytest 9 失败: <9 个 FAILED 行>
- user_tables: 19
- enums: 7
- 状态: ✅ / ⚠️ / ❌

## Step 4 完成（9 失败根因诊断）
- 9 失败根因分类: A=N, B=N, C=N, D=N, E=N (合计 9)
- 严重 blocker 数: N
- 详细: 见工单 notes/work-orders/113-9-pre-existing-test-failures.md
- 状态: ✅ / ⚠️ / ❌

## Step 5 完成（工单文件）
- 路径: notes/work-orders/113-9-pre-existing-test-failures.md
- 总行数: N
- 9 失败齐全: ✓
- 优先级: P0=N, P1=N, P2=N
- 状态: ✅ / ⚠️ / ❌

## Step 6 完成（派工后 4 验 baseline）
- alembic stamp base + upgrade head: ✓
- 派工后 4 验 vs 派工前: 全部一致 ✓
- 状态: ✅ / ⚠️ / ❌

## Step 7 完成（commit）
- commit SHA: <hash>
- message: <完整 message>
- 4 字段齐: 依赖 ✓ / 下游 ✓ / 预检 ✓ / 范围 ✓
- 范围: git diff --stat HEAD~1..HEAD = <only this 1 file>
- 状态: ✅ / ⚠️ / ❌

## 4-source 核源（父会话用）
- Source 1 (commit count): 1 (668fddd..HEAD 应 + 1)
- Source 2 (范围): git diff --stat HEAD~1..HEAD = 仅 1 file
- Source 3 (4 字段): 全部齐
- Source 4 (push): 未推 (no [origin-push]) ✓
```

---

## 严禁

- 跳过任何 Step（6-line handshake 不可省）
- 改禁动文件清单任何一项（含 conftest / 测试期望 / source / migration / meta 文件）
- 跑 `alembic downgrade` / `alembic stamp <old>` / `Base.metadata.drop_all()` / 改 conftest teardown（drop_all trap）
- pytest 后不重建 dev 库（必 `alembic stamp base && alembic upgrade head`）
- 改测试期望当修根因（D-43-X #14: 把 assert 200 改 assert 404 当修 bug）
- 擅自换根因 / 改派工 brief 范围
- push 到远端（meta 工单 = 不推）
- 合并 9 失败诊断为 1 段（必分 9 段详写）
- 漏报 pytest trace 关键行号
- "已 ruff/mypy 通过" ≠ "代码能工作" —— **本任务不需 ruff/mypy**（仅写 markdown）；但**pytest trace 必带**

---

## 决策室权限

- 任何时候中止你的任务（CHARTER §7.0 决策室权限高于工地）
- 失败停手 ≠ 失败 = 详细诊断报回 = 决策室重派 / 修 brief / take over
- 4 验 baseline 任何一项不符 = silent failure 模式 = 立即停手 + 报回

---

## 关联引用

- **触发源**：memory/2026-10-13 §五（9 pre-existing 失败用例立 #113）
- **派工协议**：D-43 §5 + corrective-rule-1-dispatch-protocol（4-step）
- **Brief 纪律**：subagent-brief-discipline-constraints
- **握手协议**：subagent-env-handshake（6-line + trap 签名）
- **drop_all trap**：§治理.16/19/20（pytest 后必重建）
- **不立原则**：D-83（本工单 = 修复入口，不立新 D-XX）
- **D-43-X 协作纪律**：结论性陈述必须自我验证（subagent 报回 ≠ 父会话信）
- **修正规则 #1**：4-step 派工协议（1 试 → 核源 → 1 重试 → take over + 落字）
