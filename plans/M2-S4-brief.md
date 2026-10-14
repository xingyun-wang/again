# M2-S4 brief — 作业单 PDF 导出（v0.5 §3.6 + §7.5；reportlab 流式直返）

> **起源**：星轨 S4 实施流程 v2（2026-10-14 14:00，HEAD `3a54d56`）+ 用户 2026-10-14 20:19 P0 拍板
> **HEAD base**：`9f34dcc`（audit 收口后 1 笔；本 brief 起草后 落地后 = 48）
> **派工目标**：1 subagent 闭环 S4 PDF 导出（替换 S3 stub；真 PDF 流式直返）
> **决策已拍**（D-S4-1/2/3）：见 §二
> **基线已绿**：init-test-db.sh 4 验 = 0011/19/7 ✓；pytest = 318 passed / 9 skipped / 0 failed in 154.32s ✓
> **模板依从**：`plans/M2-S3-frontend-brief.md`（15 节结构）

---

## 一、范围

- **替换** `backend/app/api/v1/routers/assignments.py:332-383` 的 S3 stub → 真 PDF 流式直返
- **新增** `backend/app/services/assignment_export.py`（PDF 渲染 service 模块）
- **新增** `backend/tests/api/v1/test_pdf_export.py`（5 case 端到端）
- **1 份/作业单** 粒度（D-S4-2 ①）—— 不做每生一份（M2 构造不出 per §3.2）
- **流式直返**（D-S4-3 ①）—— 不落盘（避免 UPLOADS_DIR 撞 #113 同目录）
- **reportlab** 选型（D-S4-1）—— pure python，Dockerfile 零系统依赖

**不**包含：每生一份 PDF（M3 范围）、异步任务队列（M3 范围）、邮件发送（M3 范围）、PDF 水印/签名（M4 范围）。

## 二、§7.5 + §3.6 拍板（**D-S4-1 / D-S4-2 / D-S4-3**）

### D-S4-1：PDF 库 = **reportlab**

- **理由**：pure python（无 pango/cairo 系统依赖），Dockerfile 零 system packages；模板能力足够 1 份作业单（标题/段落/表格/分页）
- **备选否决 weasyprint**：需 cairo + pango 系统包 ⇒ 改 Dockerfile + CI 镜像升级
- **备选否决 fpdf2**：模板能力弱，无内建 Table 排版
- **版本**：`reportlab>=4.0,<5.0`（4.x stable；与 pyproject 已有 lib 不冲突）

### D-S4-2：交付粒度 = **① 1 份/作业单**

- **理由**：v0.5 §3.2 强制 M2 阶段构造不出每生一份（学生端未启）
- **每生一份时序**：M3 + 学生端落地后；本期 brief 不预留 per-student 接口
- **作业单内容**：抬头 + §0 档位分布 + §2 题目列表（per chapter × 4 档分节） + §3 审阅状态

### D-S4-3：返回方式 = **① 流式直返**

- **理由**：MVP 最简，无中间文件 = 无文件系统权限问题（#113 同目录规避）
- **备选否决 ② 落盘**：写 `UPLOADS_DIR = /app/data/uploads` = 与 #113 根因 #1 同目录；硬前置 = 必须先拿到干净 test 库基线（**已绿 per §十一**）
- **接口形态**：`Response(bytes, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=..."})` —— **移除** S3 的 `response_model=AssignmentExportResponse`（stub 字段无意义）

## 三、严禁

- **严禁** 放松 §7.5 闸门（`review_status != APPROVED → 403` 必保留；`routers/assignments.py:367-374` 不动逻辑）
- **严禁** D-29 B 项违反（跨用户访问仍返 **404** 而非 403；不暴露存在性）
- **严禁** 改动 §7.5 闸门位置或 ORM enum 判别方式（DB 侧判 `KnowledgeReviewStatus.APPROVED`，不用 API Literal）
- **严禁** 直接调 S3 stub response（必须真生成 PDF；stub response 是过渡态）
- **严禁** 新增 file storage / 中间文件（流式直返 = 内存 BytesIO → 立即返；不写盘）
- **严禁** pip install 跳过 mirror（必须 `--index-url https://mirrors.tencent.com/pypi/simple/`；与既有约定一致）
- **严禁** requirements.txt 与 Dockerfile 双 pip install 漏一处（3 处必同步：requirements.txt + pyproject.toml + Dockerfile pip × 2；per 既有 `tenacity` 教训）
- **严禁** pytest 跳过/装饰（xfail/skip = 退单；5 case 必真跑）
- **严禁** 跨工单扩散（S4 改 S3 代码 = 退单；§7.5 闸门段除外不动）

## 四、复用既有模式（核源 2026-10-14 20:19）

- `scripts/init-test-db.sh`（`90393f7` 修法）：pytest 前必跑；4 验 baseline = 0011/19/7
- `backend/tests/fixtures/questions_pool.jsonl` + `questions_tier_demo.json`（`3b68529` C/D 池）：测 PDF 渲染的 chapter/tier 字段
- `backend/app/api/v1/routers/assignments.py:367-374`（§7.5 闸门）：**不动**；只改 :332-382 的 stub 段
- `backend/app/api/v1/schemas/assignments.py:116-128`（`AssignmentExportResponse`）：**B4-1 决策 = 移除**（流式直返不返此 schema；保留 schema 字段无害但无意义）
- `backend/app/models/`（ORM）：`Assignment` / `Chapter` / `Question` / `KnowledgeReviewStatus`（用 `assignment.chapters` / `assignment.review_status` ORM 关系）
- `backend/app/deps.py`（`get_current_user_id`）：auth_client fixture 用
- `backend/tests/conftest.py`：`auth_client` / `assignment_approved` / `assignment_pending_review` 已有 fixtures 模式
- §治理.19 4 验 baseline（per `docs/PROJECT-CHARTER-protocol.md`）
- D-43-X §5 派工纪律（per `docs/decisions.md`）
- 9 个已有 brief 模板：本 brief 15 节结构依从 `plans/M2-S3-frontend-brief.md`

## 五、API 设计（contract — 不许改）

```
POST /api/v1/assignments/{id}/export
Headers: Authorization: Bearer <jwt>
  Content-Type: application/json

Response 200:
  Content-Type: application/pdf
  Content-Disposition: attachment; filename="assignment_{id}_{YYYYMMDDHHMMSS}.pdf"
  Content-Length: <bytes>
  body: <PDF bytes, %PDF 头>

Response 403:
  {"detail": "assignment {id} 未通过教师审阅（review_status=...），不能导出"}

Response 404:
  {"detail": "assignment {id} 不存在"}

Response 500:
  {"detail": "PDF 生成失败: <reason>"}
```

## 六、B4 必改 + pytest 验证

### B4-1：`AssignmentExportResponse` schema 移除（流式直返不需要）

- 现有 `schemas/assignments.py:116-128` 是 stub response model
- 流式直返 (D-S4-3 ①) 返 raw bytes，`response_model=...` 必须改 `Response`（FastAPI raw）
- **决策**：B4-1 = 移除 `response_model=AssignmentExportResponse` 改 `response_model=None` 或 `Response`；schema 字段保留无害（无 caller）
- **回滚点**：如未来需返 metadata，schema 字段直接复用

### B4-2：service 模块（新增）

- 路径：`backend/app/services/assignment_export.py`
- 入口：`def render_assignment_pdf(assignment: Assignment) -> bytes`
- 依赖：`reportlab.platypus.SimpleDocTemplate` / `reportlab.lib.pagesizes.A4` / `reportlab.lib.styles.getSampleStyleSheet` / `io.BytesIO`
- 输入：assignment ORM（含 `.chapters` / `.questions` / `.review_status` / `.title` / `.owner_user_id` / `.created_at`）
- 输出：PDF bytes（头 4 字节 = `b"%PDF"`）

### B4-3：router 改（最小侵入）

- 路径：`backend/app/api/v1/routers/assignments.py:332-383`
- 改动：
  1. `response_model=AssignmentExportResponse` → `response_model=None`（或直接用 `Response`）
  2. endpoint body 末尾：从 `return AssignmentExportResponse(...)` → `return Response(content=render_assignment_pdf(assignment), media_type="application/pdf", headers={...})`
  3. import：`from app.services.assignment_export import render_assignment_pdf`
- **不动**：§7.5 闸门段（:355-374）；D-29 B 项段（:345-354）

### B4-4：requirements + Dockerfile 3 处同步

- `backend/requirements.txt`：加 `reportlab>=4.0,<5.0`
- `backend/pyproject.toml:8-19`：dependencies 段加 `reportlab>=4.0,<5.0`
- `backend/Dockerfile`：2 处 pip install（builder ~:35 + runtime ~:78）均加 reportlab
- **3 处必同步**（per 既有 `tenacity` 教训：单加一处 = 镜像裂）

## 七、PDF 服务模块实现 spec（`app/services/assignment_export.py`）

```python
"""作业单 PDF 渲染 service（M2-S4 D-S4-1/2/3 锁定）。"""
from io import BytesIO
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)

from app.models import Assignment


def render_assignment_pdf(assignment: Assignment) -> bytes:
    """Render 1 份作业单 PDF（流式直返 per D-S4-3 ①）.

    Layout (per D-S4-2 ① 1 份/作业单):
    - 抬头: 作业名 / 老师 / 出题时间
    - §0 档位分布表 (D/C/B/A 4 档 + 题数)
    - §2 题目列表 (per chapter × 4 档分节)
    - §3 教师备注 / 审阅状态
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2 * 28, bottomMargin=2 * 28)
    styles = getSampleStyleSheet()
    story = []

    # 抬头
    story.append(Paragraph(f"<b>{_escape(assignment.title)}</b>", styles["Title"]))
    story.append(Paragraph(
        f"老师 ID: {assignment.owner_user_id} | 出题: {assignment.created_at.isoformat()}",
        styles["Normal"],
    ))
    story.append(Spacer(1, 12))

    # §0 档位分布
    story.append(Paragraph("<b>§0 档位分布</b>", styles["Heading2"]))
    tier_rows = [["档位", "题数"]]
    for tier_label, tier_code in [("D 基础", "D"), ("C 进阶", "C"), ("B 挑战", "B"), ("A 扩展", "A")]:
        tier_rows.append([tier_label, str(_count_tier(assignment, tier_code))])
    tier_table = Table(tier_rows, colWidths=[3 * 28, 2 * 28])
    tier_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    story.append(tier_table)
    story.append(Spacer(1, 12))

    # §2 题目列表（per chapter × 4 档分节）
    for chapter in assignment.chapters:
        story.append(Paragraph(f"<b>§2 {_escape(chapter.title)}</b>", styles["Heading2"]))
        for tier_code in ["D", "C", "B", "A"]:
            tier_qs = [q for q in chapter.questions if q.tier == tier_code]
            if not tier_qs:
                continue
            story.append(Paragraph(f"<i>[{tier_code}]</i>", styles["Normal"]))
            for q in tier_qs:
                story.append(Paragraph(f"&nbsp;&nbsp;{_escape(q.stem)}", styles["Normal"]))
            story.append(Spacer(1, 6))
        story.append(Spacer(1, 6))

    # §3 审阅状态
    story.append(Paragraph(
        f"<b>§3 审阅状态: {assignment.review_status.value}</b>",
        styles["Heading2"],
    ))

    doc.build(story)
    return buf.getvalue()


def _count_tier(assignment: Assignment, tier: str) -> int:
    return sum(1 for ch in assignment.chapters for q in ch.questions if q.tier == tier)


def _escape(s: str) -> str:
    """reportlab Paragraph XML escape (限 < > & ' 避免 XML parse 错)."""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))
```

## 八、测试 spec（`backend/tests/api/v1/test_pdf_export.py`，**5 case 必全过**）

```python
"""S4 PDF 导出端到端测试（M2-S4 必跑；5 case 必全过）."""
import pytest
from fastapi.testclient import TestClient

from app.services.assignment_export import render_assignment_pdf


def test_pdf_export_403_when_not_approved(auth_client, assignment_pending_review):
    """§7.5 闸门: review_status != APPROVED → 403."""
    r = auth_client.post(f"/api/v1/assignments/{assignment_pending_review.id}/export")
    assert r.status_code == 403
    assert "未通过教师审阅" in r.json()["detail"]


def test_pdf_export_404_when_cross_user(auth_client_2, assignment_approved):
    """D-29 B 项: 跨用户 404 而非 403."""
    r = auth_client_2.post(f"/api/v1/assignments/{assignment_approved.id}/export")
    assert r.status_code == 404
    assert "不存在" in r.json()["detail"]


def test_pdf_export_200_returns_valid_pdf(auth_client, assignment_approved):
    """D-S4-3 ① 流式直返: 200 + application/pdf + 头 4 字节 = %PDF."""
    r = auth_client.post(f"/api/v1/assignments/{assignment_approved.id}/export")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    assert "attachment" in r.headers.get("content-disposition", "")


def test_pdf_export_contains_assignment_title(auth_client, assignment_approved, snapshot_pdf):
    """D-S4-2 ① 1 份/作业单: PDF 字节含作业名（落盘 + 解析验证）.

    注: PDF 是二进制，不能用 in assertion. 用 pdfplumber (test 依赖) 解析后校验文本.
    """
    r = auth_client.post(f"/api/v1/assignments/{assignment_approved.id}/export")
    pdf_path = snapshot_pdf(r.content, "approved")
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        text = "".join(p.extract_text() or "" for p in pdf.pages)
    assert assignment_approved.title in text
    assert "§0 档位分布" in text
    assert assignment_approved.review_status.value in text


def test_render_assignment_pdf_unit(assignment_approved):
    """service 层单测: 返 bytes + 头 4 字节 = %PDF + 长度 ≥ 1KB."""
    pdf_bytes = render_assignment_pdf(assignment_approved)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 1024
```

### 8.1 conftest fixture 增（最小侵入）

- `auth_client` / `auth_client_2`：2 个 user fixture（沿用既有）
- `assignment_pending_review`：`review_status=KnowledgeReviewStatus.PENDING`（或 `DRAFT`，待核源）
- `assignment_approved`：`review_status=KnowledgeReviewStatus.APPROVED`
- `snapshot_pdf(content, name) -> Path`：落 `/tmp/...pdf` 返回路径（per test 4 用）

### 8.2 `scripts/init-test-db.sh:70` enums 1 行修补（4 验口径一致）

```diff
- "SELECT count(*) FROM pg_type WHERE typtype='e';"
+ "SELECT count(*) FROM pg_type t JOIN pg_namespace n ON t.typnamespace=n.oid WHERE t.typtype='e' AND n.nspname='public';"
```

**理由**：现有查询计 ALL enums（含 public + pg_catalog 内部） = 错把 `pg_catalog` 内部 enum 算上。应限定 `public` schema = 与 `user_tables` 同一口径（"用户表 = 19"，enums 也应只数用户域 enum = 7，**不**数 pg_catalog 内部 enum）。当前实际值 7 是因 pg_catalog 恰好无 enum；语义对齐 = 修。

**实证前**（不改时）：`enums: 7` 偶发等于 `pg_catalog` 0 + `public` 7
**实证后**（改后）：`enums: 7` 严格 = `public` 7

## 九、Commit 划分（**3 commit；守 §5 教训 #9 不并片**）

1. **`chore(S4 deps): reportlab 3 处同步`**
   - `backend/requirements.txt` + `backend/pyproject.toml` + `backend/Dockerfile` (× 2 pip)
   - 加 `reportlab>=4.0,<5.0`
   - pdfplumber 已存在，不重加（避免与既有版本冲突）

2. **`chore(S4 infra): init-test-db.sh enums 口径对齐`**
   - 1 行 SQL 修补（`:70` + JOIN + schema 限定）
   - 改 4 验 baseline 口径 = 严格 public schema

3. **`feat(S4 service + router + tests): PDF 流式直返`**
   - `app/services/assignment_export.py`（新增）
   - `routers/assignments.py:332-383`（改 stub → 流式）
   - `tests/api/v1/test_pdf_export.py`（新增 5 case）
   - `tests/conftest.py` 增 fixture（如缺）

## 十、入场闸（**必读**；subagent 派工前必读 §一-§九）

1. 读 §一-§九 全 + 本节 + §十一-§十四
2. 跑 `bash scripts/init-test-db.sh`（期望 0011/19/7）
3. 跑 `git status --porcelain`（期望 0 行）
4. 跑 `git log -1 --format=%B | grep -q '\[origin-push\]'`（commit 留 trace）

派工后必跑：
1. `bash scripts/init-test-db.sh`（再验 4 验 baseline 一致）
2. `docker compose exec -T -e DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/tiered_homework_test backend python -m pytest tests/api/v1/test_pdf_export.py -v`（5 case 全过）
3. `docker compose exec -T -e DATABASE_URL=... backend python -m pytest -q`（全套 仍 318+ passed / 9 skipped / 0 failed）
4. `bash scripts/ledger_check.sh`（11/11 PASS，0 WARN）
5. `git status --porcelain`（0 行）
6. `git log -1 --format=%B | grep -q '\[origin-push\]'`

## 十一、§治理.19 派工前/后 4 验 baseline

**派工前**（per §治理.19 升级为结构性防）：
```bash
bash scripts/init-test-db.sh
# 期望: alembic=0011 / user_tables=19 / enums=7
```

**派工后**（同）：
```bash
bash scripts/init-test-db.sh
# 期望: alembic=0011 / user_tables=19 / enums=7 (与派工前一致)
```

**当前基线**（@ 2026-10-14 20:16 per `90393f7` 修法）：
- alembic: `0011_question_images (head)`
- user_tables: 19
- enums: 7（修后严格 = public 7）

## 十二、D-43-X §5 修正规则 #1 派工纪律

- 派工前必读：§一-§十一 全
- 派工 brief 内容不得改（本 brief 是 contract；subagent 改 brief = 退单）
- subagent 报回格式 per §十四（6-line handshake + 11 必报）
- 严禁跨工单扩散（S4 改 S3 代码 = 退单；§7.5 闸门段除外不动）
- 严禁 pytest 跳过/装饰（xfail/skip = 退单；5 case 必真跑）
- 严禁静默 `try/except` 吞错（PDF 渲染失败必 raise → 500 详情）

## 十三、完成定义（DoD）

- [ ] commit 1 (chore deps) 落字：reportlab 3 处同步（pdfplumber 已存在）
- [ ] commit 2 (chore infra) 落字：init-test-db.sh:70 enums 1 行修补
- [ ] commit 3 (feat service+router+tests) 落字：service 新建 + router 改 + 5 case 全过
- [ ] `bash scripts/init-test-db.sh` 派工前 = 派工后 = 0011/19/7
- [ ] `pytest tests/api/v1/test_pdf_export.py -v` = **5 passed, 0 failed, 0 skipped**
- [ ] `pytest -q` 全套 = **318+ passed, 9 skipped, 0 failed**
- [ ] `bash scripts/ledger_check.sh` = 11/11 PASS, 0 WARN
- [ ] `git status --porcelain` = 0 行
- [ ] commit message 全含 `[origin-push]`
- [ ] `git push origin master` + `git push github master` 成功
- [ ] `bash ~/zaiyao-memory/backup.sh` 成功（zaiyao-memory 同步 + Gitee push）

## 十四、报回格式（每 commit 必带 + 6-line handshake）

**每 commit 报回**：
```
commit <SHA>
files: <list>
+lines / -lines
pytest_local: <"N passed, M failed, K skipped" string>
ledger_check: <"11/11 PASS" string>
[origin-push]: yes
```

**6-line handshake**（派工后必报）：
1. commit SHA 最新 1 笔
2. pytest `tests/api/v1/test_pdf_export.py -v` 输出尾部 15 行
3. pytest 全套 `-q` 输出尾部 5 行
4. `git show --stat HEAD` 输出
5. 偏离 brief 项（如有；无则"无偏离"）
6. 风险/盲区（如有；无则"无风险"）

## 十五、修订追记

- **2026-10-14 20:19** 起草（载曜，per 星轨 v2 + 用户拍 D-S4-1/2/3）
  - 拍板来源：
    - D-S4-1 reportlab：星轨 v2 §2.1 / 用户 2026-10-14 20:19 接受
    - D-S4-2 ① 1 份/作业单：星轨 v2 §2.2 / 用户 2026-10-14 20:19 接受
    - D-S4-3 ① 流式直返：星轨 v2 §2.3 / 用户 2026-10-14 20:19 接受
  - 实证基线：
    - HEAD = `9f34dcc`（audit 收口 1 笔后）
    - init-test-db.sh 4 验 = 0011/19/7
    - pytest baseline = **318 passed / 9 skipped / 0 failed in 154.32s**（per B-1 §一.3）
    - 文档 15 节结构依从 `plans/M2-S3-frontend-brief.md`
  - 1 处架构决策（**B4-1 schema 移除**）：流式直返不返 `AssignmentExportResponse`；`response_model=None` 替代
  - 1 处 1 行修补（**B4-2 init-test-db.sh:70 enums schema 限定**）：与 user_tables 口径对齐
  - 1 处依赖决策（**B4-4 3 处同步**）：builder/runtime split 防镜像裂；pdfplumber 沿用现有
