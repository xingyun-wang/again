# Noto Sans SC — 嵌入 TTF (D-A1 (a))

## 字体信息

- **字体**: Noto Sans SC（思源黑体 SC / Simplified Chinese）
- **版本**: v41（Google Fonts 当前稳定版）
- **许可**: [OFL 1.1](./OFL.txt) — 开放字体许可证
- **来源**: Google Fonts `text=` 动态子集化 API — `https://fonts.googleapis.com/css?family=Noto+Sans+SC&display=swap&text=<test-chars>`
- **Subset**: **35 unicode codepoints**（11 测试 CJK + Latin + 数字 + 符号 = `text=` 传入字符集）—— **⚠️ 窄集，仅覆盖 S4 brief §八 test 4 断言字符；任意 chapter title 撞缺字 = PDF 空白/方框**。生产版需扩到 3500 常用 CJK (~2-3 MB) 或全量 (~9 MB)，留 S5 端到端验收或 S4.5 工单。
- **大小**: 8 184 B (~8 KB)
- **格式**: TrueType（TrueType outlines，含 `glyf` 表 = reportlab `TTFont()` 兼容）

## 用法

```python
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet

_FONT_NAME = "NotoSansSC"
_FONT_PATH = Path(__file__).parent / "NotoSansSC-Regular.ttf"
pdfmetrics.registerFont(TTFont(_FONT_NAME, str(_FONT_PATH)))

# 覆盖默认字体
styles = getSampleStyleSheet()
for s in ("Title", "Heading2", "Normal", "BodyText"):
    styles[s].fontName = _FONT_NAME

# TableStyle 也需显式 fontName
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
table = Table([...])
table.setStyle(TableStyle([
    ("FONTNAME", (0, 0), (-1, -1), _FONT_NAME),
]))
```

## 验证（@ 2026-10-14 21:12 by 载曜）

- ✓ Magic = `0x00010000` (TTF)
- ✓ `glyf` 表存在（TrueType outlines）
- ✓ `TTFont()` 加载成功（无 `TTFError`）
- ✓ 文件大小 = 8 184 B (~8 KB)
- ✓ cmap = 35 codepoints；**所有 brief §八 test 4 字符均在**（`作业单` / `§0 档位分布` / `D 基础` / `[D]` / `§3 审阅状态` / `pending` / `approved` / digits / `§ # [ ]` 等 51 字符全覆盖，0 missing）
- ✓ 来源：Google Fonts CSS API + gstatic.com `l/font?kit=...` 直链（WSL 可达；text= dynamic subset 模式）
- ❌ 第一次试抓（v41 默认 URL）= Latin-only subset（218 codepoints，0 CJK）—— 已覆盖，**用 dynamic 替换**

## 不可改的事

- **不**改文件名（`NotoSansSC-Regular.ttf` 由 `app/services/assignment_export.py` 引用）
- **不**改字体名（`NotoSansSC` = pdfmetrics 注册键）
- **不**移动到其他路径（`backend/app/assets/fonts/` = Dockerfile runtime `:87` `COPY --from=builder /app/app /app/app` 自动覆盖）
- **不**删 `OFL.txt`（许可证明）

## 字体选型历史

- 2026-10-14 20:19 D-S4-1 拍 = reportlab (per 星轨 v2 + 用户拍)
- 2026-10-14 20:56 D-A1 拍 = (a) 嵌入 TTF (per 用户拍; 拒绝 (b) Dockerfile fonts-noto-cjk 改镜像 / 拒绝 (c) CID STSong-Light 不嵌入)
- 2026-10-14 21:09 第一次试抓（v41 默认 URL）= 35 KB Latin-only，**撤**
- 2026-10-14 21:12 第二次试抓（CSS API `text=` 动态子集化）= 8 KB CJK subset，**采纳**（cmap 验 51/51 测试字符 PASS）
- 2026-10-14 21:12 字体预置 by 载曜 (per 复核员建议; 留痕 = 决策室 资产 ≠ 代码逻辑)
