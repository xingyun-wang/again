# M1-B retro CI-1-1 工地 brief（决策室派工）

> **工单命名**：`M1-B retro CI-1-1`（沿用 D-30 命名法；CI-1 续号）
> **前置依赖**：review4 通过，CI 路径问题已知
> **关联决策**：D-31 / D-36-A/B/C / D-40 / D-42 / D-43
> **工人 ID**：`m1b-retro/ci1-1-working-directory`
> **工作目录**：当前 dev box `/home/wsq_1/tiered-homework-platform`
> **预算**：≤ 15 分钟
> **不入主会话**

---

## 1. 目标

完成 **CI-1-1** = 修复 ci.yml working-directory 问题 + 推 GitHub 触发 CI run #6 + 等 5 命令实跑绿 = D-36-B 完整机器证据。

**为什么 CI-1-1 必须做**：
- review4 通过 ≠ CI 5 命令全绿
- M2-A 工地启动前必须 CI 绿，否则 M2-A worker 跑测试会撞 ci.yml 路径问题
- D-36-B 机器证据是下个 milestone 启动的基础设施

---

## 2. 必读上下文

1. `docs/decisions.md` §D-30 / D-31 / D-36-A/B/C / D-40 / D-42 / D-43 / D-44
2. `docs/reviews/2026-09-21-27515d2.md`（review4 报告 §6 CI run #5 evidence）
3. `.github/workflows/ci.yml` 当前结构（约 220 行，**注意：C 路径前 working-directory 未加**）
4. `backend/requirements.txt`（tenacity / fastapi / sqlalchemy 等 17 行已列）

**前置验证**：
```bash
cd /home/wsq_1/tiered-homework-platform
git log --oneline -5
# 期望：HEAD = 7ff30aa（review 归档 commit），前面 27515d2 = P1-1-1 fix
```

---

## 3. 任务清单（每条带命令 + 期望退出码）

### 3.1 工作目录修改

文件 `.github/workflows/ci.yml` line 71-74：

```yaml
# 改前：
      - name: Install Python deps
        run: |
          python -m pip install --upgrade pip
          pip install -r backend/requirements.txt

# 改后（working-directory 加在所有 backend step 之前统一）：
      - name: Install Python deps
        working-directory: backend
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
```

**所有需要 cwd 是 backend 的 step 都要加 `working-directory: backend`**：
- step 5 Install Python deps
- step 6 Ruff check
- step 7 Mypy
- step 8 Alembic upgrade
- step 9 Pytest
- step 11 Verify end-to-end

**简化为**：把这些 step 的 `run:` 行全部加 `working-directory: backend`，路径从 `backend/requirements.txt` 改为 `requirements.txt` / `app` / `tests` 等相对路径。

**不要做**：
- ❌ 不要 `cd backend && ...` 内嵌在 run（GitHub Actions 推荐用 working-directory，不是 cd）
- ❌ 不要改 trigger / deps 安装内容 / actions 节点（CI-1 工单已落地，CI-1-1 不重做）
- ❌ 不要删 alembic-prep step（已删，C 路径）

### 3.2 push + 等 CI 跑通

```bash
cd /home/wsq_1/tiered-homework-platform
git add .github/workflows/ci.yml
git status --short
# 期望：1 file changed（ci.yml）

git commit -m "ci: CI-1-1 working-directory: backend 修 step 5 路径问题

触发：CI run #5 step 5 Install Python deps failed（doc/...）
冻结 SHA：27515d2

变更（1 文件 ci.yml）：
- 5 个 backend step（Install / Ruff / Mypy / Alembic / Pytest / Verify）
  加 working-directory: backend
- 路径从 backend/requirements.txt → requirements.txt
- 其他 step（actions/setup-python / checkout）不动

D-36-A 环境钉死：commit SHA + Python 3.11 + ubuntu-latest
D-36-B 机器证据（dev box 真跑）：
- yaml.safe_load → EXIT=0（YAML 合法）
- git grep actions/node@v4 → EXIT=1（0 命中，CI-1 已修）
- git grep alembic-prep → EXIT=1（0 命中，C 路径已删）

D-40 push 策略：本 commit 后 push github master:main
→ ci.yml trigger branches:[main] 触发 run #6
→ 5 命令实跑 + D-36-A 环境钉死锚 + artifact 落
= D-36-B 机器证据完整

D-33 中立：commit message 仅描述事实 + 决策 ID + 退出码原文"

git push github master:main 2>&1
echo "PUSH_EXIT=$?"
```

### 3.3 等 CI 跑通（≤ 5 min）

```bash
sleep 60 && curl -sL --max-time 15 \
  "https://api.github.com/repos/xingyun-wang/again/actions/runs?per_page=1" \
  -o /tmp/runs.json 2>&1
python3 -c "
import json
d = json.load(open('/tmp/runs.json'))
for r in d.get('workflow_runs', []):
    print(f\"run #{r['run_number']} | {r['head_sha'][:7]} | status={r['status']} | conclusion={r.get('conclusion')}\")
"
```

**期望 run #6 状态**：
- step 5 Install Python deps ✅（working-directory fix 生效）
- step 6 Ruff check ✅（dev box 已确认 ruff 0）
- step 7 Mypy — 可能 FAIL（B1 pre-existing narrowing）— 这是已知 baseline
- step 8 Alembic upgrade ✅（CI runner 有 PG service）
- step 9 Pytest — 可能 FAIL（dev box 无 psycopg，但 CI 有）— 期望真跑起来
- step 11 Verify end-to-end — **会 FAIL**，因为 `secrets.DEEPSEEK_API_KEY` 未在 GitHub Secrets 配置（用户拍 D-40 已授权但未实际配）

**重要**：
- step 7 / step 11 FAIL 是**已知问题**，与本工单修复无关
- **判定本工单成功的标准**：step 5/6/8/9 全过 + step 7 mypy 失败与 baseline 一致 + step 11 verify 失败因为缺 secret

### 3.4 jobs 详情核对

```bash
curl -sL --max-time 15 \
  "https://api.github.com/repos/xingyun-wang/again/actions/runs/<RUN_ID>/jobs" \
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
- YAML 合法验证 EXIT
- push EXIT
- CI run #6 状态（status / conclusion / head_sha）
- 11 个 step 全列表（OK / FAIL / SKIP）
- 失败的 step 是否与本工单相关

**判定本工单成功**：
- 5 命令实跑（Install / Ruff / Alembic / Pytest + Mypy baseline 一致）
- 工作目录路径问题真修

**判定本工单失败**：
- step 5/6/8/9 任一 FAIL 是 working-directory 问题（继续修）
- step 7 mypy 引入新错（B1-2 真修，不再 type: ignore）

---

## 5. 不要做

- ❌ 不要 push origin (Gitee) — 决策室控制 Gitee 推送
- ❌ 不要 merge
- ❌ 不要 spawn 第三方 subagent
- ❌ 不要改 ci.yml 外的文件
- ❌ 不要触发 CI（决策室控制 push 时机）
- ❌ 不要 git tag review/*（review3 + review4 已 tag 过，不能重打）
- ❌ 不要让 mypy step 加 continue-on-error（CI-1 工单已删，故意让 B1 暴露）

---

## 6. 与 D-43 决策室越权反思的关系

本工单是 subagent 工地（不是决策室），**不算决策室越权**。CI-1-1 commit 由 subagent 独立 commit，决策室只接收回报。
