"""作业单 PDF 渲染 service（M2-S4 D-S4-1/2/3 + D-A1 锁定）。"""
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models import Assignment

# D-A1 (a) Noto Sans SC 嵌入 TTF (OFL 1.1)
# 改 lazy 注册 (per B13: 模块级副作用 ⇒ 字体缺失时 import 崩 ⇒ 全站 router 不可用)
_FONT_NAME = "NotoSansSC"
_FONT_PATH = (
    Path(__file__).parent.parent
    / "assets"
    / "fonts"
    / "NotoSansSC-Regular.ttf"
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
    """reportlab Paragraph XML escape（避免 < > & ' " 触发 XML parse 错; per B6）."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
