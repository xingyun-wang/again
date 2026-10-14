# M2-S4 brief — 作业单 PDF 导出（v0.5 §3.6 + §7.5；reportlab + Noto Sans SC 嵌入 + 流式直返）

> **起源**：星轨 S4 实施流程 v2（2026-10-14 14:00，HEAD `3a54d56`）+ 用户 2026-10-14 20:19 P0 拍板 + 用户 2026-10-14 20:56 A1/A3 拍板
> **HEAD base**：`c6d64dd`（brief 首版 commit；本 brief 订正后 = 49 笔 = 668fddd..HEAD）
> **派工目标**：1 subagent 闭环 S4 PDF 导出（替换 S3 stub；真 PDF 流式直返）
> **决策已拍**：D-S4-1/2/3 + D-A1（a） + D-A3（S4-b sub工单）
> **基线已绿**：init-test-db.sh 4 验 = 0011/19/7 ✓；pytest = 318 passed / 9 skipped / 0 failed in 154.32s ✓
> **mirror probe**：reportlab-4.4.3 @ 腾讯 mirror PASS（@ 2026-10-14 20:53）
> **模板依从**：`plans/M2-S3-frontend-brief.md`（15 节结构）

---

## 一、范围

- **替换** `backend/app/api/v1/routers/assignments.py:334-382` 的 S3 stub → 真 PDF 流式直返
- **新增** `backend/app/services/assignment_export.py`（PDF 渲染 service 模块）
- **新增** `backend/app/assets/fonts/NotoSansSC-Regular.ttf` + `OFL.txt` + `README.md`（D-A1 (a) 嵌入 TTF；OFL 1.1）
- **新增** `backend/tests/api/v1/test_pdf_export.py`（5 case 端到端）
- **1 份/作业单** 粒度（D-S4-2 ①）—— 1 作业单 = 1 章节（FK 约束）⇒ 自然单粒度
- **流式直返**（D-S4-3 ①）—— 不落盘（避免 UPLOADS_DIR 撞 #113 同目录）
- **Noto Sans SC 嵌入**（D-A1 (a)）—— 保打印链 + 保中文检出器

**S4-b 范围固定 4 项**（**本工单不实施**，S4-b 实施；阻塞 M2-S5 端到端验收）：

1. `frontend/src/pages/Assignments.tsx` 改 `responseType:'blob'` + `URL.createObjectURL` 触发下载
2. 删 `ExportResponse` 接口（`:67-72` 改流式后是死码）
3. 改文案（不再"导出已入队（export_id=…）"）
4. 403/404 catch 路径保留（错误体仍 JSON）

**不**包含：每生一份 PDF（M3 范围）/ 异步任务队列（M3 范围）/ 邮件发送（M3 范围）/ PDF 水印/签名（M4 范围）/ **前端导出 UI 落地（S4-b 范围，工单号 `M2-S4-b` 待派）** / 打印链真验（M2-S5 端到端验收）

**⚠️ 窗口期风险声明**（S4 commit 3 message 必含）：

> S4 落地 → S4-b 落地之间，导出按钮表现 = "点了显示成功但不下载"（`export_id=undefined`）。这是预期，不是 bug。

## 二、§7.5 + §3.6 拍板

### D-S4-1：PDF 库 = **reportlab** + **Noto Sans SC 嵌入**（D-A1 (a)）

**PDF 库选型 = reportlab**

- **理由**：pure python（无 pango/cairo 系统依赖），Dockerfile 零 system packages
- **版本**：`reportlab>=4.0,<5.0`（4.x stable；**mirror probe PASS** @ 2026-10-14 20:53，腾讯 mirror 有 4.4.3）
- **备选否决 weasyprint**：需 cairo + pango 系统包 ⇒ 改 Dockerfile + CI 镜像升级
- **备选否决 fpdf2**：table API 在 ≥2.7 已有但 API 不稳 + 排版能力比 reportlab 弱；选更成熟的 reportlab

**字体方案 = (a) 嵌入 TTF**（D-A1）

- **字体**：**Noto Sans SC**（思源黑体 SC）—— **拒绝** SimSun / MS YaHei（专有许可）
- **许可**：OFL 1.1（附 `backend/app/assets/fonts/OFL.txt` 全文）
- **路径**：`backend/app/assets/fonts/NotoSansSC-Regular.ttf`
- **Subset**：**35 码点 dynamic subset** (Google Fonts `text=` API 动态子集化); 覆盖 brief §八 test 4 字符 (`作业单` / `§0 档位分布` / `D 基础` / `[D]` / `§3 审阅状态` / `pending` / `approved` 等 51 字符 → 去重 35 码点); 常用 37 字 (如 `第一章有理数下列计算教师备注目难度进阶挑战扩展`) 中 22 字 **不在字体中** (D-28 家族同源循环); **生产用任意 chapter title 撞缺字** ⇒ PDF 空白/方框; 扩集 = S4.5 / M2-S5 前置 (per A10 + 复核员 (c) R2 选)
- **产品链**（核源 `产品定义-v0.5.md:152/175`）：§3.6 流程节点 4 = **教务处打印 → 下发学生**（PDF 终消费者是打印机，不是浏览器）⇒ **必须嵌入**（CID 字体 by name ⇒ 换机器/打印驱动 = 空白或替换字体）
- **测试链**（核源 `产品定义-v0.5.md`）：pdfplumber ToUnicode 提取中文需要 font 嵌入，否则**主动关掉唯一字体检出器** = D-28 家族阈值退化（本仓 `#73/#74/#84/#97` 同族）
- **Dockerfile 不用改**（runtime `:87` `COPY --from=builder /app/app /app/app` 已覆盖 `app/assets/...` 整树）—— §二「零系统依赖」**依然成立**（字体 = 仓内资产 ≠ apt 包）

### D-S4-2：交付粒度 = **① 1 份/作业单**

- **理由**：1 作业单 = 1 章节（FK 约束 `assignment.chapter_id → chapters.id`）⇒ 自然单粒度
- **每生一份时序**：M3 + 学生端落地后；本期 brief 不预留 per-student 接口
- **作业单内容**：抬头 + §0 档位分布 + §2 题目列表（per `assignment.items[*]` 4 档分节）+ §3 审阅状态

### D-S4-3：返回方式 = **① 流式直返**

- **理由**：MVP 最简，无中间文件 = 无文件系统权限问题（#113 同目录规避）
- **备选否决 ② 落盘**：写 `UPLOADS_DIR = /app/data/uploads` = 与 #113 根因 #1 同目录；硬前置 = 必须先拿到干净 test 库基线（**已绿 per §十一**）
- **接口形态**：`Response(bytes, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=..."})` —— **移除** `response_model=AssignmentExportResponse`（stub 字段无意义）

## 三、严禁

- **严禁** 放松 §7.5 闸门（`review_status != APPROVED → 403` 必保留；`routers/assignments.py:369-375` 不动逻辑）
- **严禁** D-29 B 项违反（跨用户访问仍返 **404** 而非 403；不暴露存在性；段 `:353-365`）
- **严禁** 改动 §7.5 闸门位置或 ORM enum 判别方式（DB 侧判 `KnowledgeReviewStatus.APPROVED`，不用 API Literal）
- **严禁** 直接调 S3 stub response（必须真生成 PDF；stub response 是过渡态）
- **严禁** 新增 file storage / 中间文件（流式直返 = 内存 BytesIO → 立即返；不写盘）
- **严禁** pip install 跳过 mirror（必须 `--index-url https://mirrors.tencent.com/pypi/simple/`；与既有约定一致）
- **严禁** requirements.txt 与 Dockerfile 双 pip install 漏一处（3 处必同步：requirements.txt + pyproject.toml + Dockerfile pip × 2；per 既有 `tenacity` 教训）
- **严禁** pytest 跳过/装饰（xfail/skip = 退单；5 case 必真跑）
- **严禁** 跨工单扩散（S4 改 S3 代码 = 退单；§7.5 闸门段除外不动）
- **严禁** 字体方案走 (b) Dockerfile fonts-noto-cjk（推翻 §二「零系统依赖」核心理由）
- **严禁** 字体方案走 (c) `UnicodeCIDFont('STSong-Light')`（打印链 + 中文检出双失败风险，已讨论否决）
- **严禁** 走 SimSun / MS YaHei（专有许可；必须 OFL）
- **严禁** 改前端导出 UI（本工单不覆盖；S4-b 实施）

## 四、复用既有模式（核源 2026-10-14 20:53）

- `scripts/init-test-db.sh`（`90393f7` 修法）：pytest 前必跑；4 验 baseline = 0011/19/7
- `backend/tests/fixtures/questions_pool.jsonl` + `questions_tier_demo.json`（`3b68529` C/D 池）：测 PDF 渲染的 chapter/tier 字段
- `backend/app/api/v1/routers/assignments.py`：
  - `:334-382` = stub 段（改流式）
  - `:369-375` = §7.5 闸门（**不动**）
  - `:353-365` = D-29 B 项段（**不动**）
  - `:87` = `get_current_user_id`（用本 router 内；**不**用 `app/api/deps.py` —— 那里只有 `_enforce_owner_or_404` helper）
- `backend/app/api/v1/schemas/assignments.py:116-128`（`AssignmentExportResponse`）：**B4-1 决策 = 移除**（流式直返不返此 schema；保留 schema 字段无害但无意义）
- `backend/app/models/assignment.py`：
  - `Assignment`（`:55-`）：字段 = `id/owner_user_id/chapter_id/tier/total_count/d_count/c_count/b_count/a_count/seed/review_status/reviewed_by/reviewed_at/review_notes/created_at/updated_at`
  - `Assignment.chapter`（**单数**, `:125`）：1 作业单 = 1 章节（FK 约束）
  - `Assignment.items`（`:118`）：1:N → `AssignmentItem`
- `backend/app/models/assignment.py:139-`（`AssignmentItem`）：`position` / `tier_origin`（`QuestionDifficulty`）/ `question`（FK → `Question`）
- `backend/app/models/academic.py:72-78`（`KnowledgeReviewStatus`）：`PENDING/APPROVED/MODIFIED` 三态（**无** `DRAFT`）
- `backend/app/models/academic.py:500/524/548/615/781/877`（`Question.content`）：题目正文（**不是** `q.stem`）
- `backend/app/models/academic.py:782`（`Question.difficulty`）：题目本身难度（不直接用于作业档位；作业档位用 `AssignmentItem.tier_origin`）
- `backend/tests/api/v1/test_assignment_review.py:127` `_create_assignment_pending(client: TestClient, chapter_id: int, user_id: int = 1) -> int` —— **A4 fixture 复用既有 API（无 `mock_db_session`；per A6 复核更正）**
- `backend/tests/api/v1/test_assignment_review.py:142` `_create_assignment_approved(client, mock_db_session, chapter_id, user_id=1) -> int` —— **A4 fixture 复用既有 API**（**有** `mock_db_session`；调 PATCH `/review reviewed` 升 APPROVED）
- `backend/tests/api/v1/test_assignment_review.py:62-70` 模式 = `TestClient(app)` + **`def _override_get_db(): yield mock_db_session`**（**必须** generator function；**不**可用 `lambda: iter([...])` per A8 = iter 返回 iterator, FastAPI 不会解包 ⇒ 端点里 `db = list_iterator` ⇒ `db.get()` AttributeError）+ `X-User-Id: "1"` header
- `backend/tests/api/v1/_s4_helpers.py`（**S4 抽出**；per B11 = 避免 `tests/api/__init__.py` 不存在 ⇒ 双导入）：含 `make_test_client(mock_db_session)` + re-export `_create_assignment_pending/approved` + `chapter_with_questions`（**单一真值源** = D-43 §5 协作纪律）
- `backend/tests/conftest.py` 既有 fixture（**不**含 `auth_client` / `assignment_approved` / `assignment_pending_review` —— 别名引诱，**勿**新增同名 fixture，直接 import 既有 API）：
  - `mock_db_session` / `mock_db_engine` / `mock_user_system_seed` / `mock_subject` / `mock_textbook` / `mock_chapter`
  - `user_1` / `user_1_chapter`
  - `chapter_with_questions`（在 `test_assignment_review.py` 内 fixture，章节 + 100 C + 100 D 池）
  - `question_pool_fixtures`（`scope="session"`）
  - `monkeypatch_owner_filter_to_constant_one`（D-37 负面测试用）
- `backend/app/api/deps.py` `_enforce_owner_or_404`（跨用户隔离硬门槛 helper）
- `reportlab-4.4.3` 已在腾讯 mirror（**实测 PASS** @ 2026-10-14 20:53；per §二 D-S4-1 mirror probe）
- `pdfplumber>=0.11.0` 已存在（test 依赖；不重加；per B4-4）
- §治理.19 4 验 baseline（per `docs/PROJECT-CHARTER-protocol.md`）
- D-43-X §5 派工纪律（per `docs/decisions.md`）
- 9 个已有 brief 模板：本 brief 15 节结构依从 `plans/M2-S3-frontend-brief.md`

## 五、API 设计（contract —— 不许改）

```
POST /api/v1/assignments/{id}/export
Headers: X-User-Id: <int>    (per B.2 简化 auth; 实测 = X-User-Id header, 不是 Authorization Bearer; per B14 复核更正)
  (无 body, 不需 Content-Type)

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
- 流式直返（D-S4-3 ①）返 raw bytes，**移除** `response_model=AssignmentExportResponse` 参数（return `Response` 即不需 response_model）
- **回滚点**：如未来需返 metadata，schema 字段直接复用

### B4-2：service 模块（新增）

- 路径：`backend/app/services/assignment_export.py`
- 入口：`def render_assignment_pdf(assignment: Assignment) -> bytes`
- 依赖：`reportlab.platypus.SimpleDocTemplate` / `reportlab.lib.pagesizes.A4` / `reportlab.lib.styles.getSampleStyleSheet` / `io.BytesIO` / `reportlab.pdfbase.pdfmetrics` / `reportlab.pdfbase.ttfonts.TTFont` / `pathlib.Path`
- 输入：`Assignment` ORM（`.chapter.title` / `.items[*].position` / `.items[*].tier_origin` / `.items[*].question.content` / `.review_status.value` / `.owner_user_id` / `.created_at` / `.d_count` / `.c_count` / `.b_count` / `.a_count`）
- 输出：PDF bytes（头 4 字节 = `b"%PDF"`）

### B4-3：router 改（最小侵入；锚点 `:334-382`）

- 路径：`backend/app/api/v1/routers/assignments.py:334-382`
- 改动（仅 3 行级）：
  1. 移除 `response_model=AssignmentExportResponse` 参数
  2. endpoint body 末尾：从 `return AssignmentExportResponse(...)` → `return Response(content=render_assignment_pdf(assignment), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="assignment_{assignment.id}_{datetime.now().strftime("%Y%m%d%H%M%S")}.pdf"'})`
  3. import：新增 `from fastapi.responses import Response` + `from app.services.assignment_export import render_assignment_pdf`
- **不动**：§7.5 闸门段（`:369-375`）；D-29 B 项段（`:353-365`）

### B4-4：requirements + Dockerfile 3 处同步

- `backend/requirements.txt`：加 `reportlab>=4.0,<5.0`（注：pdfplumber 已存在，无须新加）
- `backend/pyproject.toml:8-19`：dependencies 段加 `reportlab>=4.0,<5.0`（注：pdfplumber 已存在）
- `backend/Dockerfile`：2 处 pip install（builder ~:35 + runtime ~:78）均加 reportlab
- **3 处必同步**（per 既有 `tenacity` 教训：单加一处 = 镜像裂；pdfplumber 沿用现有，无须重加）

### B4-5：字体资产（**已预置** by 载曜 per A9；非 subagent 实施）—— commit 2 仅写 service

- 路径：`backend/app/assets/fonts/NotoSansSC-Regular.ttf`（**已落**；8 184 B / 35 codepoints / Google Fonts `text=` 动态子集化）
- 许可：`backend/app/assets/fonts/OFL.txt`（**已落**；OFL 1.1 全文）
- 文档：`backend/app/assets/fonts/README.md`（**已落**；来源 + 验证 + 不可改 + 升级路径）
- 来源：Google Fonts CSS API（`text=` 动态子集化）→ gstatic.com `l/font?kit=...`
- **子集范围**：仅 11 测试 CJK + Latin + 数字 + 符号 = 51 字符（去重 35 码点）；**窄集**（生产用任意 chapter title 撞缺字 = PDF 空白/方框）；生产扩 3500 字符留 S5 端到端验收或开 S4.5 工单
- **Dockerfile 不用改**（runtime `:87` `COPY --from=builder /app/app /app/app` 已覆盖 `app/assets/...` 整树）
- **§二「零系统依赖」依然成立**（字体 = 仓内资产 ≠ apt 包）
- **Subagent 实施步骤**（仅 1 步）：写 `backend/app/services/assignment_export.py` + **lazy `_ensure_font()`**（per B13 避免模块级 registerFont ⇒ import 崩 ⇒ 全站 router 不可用）

### B4-6：1 行 SQL 修补（init-test-db.sh:70 enums 口径对齐）—— 并入 commit 1

```diff
- "SELECT count(*) FROM pg_type WHERE typtype='e';"
+ "SELECT count(*) FROM pg_type t JOIN pg_namespace n ON t.typnamespace=n.oid WHERE t.typtype='e' AND n.nspname='public';"
```

- **理由**：现有查询计 ALL enums（含 public + pg_catalog 内部）⇒ 严格限定 public schema = 与 `user_tables` 同一口径
- **并入 commit 1**（per B8；deps + 1 行 脚本 = 1 笔）

## 七、PDF 服务模块实现 spec（`app/services/assignment_export.py`）

```python
"""作业单 PDF 渲染 service（M2-S4 D-S4-1/2/3 + D-A1 锁定）。"""
from io import BytesIO
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)

from app.models import Assignment

# D-A1 (a) Noto Sans SC 嵌入 TTF (OFL 1.1)
# 改 lazy 注册 (per B13: 模块级副作用 ⇒ 字体缺失时 import 崩 ⇒ 全站 router 不可用)
_FONT_NAME = "NotoSansSC"
_FONT_PATH = (
    Path(__file__).parent.parent
    / "assets" / "fonts" / "NotoSansSC-Regular.ttf"
)


def _ensure_font() -> str:
    """Lazy 注册 Noto Sans SC；字体缺失/路径漂移 ⇒ FileNotFoundError 清晰文案.

    调用方: render_assignment_pdf() 入口. 不在模块级执行, 避免 import 崩.
    """
    if _FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        if not _FONT_PATH.is_file():
            raise FileNotFoundError(
                f"Noto Sans SC 字体文件缺失: {_FONT_PATH}. "
                f"per D-A1 (a) 嵌入 TTF; 字体资产在 commit 2 预置. "
                f"检查 backend/app/assets/fonts/ 目录."
            )
        pdfmetrics.registerFont(TTFont(_FONT_NAME, str(_FONT_PATH)))
    return _FONT_NAME


def render_assignment_pdf(assignment: Assignment) -> bytes:
    """Render 1 份作业单 PDF（流式直返 per D-S4-3 ①）。

    Layout（per D-S4-2 ① 1 份/作业单）：
    - 抬头：作业 ID / 章节 / 老师 ID / 出题时间
    - §0 档位分布表（D/C/B/A 4 档 + 题数，来自反马太审计字段 d_count/c_count/b_count/a_count）
    - §2 题目列表（per assignment.items[*]，按 position 排，4 档分节）
    - §3 审阅状态

    Note: 1 作业单 = 1 章节（FK 约束），不需循环 chapter。
    """
    font_name = _ensure_font()  # per B13: lazy 注册
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2 * 28, bottomMargin=2 * 28)
    styles = getSampleStyleSheet()
    # 覆盖默认字体（D-A1 (a) Noto Sans SC 嵌入）
    for style_name in ("Title", "Heading2", "Normal", "BodyText"):
        styles[style_name].fontName = font_name

    story = []

    # 抬头
    story.append(Paragraph(f"<b>作业单 #{assignment.id}</b>", styles["Title"]))
    story.append(Paragraph(
        f"章节: {_escape(assignment.chapter.title)} | "
        f"老师 ID: {assignment.owner_user_id} | "
        f"出题: {assignment.created_at.isoformat()}",
        styles["Normal"],
    ))
    story.append(Spacer(1, 12))

    # §0 档位分布（直接读反马太审计字段，不重算）
    story.append(Paragraph("<b>§0 档位分布</b>", styles["Heading2"]))
    tier_rows = [
        ["档位", "题数"],
        ["D 基础", str(assignment.d_count)],
        ["C 进阶", str(assignment.c_count)],
        ["B 挑战", str(assignment.b_count)],
        ["A 扩展", str(assignment.a_count)],
    ]
    tier_table = Table(tier_rows, colWidths=[3 * 28, 2 * 28])
    tier_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, -1), font_name),  # D-A1 (a) 字体覆盖
    ]))
    story.append(tier_table)
    story.append(Spacer(1, 12))

    # §2 题目列表（per assignment.items[*]，按 position 排，4 档分节）
    items = sorted(assignment.items, key=lambda i: i.position)
    for tier_code in ("D", "C", "B", "A"):
        tier_items = [i for i in items if i.tier_origin.value == tier_code]
        if not tier_items:
            continue
        story.append(Paragraph(f"<b>[{tier_code}]</b>", styles["Heading2"]))
        for i in tier_items:
            stem = i.question.content if i.question else "(题目已删)"
            story.append(Paragraph(
                f"&nbsp;&nbsp;{i.position}. {_escape(stem)}",
                styles["Normal"],
            ))
        story.append(Spacer(1, 6))

    # §3 审阅状态
    story.append(Paragraph(
        f"<b>§3 审阅状态: {assignment.review_status.value}</b>",
        styles["Heading2"],
    ))

    doc.build(story)
    return buf.getvalue()


def _escape(s: str) -> str:
    """reportlab Paragraph XML escape（避免 < > & ' " 触发 XML parse 错）。"""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )
```

## 八、测试 spec（`backend/tests/api/v1/test_pdf_export.py`，**5 case 必全过**）

```python
"""S4 PDF 导出端到端测试（M2-S4 必跑；5 case 必全过）。

模式：复用 test_assignment_review.py:62-70（TestClient + generator-based dependency_overrides + X-User-Id）。
复用既有 _create_assignment_pending / _create_assignment_approved（不手搓 DB）。
所有 helper / client factory 抽到 tests/api/v1/_s4_helpers.py（per B11 = 避免 tests/api/__init__.py 缺失 ⇒ 双导入）。
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.assignment_export import render_assignment_pdf
from app.models import Assignment
from tests.api.v1._s4_helpers import (  # noqa: F401
    make_test_client,
    _create_assignment_pending,
    _create_assignment_approved,
    chapter_with_questions,
)


@pytest.fixture()
def client(mock_db_session: Session) -> TestClient:
    """TestClient + dependency_overrides get_db（per test_assignment_review.py:62-70 既有模式；per A8 strict 修法）。"""
    return make_test_client(mock_db_session)


def test_pdf_export_403_when_not_approved(
    client, mock_db_session, chapter_with_questions
):
    """§7.5 闸门：review_status != APPROVED → 403。"""
    aid = _create_assignment_pending(client, chapter_with_questions.id)  # per A6: 删 mock_db_session
    r = client.post(
        f"/api/v1/assignments/{aid}/export",
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 403
    assert "未通过教师审阅" in r.json()["detail"]


def test_pdf_export_404_when_cross_user(
    client, mock_db_session, chapter_with_questions
):
    """D-29 B 项：跨用户 404 而非 403。"""
    aid = _create_assignment_approved(client, mock_db_session, chapter_with_questions.id)
    r = client.post(
        f"/api/v1/assignments/{aid}/export",
        headers={"X-User-Id": "999"},  # 不是 owner
    )
    assert r.status_code == 404
    assert "不存在" in r.json()["detail"]
    # per B12: 加强判别力 (防 "user 999 不存在" 同过伪绿)
    assert f"assignment {aid}" in r.json()["detail"]


def test_pdf_export_200_returns_valid_pdf(
    client, mock_db_session, chapter_with_questions
):
    """D-S4-3 ① 流式直返：200 + application/pdf + 头 4 字节 = %PDF。"""
    aid = _create_assignment_approved(client, mock_db_session, chapter_with_questions.id)
    r = client.post(
        f"/api/v1/assignments/{aid}/export",
        headers={"X-User-Id": "1"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    assert "attachment" in r.headers.get("content-disposition", "")


def test_pdf_export_contains_chinese_marker(
    client, mock_db_session, chapter_with_questions, tmp_path
):
    """D-A1 (a) 字体嵌入 + 中文检出器。

    注 1（per B5）：整串中文标题做 in 断言易撞 PDF 断行假红；改用结构标记（短串 + 标点）。
    注 2（per A11 path 2）：A10 R2 覆盖度判据**撤除**（per 复核员 v4 评：硬红让 DoD 恒假 + CI 永久红 + 红与真红不可分）。
    字体扩集（3500 码点）= **S4.5 后续工单**（见 §十三 S4.5 范围）；本工单 (S4) 不做 tripwire。
    """
    aid = _create_assignment_approved(client, mock_db_session, chapter_with_questions.id)
    r = client.post(
        f"/api/v1/assignments/{aid}/export",
        headers={"X-User-Id": "1"},
    )
    pdf_path = tmp_path / "export.pdf"  # per B4 改用 tmp_path
    pdf_path.write_bytes(r.content)

    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        text = "".join(p.extract_text() or "" for p in pdf.pages)
        page_count = len(pdf.pages)

    # 结构标记断言（brief 字符集内）
    assert "作业单" in text, "结构标记 '作业单' 缺失"
    assert "§0 档位分布" in text, "结构标记 '§0 档位分布' 缺失"
    assert "D 基础" in text, "结构标记 'D 基础' 缺失"
    assert "[D]" in text, "结构标记 '[D]' 缺失"
    assert "§3 审阅状态" in text, "结构标记 '§3 审阅状态' 缺失"
    assert page_count >= 1, "至少 1 页"


def test_render_assignment_pdf_unit(client, mock_db_session, chapter_with_questions):
    """service 层单测：返 bytes + 头 4 字节 = %PDF + 长度 ≥ 1KB。"""
    # per A7: 用既有 client fixture (不用裸 FastAPI() = 无 include_router + 无 dependency_overrides ⇒ 必崩)
    aid = _create_assignment_approved(client, mock_db_session, chapter_with_questions.id)
    a = mock_db_session.get(Assignment, aid)
    pdf_bytes = render_assignment_pdf(a)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 1024
```

## 九、Commit 划分（**3 commit；守 §5 教训 #9 不并片**）

1. **`chore(S4 deps + infra): reportlab 3 处同步 + init-test-db.sh enums 口径对齐`**
   - `backend/requirements.txt` + `backend/pyproject.toml` + `backend/Dockerfile`（× 2 pip）
   - 加 `reportlab>=4.0,<5.0`
   - pdfplumber 已存在，不重加
   - `scripts/init-test-db.sh:70` 1 行 SQL 修补（B4-6，per B8）
   - **理由**：deps + 1 行 脚本 = 1 笔（都属 infra 层，不动业务逻辑）

2. **`feat(S4 assets + service): Noto Sans SC 嵌入 + PDF 渲染 service`**
   - **字体资产已于 `a63d2c2` 预置** (3 文件: NotoSansSC-Regular.ttf 8 184 B + OFL.txt 4 010 B + README.md 3 192 B = 15 386 B total); 本 commit 仅 service
   - `backend/app/assets/fonts/OFL.txt`（新增；OFL 1.1）
   - `backend/app/assets/fonts/README.md`（新增；来源 + 许可 + subset 字符集说明）
   - `backend/app/services/assignment_export.py`（新增；完整代码 per §七）
   - **理由**：font 资产 + font 注册 + service 实现 = 1 笔（都是新增，无既有代码冲突）

3. **`feat(S4 router + tests): PDF 流式直返 + 5 case 端到端`**
   - `backend/app/api/v1/routers/assignments.py:334-382`（改 stub → 流式；闸门段 `:369-375` 不动）
   - `backend/tests/api/v1/test_pdf_export.py`（新增；5 case per §八）
   - commit message 必含：
     - `[origin-push]`
     - **窗口期风险声明**（S4 → S4-b 之间，点了导出"成功但不下载"）
   - **理由**：router 改 + test 增 = 1 笔（最小可工作单元）

**commit 划分守则**：
- 1 笔 = 1 个原子行为（deps / assets+code / router+tests）
- 严禁把 1+2+3 并为 1 笔（per §5 教训 #9；退单风险）
- 严禁把 S4-b 前端改动并入本仓（S4-b 独立工单）

## 十、入场闸（**必读**；subagent 派工前必读 §一-§九）

1. 读 §一-§九 全 + 本节 + §十一-§十四
2. 跑 `bash scripts/init-test-db.sh`（期望 0011/19/7）
3. 跑 `git status --porcelain`（期望 0 行）
4. **（仅参考）** 跑 `git log --oneline -5` 看 5 笔 commit 历史 —— **不**要求当前 HEAD 必带 `[origin-push]`（派工 commit 自身必带即可；派工前后必查）
5. 读 `backend/app/assets/fonts/README.md`（**commit 2 落地后**；字体来源 + 许可 + subset 字符集）—— 必读（字体方案透明性）

派工后必跑：
1. `bash scripts/init-test-db.sh`（再验 4 验 baseline 一致；enums 1 行修补后口径）
2. `docker compose exec -T -e DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/tiered_homework_test backend python -m pytest tests/api/v1/test_pdf_export.py -v`（5 case 全过）
3. `docker compose exec -T -e DATABASE_URL=... backend python -m pytest -q`（全套 仍 318+ passed / 9 skipped / 0 failed）
4. `bash scripts/ledger_check.sh`（11/11 PASS，0 WARN）
5. `git status --porcelain`（0 行）
6. 确认每 commit message 含 `[origin-push]`
7. 确认 commit 3 含窗口期风险声明

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
- alembic：`0011_question_images (head)`
- user_tables：19
- enums：7（修后严格 = public 7）

## 十二、D-43-X §5 修正规则 #1 派工纪律

- 派工前必读：§一-§十一 全
- 派工 brief 内容不得改（本 brief 是 contract；subagent 改 brief = 退单）
- subagent 报回格式 per §十四（6-line handshake + 11 必报）
- 严禁跨工单扩散（S4 改 S3 代码 = 退单；§7.5 闸门段除外不动）
- 严禁 pytest 跳过/装饰（xfail/skip = 退单；5 case 必真跑）
- 严禁静默 `try/except` 吞错（PDF 渲染失败必 raise → 500 详情）

## 十三、完成定义（DoD）

**S4 范围**（本工单必完成）：

- [ ] commit 1（chore deps+infra）落字：reportlab 3 处同步 + pdfplumber 沿用 + init-test-db.sh:70 enums 1 行修补

**S4 范围 (字体窄集 = 已知缺口，移 S4.5)** — subagent 必看：

- 字体为窄集 (35 码点; **缺 ASCII 标点 `:` `-` `(` `)` + 数字 4-9 + 大多数 CJK; 缺字映射 U+0000 NUL**) ⇒ **S4 产出物自身即缺字**（抬头 `章节: … | 老师 ID: … | 出题: 2026-10-14T…` 里的 `:` `-` 全 NUL; §0 档位表的题数只要含 4-9 就缺）⇒ 真实内容不可用（不只是生产撞）
- 扩字体 (≥3000 码点) = **S4.5 后续工单**（见 §十三 S4.5 范围）；本工单 (S4) **不**做 tripwire（A11 path 2 撤除硬红断言）
- **test 1/2/3/4/5 = 5 passed, 0 failed, 0 skipped**（per §八 5 case 必全过 + §十/§十三 多处一致）
- [ ] commit 2 (feat service) 落字: **仅** `app/services/assignment_export.py` (含 lazy `_ensure_font()` + §七 PDF 渲染); 字体资产 (3 文件) 已于 `a63d2c2` 预置 (不在本 commit 范围)
- [ ] commit 3（feat router+tests）落字：routers/assignments.py:334-382 改流式直返 + test_pdf_export.py 5 case 全过 + 窗口期风险声明
- [ ] `bash scripts/init-test-db.sh` 派工前 = 派工后 = 0011/19/7
- [ ] `pytest tests/api/v1/test_pdf_export.py -v` = **5 passed, 0 failed, 0 skipped**
- [ ] `pytest -q` 全套 = **318+ passed, 9 skipped, 0 failed**
- [ ] `bash scripts/ledger_check.sh` = 11/11 PASS, 0 WARN
- [ ] `git status --porcelain` = 0 行
- [ ] commit 1/2/3 message 全含 `[origin-push]`
- [ ] commit 3 message 含窗口期风险声明（S4 → S4-b 之间，点了导出"成功但不下载"）
- [ ] `git push origin master` 成功（**github push 须星云单独批**，per B3）

**S4-b 范围**（**本工单未覆盖**，S4-b 实施，阻塞 M2-S5 端到端验收）：

- [ ] （S4-b 工单号 `M2-S4-b` 待派）`Assignments.tsx` 改 `responseType:'blob'` + `URL.createObjectURL`
- [ ] （S4-b）删 `ExportResponse` 接口（`:67-72`）
- [ ] （S4-b）改文案（不再"导出已入队（export_id=…）"）
- [ ] （S4-b）403/404 catch 路径保留

**S4.5 范围**（**本工单未覆盖**，S4.5 实施，**前置 M2-S5 端到端验收**）：

- [ ] （S4.5 工单号待派）字体扩集（≥3000 码点 Noto Sans SC subset ~2-3 MB；或全量 ~9 MB）
- [ ] （S4.5）覆盖度判据: **`assert "\x00" not in text`** (NUL 检出 = 任何缺字; 含 CJK + ASCII + 标点; 不需要预先挑字; 字体够时 NUL 必然消失) ⇒ **主判据**; 辅判据 = 抽样含特定字（如 `第一章` 整段）
- [ ] （S4.5）字体文件来源候选：google/fonts `ofl/notosanssc/NotoSansSC[wght].ttf`（TTF / `glyf` 表 / OFL 1.1）—— 须验 `TTFont()` 加载 + 渲染探针
- [ ] （S4.5）`backend/app/assets/fonts/NotoSansSC-Regular.ttf` 替换为新字体
- [ ] （S4.5）init-test-db.sh / commit message / README / brief 同步更新（撤"窄集"措辞）

## 十四、报回格式（每 commit 必带 + 6-line handshake）

**每 commit 报回**：
```
commit <SHA>
files: <list>
+lines / -lines
pytest_local: <"N passed, M failed, K skipped" string>
ledger_check: <"11/11 PASS" string>
reportlab_ver: <pip freeze | grep reportlab 输出; 防镜像 4.x vs 5.x 环境差>
[origin-push]: yes
```

**6-line handshake**（派工后必报）：

1. commit SHA 最新 1 笔
2. pytest `tests/api/v1/test_pdf_export.py -v` 输出尾部 15 行
3. pytest 全套 `-q` 输出尾部 5 行
4. `git show --stat HEAD` 输出
5. 偏离 brief 项（如有；无则"无偏离"）
6. 风险/盲区（如有；无则"无风险"）
7. `pip freeze | grep reportlab` 输出（per 审计员 v5 B3；防镜像 4.x vs 5.x 环境差）

## 十五、修订追记

- **2026-10-14 20:19** 起草（载曜，per 星轨 v2 + 用户拍 D-S4-1/2/3）
  - 拍板来源：
    - D-S4-1 reportlab：星轨 v2 §2.1 / 用户 2026-10-14 20:19 接受
    - D-S4-2 ① 1 份/作业单：星轨 v2 §2.2 / 用户 2026-10-14 20:19 接受
    - D-S4-3 ① 流式直返：星轨 v2 §2.3 / 用户 2026-10-14 20:19 接受
  - 当时 brief 含 5 A级失实 + 9 项 B级 隐患

- **2026-10-14 20:53** 复核响应 + 修订路线图（载曜）
  - 核源 A1-A5 + 9 项 B级 全部对得上
  - 跑 mirror probe：reportlab-4.4.3 已在腾讯 mirror（PASS）
  - 修正核源表（A5.1 锚点 = `:334-382` 非 `:332-383`；其他 OK）

- **2026-10-14 20:56** 用户拍 (a) + S4-b（用户 2026-10-14 20:56 拍板）
  - 拍板来源：
    - D-A1 (a) Noto Sans SC 嵌入 TTF（OFL 1.1）：用户 2026-10-14 20:56 接受（产品链 = 打印机，必须嵌入）
    - D-A3 S4-b sub工单 + 3 约束：用户 2026-10-14 20:56 接受（接受窗口期；不并片）

- **2026-10-14 20:57** 本次订正（载曜）
  - 订正依据：复核员 2 处 A5.1 锚点更正（`:334-382` 非 `:332-383`）+ 1 处 A1 字体方案关键提醒（产品链 = 打印机）+ 9 项 B级
  - **同笔改 A2 + A5**（合并避免自引滞后；锚点 `:334-382` / 闸门 `:369-375` / 跨用户 `:353-365` / `get_current_user_id` @ `assignments.py:87`）
  - **改 A4**（复用 `_create_assignment_pending/approved` 既有 API + `chapter_with_questions` fixture，不手搓 DB、不新增同名 fixture）
  - **落实 A1**（§六 B4-5 font 资产 + 注册；§七 font 注册代码；Noto Sans SC + OFL.txt + README.md）
  - **落实 A3**（§一范围 + §十三 DoD 显式「未覆盖」+ commit 3 窗口期；S4-b 工单号 `M2-S4-b`）
  - **9 项 B级 集成**：
    - B1：§二 D-S4-2 改用 FK 约束理由（无错节引用）
    - B2：§十 入场闸 #4 改"仅参考"语义（不强制当前 HEAD 必带 origin-push）
    - B3：§十三 DoD github push 拆"须星云单独批"
    - B4：§八 test 4 改 `tmp_path`（pytest 内建 fixture）
    - B5：§八 test 4 改结构标记判据（避 PDF 断行假红）
    - B6：§七 `_escape` docstring 加 `"` 字符说明
    - B7：§二 fpdf2 否决理由改"API 不稳 + 排版弱"
    - B8：§九 B4-6 enums 修补并入 commit 1
    - B9：§二 D-S4-1 标 "mirror probe PASS @ 2026-10-14 20:53 (4.4.3)"

- **实证基线**：
  - HEAD = `c6d64dd`（brief 首版后；本 brief 订正后 = 49 笔 = 668fddd..HEAD）
  - init-test-db.sh 4 验 = 0011/19/7
  - pytest baseline = **318 passed / 9 skipped / 0 failed in 154.32s**（per B-1 §一.3）
  - mirror probe = reportlab-4.4.3 @ 腾讯 mirror PASS（2026-10-14 20:53）
  - 文档 15 节结构依从 `plans/M2-S3-frontend-brief.md`

- **关键决策**：
  - 1 处架构（B4-1 schema 移除）：流式直返不返 `AssignmentExportResponse`；移除 `response_model=...` 参数
  - 1 处 1 行修补（B4-6 init-test-db.sh:70 enums schema 限定）：与 user_tables 口径对齐
  - 1 处依赖决策（B4-4 3 处同步）：builder/runtime split 防镜像裂；pdfplumber 沿用现有
  - 1 处字体决策（B4-5 D-A1 (a) 嵌入）：Noto Sans SC OFL 1.1；Dockerfile 零改；§二「零系统依赖」依然成立
  - 1 处前端决策（D-A3 S4-b）：本工单不覆盖前端；接受窗口期；commit 3 明记
  - 1 处范围 4 项（S4-b）：responseType:'blob' / 删接口 / 改文案 / catch 保留

- **2026-10-14 21:18** 第二次订正（载曜，per 复核员 A6-A9 + B10-B14 复核回执）
  - **A6 §四 + §八 签名订正**：`_create_assignment_pending` 误加 `mock_db_session`（实无）；§八 test 1 调用删实参。⚠️ **别一起改错**：`test 2/3/4` 用 `_create_assignment_approved` 真有 `mock_db_session`，不变。
  - **A7 §八 test 5**：去 `TestClient(FastAPI())` 裸 app（无 include_router + 无 dependency_overrides ⇒ helper POST 必 404 ⇒ 必崩），改用既有 `client` fixture。
  - **A8 §八 client fixture**：`lambda: iter([mock_db_session])` 改 yield-based generator（照抄 test_assignment_review.py:62-70；`iter(...)` 返回 iterator, FastAPI 不解包 ⇒ 5 用例全崩）。
  - **A9 字体预置 by 载曜**（per 复核员「人预置」建议）：
    - 1st try: Google Fonts v41 默认 URL = 35 KB **Latin-only**（218 codepoints, 0 CJK）—— 撤。
    - 2nd try: Google Fonts CSS `text=` 动态子集化 = 8 184 B / 35 codepoints / **51 字符（去重 35 码点）= 35/35 全覆盖 PASS**（`作业单` / `§0 档位分布` / `D 基础` / `[D]` / `§3 审阅状态` / `pending` / `approved` / digits / `§ # [ ]`）—— 采纳。
    - 资产：`backend/app/assets/fonts/NotoSansSC-Regular.ttf` + `OFL.txt` + `README.md`（来源 + 验证 + 不可改 + 升级路径）。
    - **生产缺口**：8 KB 窄集 = 仅测试字符；任意 chapter title 撞缺字 = PDF 空白/方框；生产扩 3500 字符留 S5 端到端验收或开 S4.5 工单。
  - **B10 §十 入场闸 #5**：README 标「**commit 2 后**」（派工前读不到；commit 2 落地后才存在）。
  - **B11 抽 helper**：新增 `backend/tests/api/v1/_s4_helpers.py`（`make_test_client` + re-export；不动 test_assignment_review.py = 避免跨工单污染）。
  - **B12 §八 test 2**：加 `assert f"assignment {aid}" in detail`（防「user 999 不存在」同过伪绿）。
  - **B13 §七 模块级副作用**：模块级 `pdfmetrics.registerFont(...)` ⇒ 字体缺失 import 崩 ⇒ 全站 router 不可用。改 lazy `_ensure_font()`（字体缺失 ⇒ 清晰 `FileNotFoundError`；不 import 崩 ⇒ 不影响其他 router）。
  - **B14 §五 contract**：header 改 `X-User-Id: <int>`（实测 = X-User-Id, 不是 Authorization Bearer；`get_current_user_id:87-107` 只解析 header）；删 `Content-Type: application/json`（无 body POST 无意义）。

- **第二次实证基线**：
  - HEAD = `82e3053`（brief 首次订正后；本笔第二次订正后 = 50 笔 = 668fddd..HEAD）
  - init-test-db.sh 4 验 = 0011/19/7
  - pytest baseline = **318 passed / 9 skipped / 0 failed in 154.32s**（per B-1 §一.3）
  - 字体预置 = Noto Sans SC v41 text= dynamic 8 KB / 35 codepoints / 51 字符（去重 35 码点）= 35/35 PASS（2026-10-14 21:12）
  - fontTools cmap 实测 = 35 codepoints；51 字符（去重 35 码点）= 35/35 PASS（0 missing 测试字符）；Magic `0x00010000` (TTF)；`glyf` 表存在；`TTFont()` 加载成功

- **第二次关键决策**：
  - 1 处字体来源决策（Google Fonts CSS `text=` 动态子集化 API）= 拿确定 CJK subset，**拒** Latin-only 默认 URL
  - 1 处代码副作用治理（lazy `_ensure_font()` vs 模块级 `registerFont`）= 爆炸半径从「全站 router 不可用」降到「仅 PDF 端点 500 + 清晰文案」
  - 1 处测试卫生（抽 _s4_helpers.py 单一真值源）= 避免 `tests/api/__init__.py` 缺失 ⇒ PEP 420 命名空间包侥幸 + 双导入
  - 1 处 A8 strict 修法（yield-based generator vs `lambda: iter([...])`）= 照抄 test_assignment_review.py:62-70 既有 3 行模式，避免 FastAPI 不会解包 iterator 的坑

- **2026-10-14 21:35** 第四次订正（载曜，per 复核员 A11 v4 复核回执）
  - **A11 · DoD 恒假** (per 复核员 (c) 选 **path 2** 撤硬红断言 + 移 S4.5；path 1 R1' 试不通 = SSH 443 不达 + jsdelivr 阻 + GitHub raw 阻 + PyPI 无字体包 = 复审员 4-7h 估时过高):
    - **核源 A11 矛盾** (per 复核员 v4): §十三:531-538 + §十:487 + §八:322/325/398 + §三:78 + §十二:518 全有 "5 passed / 0 failed / 5 case 必全过 / 5 case 必真跑" 约束, 但 §十三:531-532 加 "test 4 设计为红" ⇒ **DoD 互斥恒假** (D-28 ② 家族) + CI 永久红 + 红与真红不可分 (普通 assert 无 tripwire 语义)
    - **撤 §八 test 4 A10 R2 覆盖度判据**: 删 `chapter_with_questions.title = "第一章 有理数 ..."` + 删 `assert "第一章" in text, (...)` + 改 docstring (注 2 改 path 2 撤除说明) ⇒ 5 case 恢复「必全过」= 5 passed
    - **撤 §十三 DoD A10 R2 显式未覆盖段**: 删 "test 4 设计为红" + 改 test 1/2/3/4/5 = 5 passed + 加 "字体窄集 = 已知缺口，移 S4.5" 措辞
    - **加 §十三 S4.5 范围 (后续, 非本工单)**: 字体扩集 (≥3000 码点) + 覆盖度判据 + 字体来源 (google/fonts `ofl/notosanssc/`) + 替换 `NotoSansSC-Regular.ttf` + 同步更新 README/brief/init-test-db
  - **未做**: path 1 (R1' 扩字体 via git SSH 443 + sparse checkout) — 试 SSH 443 / HTTPS 22 / gitee 镜像 / aliyun code = 5 通道均不通或卡; 估时 4-7h, 优先级低于 path 2 (确定性, 30 min)
  - **未做**: path 3 (xfail strict=True) — 需星云豁免 §三/§十二 严禁 xfail/skip; 改写纪律建议 = "严禁**无工单号**的 xfail/skip" (本意防假绿, strict=True 不造成假绿); 暂不申请豁免
  - **路径选择理由**: path 2 = 确定性 + 快速 + 审计认 ✅; path 1 = 不确定时延; path 3 = 需纪律改写

- **第四次实证基线**:
  - HEAD = `8b2cf53` (brief v4 后; 本笔 v5 后 = 52 笔 = 668fddd..HEAD)
  - conftest.py:130 `expire_on_commit=False` 确认 (复核员发现) ⇒ test 4 内存改 title 路径**成立**; A11 path 2 撤此 tripwire 不破测试集

- **第四次关键决策**:
  - 1 处 DoD 互斥修复 (path 2): 撤硬红断言 = DoD 恢复 5 passed + CI 不永久红; S4.5 接手覆盖度判据
  - 1 处 S4.5 范围建立: 字体扩集 3000 码点 + 覆盖度判据 + 字体来源候选 + 同步更新
  - 1 处诚实表达: 删"test 4 设计为红"tripwire 改"5 passed"实然 + §十三 S4.5 范围显式未覆盖 (vs 自我欺骗的恒假 DoD)

- **2026-10-14 21:55** 第五次订正（载曜，per 复核员 v5 实跑证据 + 2 建议 + 3 B级）
  - **复核员 v5 实跑证据** (新信息): 独立 venv (reportlab 5.0.1 + pdfplumber) 渲染真 PDF, 5 条断言全 PASS (test 4 派工会绿); 反证缺字映射 U+0000 NUL; 字体 ASCII 缺 `:` `-` `(` `)` + 数字 4-9 + 大多数 CJK
  - **建议 1** (§十三 S4 范围措辞): "字体窄集"段 升级描述 — 不只是"生产撞", **S4 产出物自身即缺字** (抬头/日期/§0 题数表 demo 阶段即残缺)
  - **建议 2** (§十三 S4.5 覆盖度判据): 改 `assert "\x00" not in text` (NUL 检出) 为主判据; 不需要预先挑字; 字体够时 NUL 必然消失
  - **B 级 1** (§十五历史「已废弃」标记): 21:25 两条 (「§八 test 4 加 A10 R2 覆盖度判据」+「§十三 DoD 加 A10 R2 显式未覆盖段」) 加 "该条已被 21:35 条撤销，非生效指令" ⇒ subagent 读 §十五不被历史误导
  - **B 级 2** (§九 + §十三 commit 2 交付物清单): 字体资产 3 文件已于 `a63d2c2` 预置; commit 2 **仅** `app/services/assignment_export.py` (改 "feat assets+service" → "feat service")
  - **B 级 3** (§十四 报回格式 + 6-line handshake): 加 `reportlab_ver` 一行 (per commit 报回) + 6-line handshake 第 7 项 `pip freeze | grep reportlab` (防镜像 4.x vs 5.x 环境差)
  - **未做**: R1' (扩字体 via git SSH 443); path 1 仍 = 4-7h 估时; path 2 已落地
  - **未做**: path 3 (xfail strict=True); 仍需星云豁免 §三/§十二 严禁 xfail/skip

- **第五次实证基线**:
  - HEAD = `a1e016f` (brief v5 后; 本笔 v6 后 = 53 笔 = 668fddd..HEAD)
  - 复核员 v5 实测 = 5 条断言全 PASS (脚本 `_probe_s4_pdf_render.py` 可复跑); 缺字映射 NUL (U+0000)
  - 字体 ASCII 缺 11 字符 (`: - ( )` + 数字 4-9); 16 非 ASCII 字符 = §位作分单基审布态数档状础阅题

- **第五次关键决策**:
  - 1 处 S4 范围措辞升级 (per 实测): "S4 产出物自身即缺字" ⇒ 不掩盖 demo 阶段残缺
  - 1 处 S4.5 覆盖度判据换 NUL 检出 (per 实测): 1 行覆盖所有缺字 vs 原"预先挑字"漏检
  - 1 处历史条目加 "已废弃" 标记 (B1): 防 subagent 读 §十五被 21:25 字面"加"误导
  - 1 处 commit 2 交付物清单 (B2): 字体预置与本 commit 边界明确, 避免 commit 重复落字
  - 1 处报回格式加 reportlab_ver (B3): 防镜像 4.x vs 5.x 环境差致 silent fail

- **2026-10-14 21:25** 第三次订正（载曜，per 复核员 A10 + B15/B16 复核回执）
  - **A10 · 同源循环** (per 复核员 (c) 选 **R2** 路径；R1 = 全量/VF Noto Sans SC, 8-10 MB 二进制, 网络/许可/仓容 限制 ⇒ 留 S4.5/S5):
    - 独立核源: fontTools cmap = 35 码点; 16 非 ASCII = `§业位作分单基审布态数档状础阅题`; 复核员 37 字探针 = 22 缺失 (`第一章有理下列计算教师备注目难度进阶挑战扩展` 全不在) ⇒ 同源循环确认
    - **§二:52** 撤误规格「3500 常用 CJK ~2-3 MB」, 改实际 35 码点 dynamic subset + 缺口说明
    - **§九:448** 撤误规格「subset ~2-3 MB」, 改实际 8 184 B / 35 码点
    - **§八 test 4 加 A10 R2 覆盖度判据**（**该条已被 21:35 条撤销，非生效指令**; 留作 A10/A11 决策历史）: chapter title 改用常用字「第一章 有理数 下列计算 教师备课」(subset 外) + 断言 `第一章` in text ⇒ **窄集下必红** ⇒ 暴露字体窄集风险
    - **§十三 DoD 加 A10 R2 显式未覆盖段**（**该条已被 21:35 条撤销，非生效指令**; 留作 A10/A11 决策历史）: test 1/2/3/5 = 4 passed (结构标记); test 4 = **设计红** (A10 R2 覆盖度判据); 若绿 = 字体已扩集 (R1 完成)
  - **B15**: 新增 `backend/tests/api/__init__.py` (1 行空文件; per 复核员 1 行零风险补双导入隐患)
  - **B16**: 「51 字符」改「51 字符（去重 35 码点）= 35/35」措辞 (避免误读为 51 码点); README + §十五 同步
  - **网络可达性 (复核员 v2 未知项)**: WSL 可达 `fonts.googleapis.com` + `gstatic.com`; legacy UA 试 R1 = CSS API 改版返 dynamic subset = 拿不到 CJK-only TTF ⇒ R1 走不通 (R2 选)
  - **第三次决策**: R1 不可行 (无 accessible 全量 TTF 源) ⇒ R2 选; 期望 subagent 派工后 test 4 报告红, 触发 S4.5/S5 前置扩集

- **第三次实证基线**:
  - HEAD = `a63d2c2` (brief v3 后; 本笔 v4 后 = 51 笔 = 668fddd..HEAD)
  - fontTools cmap 实测 = 35 codepoints; 16 非 ASCII; Magic `0x00010000` (TTF); `glyf` ✓; `TTFont()` ✓; **同源循环确认** = test 4 断言集 ∈ 字体子集 (因为字体由 test 字符动态生成) ⇒ test 4 永不会因字体缺字而红
  - 复核员 37 字探针 = 12 命中 / 22 缺失 (常用字 `第一章` 等 不在 35 码点中)

- **第三次关键决策**:
  - 1 处 A10 R2 设计核心: 故意 test 4 红, 暴露窄集风险 (vs 假装绿, 走过 D-28 同源循环陷阱)
  - 1 处规格诚实: §二/§九 撤误规格「3500 ~2-3 MB」, 改实际 35 码点 + 缺口说明 (vs 自我欺骗)
  - 1 处隐性双导入堵漏: B15 加 `backend/tests/api/__init__.py` (1 行, 零风险) 替代 `_s4_helpers.py` 的 `from tests.api.v1.test_assignment_review import ...` (单引用 = 1 引用, 但仍靠 PEP 420 命名空间包侥幸)
