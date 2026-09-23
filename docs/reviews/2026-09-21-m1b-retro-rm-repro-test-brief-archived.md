# M1-B retro 7ff30aa repro test git-rm 工地 brief（决策室派工）

> **工单命名**：`M1-B retro git-rm-repro`（临时命名，不入 D-30 milestone 序列）
> **前置依赖**：CI-1-1 已完成（commit `4e73c65` 已推 GitHub main），CI run #6 step 6 ruff FAIL 因 7ff30aa 引入的 repro test
> **关联决策**：D-39 归档原则（SQLite 复现已落到 review4 报告）/ D-36-B 机器证据 / D-43 决策室不修代码
> **工人 ID**：`m1b-retro/git-rm-repro-test`
> **工作目录**：当前 dev box `/home/wsq_1/tiered-homework-platform`
> **预算**：≤ 5 分钟
> **不入主会话**

---

## 1. 目标

删除 `backend/tests/test_review4_p11_fix_repro.py` 文件 + commit + push GitHub + 等 CI run #7 5 命令实跑通 = **D-36-B 完整机器证据** + **M2 解封基础设施就绪**。

**为什么删这个文件**（用户拍 B）：
- review4 已通过，SQLite minimal 复现脚本已落到 `docs/reviews/2026-09-21-27515d2.md`（D-39 归档原则）
- 该文件是 review4 worker 一时性产物，不是回归测试
- 文件含 6 个 ruff errors（F401 × 2 unused imports + F811 × 2 重定义 + F541 × 2 f-string）—— 阻断 CI step 6
- M2-A.0 commit `3ccdf29` 自己写的 `test_question_crud.py` 不依赖这文件
- 删它是最稳路径：承认"这文件没用"+ 解 ruff blocker

---

## 2. 必读上下文

1. `docs/decisions.md` §D-39（审查材料归档原则）
2. `docs/reviews/2026-09-21-27515d2.md`（review4 报告含 SQLite 复现脚本）
3. `docs/reviews/2026-09-21-fbb7275.md`（review3 报告）
4. `.github/workflows/ci.yml`（CI-1-1 已加 working-directory: backend）
5. 当前本地 master HEAD = `3ccdf29`（M2-A.0 commit，未推）
6. 当前 GitHub main = `4e73c65`（CI-1-1 已推）

**前置验证**：
```bash
cd /home/wsq_1/tiered-homework-platform
git log --oneline -5
# 期望：3ccdf29 M2-A.0 / 4e73c65 CI-1-1 / 7ff30aa docs(retro) review 归档 / 27515d2 P1-1-1
```

---

## 3. 任务清单（每条带命令 + 期望退出码）

### 3.1 git rm 文件

```bash
cd /home/wsq_1/tiered-homework-platform

# 删除 review4 repro test
git rm backend/tests/test_review4_p11_fix_repro.py

# 核对
git status --short
# 期望：D backend/tests/test_review4_p11_fix_repro.py（deleted）
```

### 3.2 commit

```bash
git commit -m "test(review4): git rm repro test 文件（review4 SQLite 复现已归档到 review4 报告）

触发：CI run #6 step 6 ruff FAIL 阻断后续 step
- 7ff30aa commit 引入的 test_review4_p11_fix_repro.py 含 6 lint errors
- F401 unused imports × 2 + F811 重定义 × 2 + F541 f-string × 2
- review4 已通过，SQLite 复现脚本已落到 docs/reviews/2026-09-21-27515d2.md（D-39）
- 文件是 review4 worker 一时性产物，不是回归测试
- M2-A.0 commit 3ccdf29 自己写的 test_question_crud.py 不依赖这文件

变更（1 文件删）：
- backend/tests/test_review4_p11_fix_repro.py (deleted)

D-36-A 环境钉死：commit SHA + Python 3.11（CI runner）
D-36-B 机器证据（CI run #7 期望）：
- step 5 Install Python deps → success
- step 6 Ruff check → success（6 errors 解决）
- step 7 Mypy → failure（B1 pre-existing narrowing 不在本工单）
- step 8 Alembic upgrade → success
- step 9 Pytest → success（PG service + integration tests 真跑）
- step 11 Verify → failure（DEEPSEEK_API_KEY GitHub Secret 未配，预期）

D-43 决策室越权反思：本 commit 单纯删文件，不改代码逻辑，由 subagent 工地执行
D-33 中立：commit message 仅描述事实 + 决策 ID + CI 期望"

git rev-parse HEAD
echo "COMMIT_EXIT=$?"
```

### 3.3 push GitHub 触发 CI run #7

```bash
git push github master:main 2>&1
echo "PUSH_EXIT=$?"
# 期望：PUSH_EXIT=0
# 期望输出：... master -> main
```

### 3.4 等 CI 跑通（≤ 60 秒）

```bash
sleep 60
curl -sL --max-time 15 \
  "https://api.github.com/repos/xingyun-wang/again/actions/runs?per_page=1" \
  -o /tmp/runs.json
python3 -c "
import json
d = json.load(open('/tmp/runs.json'))
for r in d.get('workflow_runs', []):
    print(f\"run #{r['run_number']} | {r['head_sha'][:7]} | status={r['status']} | conclusion={r.get('conclusion')}\")
"
```

### 3.5 拉 jobs 详情

```bash
# 从 /tmp/runs.json 取 run_id
RUN_ID=$(python3 -c "
import json
d = json.load(open('/tmp/runs.json'))
print(d['workflow_runs'][0]['id'])
")

curl -sL --max-time 15 \
  "https://api.github.com/repos/xingyun-wang/again/actions/runs/${RUN_ID}/jobs" \
  -o /tmp/jobs.json
python3 -c "
import json
d = json.load(open('/tmp/jobs.json'))
for j in d.get('jobs', []):
    print(f\"--- job: {j['name']} (conclusion={j['conclusion']}) ---\")
    for s in j.get('steps', []):
        m = 'OK' if s.get('conclusion') == 'success' else ('FAIL' if s.get('conclusion') == 'failure' else 'SKIP')
        print(f'  {m} step {s[\"number\"]:2d}: {s[\"name\"]}')
"
```

---

## 4. 提交后回报

回报决策室：
- commit SHA
- PUSH_EXIT
- CI run #7 状态（run # + head_sha + status + conclusion + html_url）
- 11 个 step 全列表（OK / FAIL / SKIP）
- 失败的 step 是否与本工单相关
- **M2 解封基础设施就绪判定**：
  - ✅ step 5/6/8/9 全过 → 基础设施就绪 → 决策室推 M2-A.0 commit 3ccdf29
  - ⚠️ step 7 Mypy FAIL（B1 pre-existing）—— 不阻 M2 解封
  - ⚠️ step 11 Verify FAIL（DEEPSEEK_API_KEY 缺）—— 不阻 M2 解封

---

## 5. 不要做

- ❌ 不要 push origin (Gitee) — 决策室控制 Gitee 推送
- ❌ 不要 merge / tag
- ❌ 不要改 ci.yml / backend/requirements.txt / 其他文件
- ❌ 不要 spawn 第三方 subagent
- ❌ 不要让 mypy step 加 continue-on-error（CI-1 工单已删，故意让 B1 暴露）

---

## 6. 与 M2-A.0 的串行关系

本工单先推 GitHub → CI run #7 跑通（仅 repro test 删除）→ 决策室再推 M2-A.0 commit `3ccdf29` → CI run #8 5 命令实跑 M2-A.0。

避免顺序：
- 错误：M2-A.0 先推 → CI 5 命令又 fail（repro test 仍在）→ 看不到 M2-A.0 修复
- 正确：本工单先跑通 → CI run #7 全绿（或仅 baseline FAIL）→ M2-A.0 推 → CI run #8 验证
