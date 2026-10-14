# Task: M2-#114 P1 修复 + B2 修法 + 必跑全套 pytest 收口

> **派工 #1 试**（修正规则 #1 第 1 次试；D-43 §5 + corrective-rule-1-dispatch-protocol）
> **工作分支**：master（直接实施；非实施 = 不需 worktree）
> **预期输出**：1-2 笔 commit（B2 修法 + P1 修复；brief commit 已先落字 = `c8ca4f9+1`）
> **触发**：memory/2026-10-14 决策室拍 (b) + work order `notes/work-orders/113-9-pre-existing-test-failures.md` §决策室拍 + §P0 实施留痕 §修复后验证清单

---

## 上下文（必读）

**承接 #113 派工 #1 试**（commit `110cd46`）+ 父会话 take over P0（commit `c8ca4f9`）：
- **P0 已完成**：host chown 让容器 appuser 可写 bind mount（修法 8/9 失败 E 类根因）
- **P1 待修**：1/9 失败 B 类根因（test_real_llm_review_flow X-User-Id: 2 期望 200 返 404）
- **B2 修法**：§治理.19 升级为结构性防 — 容器 pytest 必用 test 库（`DATABASE_URL=...tiered_homework_test`），不碰 dev 库
- **复验提醒**：本次 #113 pytest -k 只证子集（54 selected / 273 deselected）⇒ #114 收口**必跑全套** `python -m pytest -q`

**必读 work order**：
- `notes/work-orders/113-9-pre-existing-test-failures.md`（commit `c8ca4f9`）
  - §决策室拍 — P1 拍 (b) 详 + #114 必带 3 项
  - §P0 实施留痕 — 复验 3 步 + 8/9 绿 推论 + dev 库脆弱状态
  - §修复后验证清单 — B2 修法具体化 + 必跑全套

---

## 任务总览

| 项 | 内容 | 必改/必跑 |
|---|---|---|
| **B2 修法** | 创建 `tiered_homework_test` 库 + 容器 pytest 显式 `-e DATABASE_URL=...test` | docker-compose.yml 或 conftest.py 或 init script |
| **P1 (b) test 修** | `backend/tests/test_academic_llm.py:227` `X-User-Id: 2` → `1` | 1 行 |
| **P1 source 注释订正** | `backend/app/api/v1/routers/academic.py:912` 注释「（双重门）」→「（单门 JOIN chapter）」| 1 行 |
| **必跑全套 pytest 收口** | `python -m pytest -q` 全套 → 期望 0 failed | 不留 -k 子集尾巴 |

**B2 修法先做**（test 库就绪后，P1 修改才能在 test 库验证，避免再次踩 §治理.19 trap）

---

## 派工前 4 验 baseline（父会话已跑，2026-10-14 11:37 +0800）

**dev 库（脆弱状态，per §P0 实施留痕）**：
- alembic: stamped=base（version=NULL；upgrade head 撞 enum 已存在；不展开修 = #114 B2 修法后不碰 dev）
- user_tables: 19
- enums: 7
- ⚠️ **dev 库不参与 #114 pytest**（per B2 修法）

**test 库（待创建）**：
- 状态：不存在（postgres 服务未创过 test 库）
- 期望 baseline: alembic 0011 / 19 / 7（与 dev 一致）

**Subagent Step 1 必跑**（test 库现状 + ci.yml:53 先例摸底）

---

## 全局硬约束（6 项）

1. **6-line env handshake FIRST**（per subagent-env-handshake）—— 任何写操作前必跑
2. **禁动文件清单**（见下）—— 6 失败 test 文件 + backend/app/ 全部 source + alembic + meta 文件 = 全部 READ ONLY（**#114 例外修改** = `test_academic_llm.py:227` + `academic.py:912` 注释）
3. **4-字段 commit message**（依赖/下游/预检/范围）—— 1-2 笔 commit 必带
4. **派工前/后 4 验 baseline 必一致**（test 库 alembic 0011 / 19/7 + pytest 全套 0 failed）—— subagent 跑前 + 跑后必报回真值，父会话重验
5. **B2 修法结构性防**（per A2 + B2 + 复验提醒）：test 库 pytest 不碰 dev 库；任何 pytest 命令必 `-e DATABASE_URL=...tiered_homework_test`
6. **失败立即停手** + 详细诊断报回决策室

---

## 严格禁止动文件清单

- **测试文件（READ ONLY 除 #114 必改）**：
  - `backend/tests/test_academic_llm.py:227` 必改（`X-User-Id: 2` → `1`；per 决策室拍 (b)）
  - 其他 5 失败 test 文件（test_p15_title_quality / test_textbook_upload_real_pdf / test_p0n1_subject_ownership / test_academic_api / test_cross_user_isolation）= READ ONLY
- **后端 source（READ ONLY 除 #114 必改）**：
  - `backend/app/api/v1/routers/academic.py:912` 必改（注释「（双重门）」→「（单门 JOIN chapter）」）
  - `backend/app/**/*.py` 其他 = READ ONLY
  - `backend/alembic/versions/*.py` = READ ONLY
  - `backend/conftest.py` / `backend/tests/conftest.py` = 禁动（除非 B2 修法必带；详 §Step 2）
  - `backend/pytest.ini` / `backend/pyproject.toml` = 禁动（除非 B2 修法必带）
- **元数据 / 治理文件（不动）**：
  - `STATE.md` / `memory/2026-10-14.md` / `notes/milestones.md` / `docs/decisions.md`
  - `AGENTS.md` / `WAKEUP.md` / `docs/PROJECT-CHARTER*.md` / `README.md` / `.env.example`
  - `Dockerfile`（禁动；除非 B2 修法必带）
  - `.github/workflows/ci.yml`（**READ ONLY**——但**必读 ci.yml:53** 找 test 库 setup 先例）
  - `docker-compose.yml` = **禁动**（除非 B2 修法必带；如有改动 = **必带 [origin-push] 标记 + 父会话重验**）
- **可写文件（#114 必改）**：
  - `backend/tests/test_academic_llm.py:227`（1 行）
  - `backend/app/api/v1/routers/academic.py:912`（1 行注释）
  - B2 修法新增文件（如 init script / test 库 setup 脚本）= 必带 [origin-push] 标记

---

## 工作环境

- **项目根**：`/home/wsq_1/tiered-homework-platform`
- **HEAD**：`c8ca4f9`（v3 收口 commit；上一笔 = `4eec216` brief commit = `110cd46` work order commit = `8c08373` / `7b8bbd1` / `d8f6d18` 收工 = `c0be4ad` 复位前 = `668fddd` 起点；A5 (a) 口径 = 截至上一笔 = 35 笔，master = 本笔 36 笔）
- **远程**：origin (Gitee) + github（0/0 同步 = c8ca4f9 双 push）
- **工作树**：clean（`git status --porcelain` 应 = 空）
- **容器 PG**：`docker compose exec -T backend <cmd>`
- **dev 库**：stamped=base / 19/7（脆弱；B2 修法后不碰）
- **test 库**：待创建（`tiered_homework_test`）
- **分支策略**：在 master 上 1-2 笔 commit；B2 修法 + P1 (b) 修复 可合 1 笔 或 分 2 笔（subagent 自决）
- **历史坑**：
  - §治理.19 字面绿口头红 trap（dev 库 pytest 必 drop_all）
  - B2 修法 = 结构性防 = 必带
  - ci.yml:53 = test 库 setup 先例（**必读**）

---

## Step 1: 6-line env handshake + 探 B2 修法先例（FIRST action, before any write）

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

**父会话期望真值**：

| 项 | 期望 |
|---|---|
| pwd / toplevel | `/home/wsq_1/tiered-homework-platform` |
| git-dir | `/home/wsq_1/tiered-homework-platform/.git` |
| HEAD | `c8ca4f9...` (or any newer) |
| log -3 顶 | `c8ca4f9 chore(诊断 #113 收口 v3): ...` |
| remote | 2 行（origin + github）|
| status | 空 |

**Trap 签名**（≥2 of 3 命中 = STOP + 报回）：
- A: only 1 commit reachable
- B: 0 remotes
- C: HEAD message 陌生（不含 "tiered-homework" / "差异化作业" / "诊断 #113" / "fixtures" / "复位前" 等项目词）

**B2 修法先例探**（必跑）：
```bash
echo "=== ci.yml:53 先例 (test 库 setup pattern) ===" && \
sed -n '45,65p' .github/workflows/ci.yml && \
echo "" && \
echo "=== 当前 dev 库 alembic state ===" && \
docker compose exec -T backend alembic current 2>&1 | tail -3 && \
echo "" && \
echo "=== 当前 postgres 服务 是否能 CREATE DATABASE ===" && \
docker compose exec -T db psql -U postgres -c "SELECT datname FROM pg_database WHERE datname='tiered_homework_test';" 2>&1 | tail -3 && \
echo "" && \
echo "=== docker-compose.yml test-db service 现状 (如无 = B2 修法需新建) ===" && \
grep -A3 "test\|tiered_homework_test" docker-compose.yml | head -20
```

**报回必带**：
- 6-line handshake 真值
- ci.yml:53 test 库 setup 模式
- 当前 dev 库 alembic state
- postgres 服务能否 CREATE DATABASE
- docker-compose.yml 是否有 test-db service

---

## Step 2: B2 修法实施（test 库创建 + pytest 必带 -e DATABASE_URL=...test）

**B2 修法 目标**：
1. 创建 `tiered_homework_test` 数据库（独立于 dev 库）
2. 在 test 库跑 `alembic upgrade head` 到 0011
3. 容器 pytest 必带 `-e DATABASE_URL=postgresql://postgres:postgres@db/tiered_homework_test`
4. **dev 库绝不参与 pytest**

**B2 修法 实施选项**（subagent 自决，仿 ci.yml:53 先例）：

**选项 A — conftest.py fixture 动态创建 + DATABASE_URL override**（最轻）：
```python
# backend/conftest.py 新增 (在现有 conftest 基础上追加，不覆盖)
@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """B2 修法：创建 test 库 + 跑 alembic + 设 DATABASE_URL 环境变量"""
    import os
    import subprocess
    test_db_url = "postgresql://postgres:postgres@db/tiered_homework_test"
    os.environ["DATABASE_URL"] = test_db_url
    # CREATE DATABASE if not exists
    subprocess.run(["psql", "-U", "postgres", "-h", "db", "-c",
                    f"CREATE DATABASE tiered_homework_test"], check=False, capture_output=True)
    # alembic upgrade head
    subprocess.run(["alembic", "upgrade", "head"], check=True, env={**os.environ, "DATABASE_URL": test_db_url})
    yield
    # teardown: DROP DATABASE? (可选；保留 = 下次 pytest 复用)
```

**选项 B — docker-compose override file + test service**（最稳）：
```yaml
# docker-compose.test.yml (新增)
services:
  backend:
    environment:
      DATABASE_URL: postgresql://postgres:postgres@db/tiered_homework_test
  db:
    volumes:
      - ./scripts/init-test-db.sql:/docker-entrypoint-initdb.d/init-test-db.sql
```

```sql
-- scripts/init-test-db.sql (新增)
CREATE DATABASE tiered_homework_test;
```

**选项 C — 复用现有 dev 库 + 临时 schema 隔离**（最简，但与 B2 "test 库" 精神冲突；**不推荐**）

**报回必带**：
- 选 A/B/C 哪个
- 新增/修改文件清单
- B2 修法命令清单（如 `docker compose exec db psql -c "CREATE DATABASE tiered_homework_test"` 等）
- dev 库 0 接触证明

---

## Step 3: 派工前 4 验 baseline（test 库；B2 修法后必跑）

**test 库（新建）4 验**：
```bash
echo "=== test 库 4 验 baseline (B2 修法后) ===" && \
echo "[1/4] alembic (test 库):" && \
docker compose exec -T -e DATABASE_URL=postgresql://postgres:postgres@db/tiered_homework_test backend alembic current 2>&1 | tail -1 && \
echo "[2/4] pytest 全套 (test 库):" && \
docker compose exec -T -e DATABASE_URL=postgresql://postgres:postgres@db/tiered_homework_test backend python -m pytest -q --tb=no 2>&1 | tail -3 && \
echo "[3/4] user_tables (test 库):" && \
docker compose exec -T -e DATABASE_URL=postgresql://postgres:postgres@db/tiered_homework_test backend python -c "from sqlalchemy import create_engine, text; eng = create_engine(os.environ['DATABASE_URL']); print(list(eng.connect().execute(text(\"SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name != 'alembic_version'\"))))" 2>&1 | tail -1 && \
echo "[4/4] enums (test 库):" && \
docker compose exec -T -e DATABASE_URL=postgresql://postgres:postgres@db/tiered_homework_test backend python -c "from sqlalchemy import create_engine, text; eng = create_engine(os.environ['DATABASE_URL']); print(list(eng.connect().execute(text(\"SELECT count(*) FROM pg_type WHERE typtype='e'\"))))" 2>&1 | tail -1
```

**期望**：
- alembic: `0011_question_images (head)` ✓
- pytest: `N failed`（N = 0 期望；如 N > 0 = 实施前已存在 fail，**报回决策室**）
- user_tables: 19
- enums: 7

**dev 库 4 验**（仅验真，不参与 pytest；确认未被污染）：
```bash
echo "=== dev 库 4 验 baseline (仅验真, 0 接触证明) ===" && \
echo "dev user_tables: $(docker compose exec -T backend python -c "from sqlalchemy import create_engine, text; import os; eng = create_engine(os.environ['DATABASE_URL']); print(list(eng.connect().execute(text(\"SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name != 'alembic_version'\"))))" 2>&1 | tail -1)" && \
echo "dev enums: $(docker compose exec -T backend python -c "from sqlalchemy import create_engine, text; import os; eng = create_engine(os.environ['DATABASE_URL']); print(list(eng.connect().execute(text(\"SELECT count(*) FROM pg_type WHERE typtype='e'\"))))" 2>&1 | tail -1)"
```

---

## Step 4: P1 (b) 实施（test 修 + source 注释订正；2 行）

**P1 (b) test 修**：
```bash
# 必带 pytest trace (详 §失败 2)
sed -i 's/"X-User-Id": "2"/"X-User-Id": "1"/' backend/tests/test_academic_llm.py
# 验证
grep -n 'X-User-Id' backend/tests/test_academic_llm.py | head -3
```

**P1 source 注释订正**：
```bash
# 必带 A2 理由 (详 §失败 2 修法方向)
sed -i 's/（双重门）/（单门 JOIN chapter — per A2 订正, source academic.py:815-819 明写 LessonPlan 无 owner_user_id 字段, 归属 = JOIN chapter 单门; D-29 反 ID 泄漏门保留）/g' backend/app/api/v1/routers/academic.py
# 验证
grep -n '（单门 JOIN chapter\|（双重门）' backend/app/api/v1/routers/academic.py | head -3
```

**报回必带**：
- 2 处改动前/后 diff（git diff HEAD）
- pytest trace 显示 test 期望 X-User-Id 已变
- source 注释已订正

---

## Step 5: 必跑全套 pytest 收口（per 复验提醒）

**全套 pytest**（不 -k，不留子集尾巴）：
```bash
echo "=== #114 收口: 全套 pytest (test 库) ===" && \
docker compose exec -T -e DATABASE_URL=postgresql://postgres:postgres@db/tiered_homework_test backend python -m pytest -q --tb=short 2>&1 | tail -20
```

**期望**：
- **0 failed** ✓（如 1+ failed = subagent 必立即停手 + 详细诊断报回决策室）
- 全套 passed = #114 收口绿

**关键失败检查**（如 0 failed 不达成）：
- `test_real_llm_review_flow_lesson_plan_pending_to_reviewed` 必绿（per P1 (b) 修复）
- `test_academic_api / test_textbook_upload_real_pdf / test_p0n1_subject_ownership / test_p15_title_quality / test_cross_user_isolation` 全绿（per P0 chown + P1 (b) test 库干净）
- 0 失败 = P0 + P1 + B2 修复全闭环

---

## Step 6: 派工后 4 验 baseline（test 库 必一致）

**test 库 4 验**（同 §Step 3 期望）：
- alembic: `0011_question_images (head)` ✓
- pytest: **0 failed** ✓
- user_tables: 19
- enums: 7

**dev 库 4 验**（0 接触证明）：
- user_tables: 19（与派工前一致）
- enums: 7（与派工前一致）

**派工后 vs 派工前 一致性**：
- test 库：pytest 0 failed（派工前 N>0，**派工后必 0**）
- dev 库：0 接触证明

---

## Step 7: commit（1-2 笔，4 字段 + [origin-push]）

**commit 1：B2 修法**（test 库 + conftest / docker-compose / init script；如必改 1 笔）：
```bash
git add backend/conftest.py scripts/init-test-db.sql docker-compose.test.yml  # 按实际改的文件
git status --porcelain  # 必只含本笔范围
git commit -m "chore(修复 #114 B2 修法): test 库创建 + 容器 pytest 显式 -e DATABASE_URL=...test (结构性防 §治理.19)

依赖: work order notes/work-orders/113-9-pre-existing-test-failures.md §修复后验证清单 + ci.yml:53 先例 + 复验提醒 (本次 -k 只证子集, #114 必跑全套)
下游: 容器 pytest 不再碰 dev 库 = §治理.19 字面绿口头红 trap 防御; #114 派工 #1 试及后续子代理必带 -e DATABASE_URL
预检: dev 库 0 接触证明 (派工后 4 验 baseline 派工前后一致 = 19/7); test 库 alembic 0011 / 19/7 (派工后)
范围: <实际改的文件清单> [origin-push]"
```

**commit 2：P1 (b) 修复**（test 修 + source 注释订正；1 笔）：
```bash
git add backend/tests/test_academic_llm.py backend/app/api/v1/routers/academic.py
git status --porcelain  # 必只含本笔范围
git commit -m "fix(P1 #114): test_academic_llm X-User-Id 2→1 + academic.py:912 注释订正 (per 决策室拍 b + A2 理由)

依赖: work order notes/work-orders/113-9-pre-existing-test-failures.md §决策室拍 + §失败 2 修法方向 (A2 订正理由)
下游: test_real_llm_review_flow_lesson_plan_pending_to_reviewed 1/9 绿; 跨用户 404 = D-29 反 ID 泄漏门保留
预检: pytest trace 验 X-User-Id 已变; source 注释 grep 验; 全套 pytest 0 failed (test 库)
范围: backend/tests/test_academic_llm.py:227 (1 行) + backend/app/api/v1/routers/academic.py:912 (1 行注释) [origin-push]"
```

**commit message 必含 4 字段** —— 父会话核源时 `git log -1..HEAD --format=%B | grep` 验。

**[origin-push]** = 必带（实际代码修改；推双 remote）

---

## 完成定义

1-2 笔 commit + 报回 7 段（Step 1-7）+ 4-source 核源 + 派工后 4 验 baseline 一致 + 必跑全套 pytest 0 failed = subagent 完成

**任何 1 步失败 / 4 验 baseline 不一致 / pytest 不 0 failed = 立即停手 + 详细诊断报回决策室**

---

## 报回格式（必带，4-source 核源 + 7 步 状态）

```markdown
## Step 1 完成
- 6-line handshake: <真值>
- B2 修法先例探: ci.yml:53 = <内容>; dev 库 alembic = <内容>; postgres CREATE DATABASE = <ok/fail>; docker-compose test-db = <有/无>
- 状态: ✅ / ⚠️ / ❌

## Step 2 完成（B2 修法实施）
- 选 A/B/C: <选项>
- 新增/修改文件: <清单>
- B2 修法命令: <真值>
- dev 库 0 接触证明: <真值>
- 状态: ✅ / ⚠️ / ❌

## Step 3 完成（派工前 4 验 baseline）
- test 库: alembic=<值> / pytest=<N failed, M passed, K skipped> / user_tables=<值> / enums=<值>
- dev 库: user_tables=<值> / enums=<值>
- 状态: ✅ / ⚠️ / ❌

## Step 4 完成（P1 (b) 实施）
- test 修: pytest trace 验真 (X-User-Id 已变)
- source 注释订正: grep 验真
- 2 行 diff: <git diff --stat HEAD>
- 状态: ✅ / ⚠️ / ❌

## Step 5 完成（必跑全套 pytest 收口）
- 全套 pytest 输出: <N failed, M passed, K skipped>
- 关键 test 状态: test_real_llm_review_flow=<PASS/FAIL>; test_textbook_upload_real_pdf×3=<PASS>; test_p0n1=<PASS>; test_p15×2=<PASS>; test_academic_api=<PASS>; test_cross_user_isolation=<PASS>
- 状态: ✅ / ⚠️ / ❌

## Step 6 完成（派工后 4 验 baseline）
- test 库: alembic=<0011> / pytest=<0 failed> / user_tables=<19> / enums=<7>
- dev 库: user_tables=<19> / enums=<7> (0 接触)
- 派工后 vs 派工前: test 库 pytest 0 failed (派工前 N>0); dev 库 0 接触
- 状态: ✅ / ⚠️ / ❌

## Step 7 完成（commit + push）
- commit SHAs: <hash1> [B2] + <hash2> [P1] (或 1 笔合)
- 4 字段齐: 依赖 ✓ / 下游 ✓ / 预检 ✓ / 范围 ✓
- [origin-push] 标记: ✓
- 范围: git diff --stat <base>..HEAD = <清单>
- 双 remote sync: master = origin = github = <hash>
- 状态: ✅ / ⚠️ / ❌

## 4-source 核源（父会话用）
- Source 1 (commit count): <N>
- Source 2 (范围): <git diff --stat <base>..HEAD>
- Source 3 (4 字段): 全部齐
- Source 4 (push): master = origin = github = <hash> (0 ahead)
```

---

## 严禁

- 跳过任何 Step（6-line handshake 不可省）
- 改禁动清单任何一项（除 #114 必改的 test_academic_llm.py:227 + academic.py:912 注释）
- pytest 必带 `-e DATABASE_URL=...tiered_homework_test`（不带 = §治理.19 字面绿口头红 trap 重触发）
- 改测试期望当修根因（D-43-X #14：除本任务指定的 test_academic_llm.py:227 1 行）
- 推送到非双 remote 路径
- 合并 7 步诊断（必分 7 段详写）
- 漏报 pytest trace 关键行号
- "已 ruff/mypy 通过" ≠ "代码能工作" —— **本任务不需 ruff/mypy**（实施小）；但**pytest trace + grep 验真 必带**
- **不留 -k 子集尾巴**（per 复验提醒；必跑全套 `python -m pytest -q`）

---

## 决策室权限

- 任何时候中止你的任务（CHARTER §7.0 决策室权限高于工地）
- pytest 不 0 failed / 4 验 baseline 任何一项不符 = silent failure 模式 = 立即停手 + 报回
- 失败停手 ≠ 失败 = 详细诊断报回 = 决策室重派 / 修 brief / take over

---

## 关联引用

- **触发源**：`notes/work-orders/113-9-pre-existing-test-failures.md`（commit `c8ca4f9`）§决策室拍 + §修复后验证清单
- **承接 #113**：commit `110cd46` (work order) + `c8ca4f9` (P0 留痕 + 8 订正)
- **派工协议**：D-43 §5 + corrective-rule-1-dispatch-protocol (4-step)
- **Brief 纪律**：subagent-brief-discipline-constraints
- **握手协议**：subagent-env-handshake (6-line + trap 签名)
- **drop_all trap**：§治理.16/19/20 → B2 修法升级为结构性防
- **D-43 §5**：决策室不修代码逻辑 → #114 派 subagent
- **D-83 不立原则**：不立新 D-XX
- **D-43-X 协作纪律**：结论性陈述必须自我验证
- **修正规则 #1**：4-step 派工协议
- **复验提醒**：本次 -k 只证子集 → #114 必跑全套
