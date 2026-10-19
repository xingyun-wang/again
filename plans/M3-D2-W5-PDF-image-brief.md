# M3-D2 brief: W5 PDF 嵌图

> **派工人**：载曜｜**派工日**：2026-10-19｜**批准**：星云（"B1, B2, D2 可以起"）
> **阻塞**：无（与 0012 无关；A1+1 P3-3 已解锁 = 立即起；与 C1 不冲突）
> **回执 commit message 必带**：`[origin-push]`（WAKEUP 8 步授权机制）

---

## §1 任务

- 改 `backend/app/services/assignment_export.py` 让题目带图 = **真渲染图像**（不是只渲染 stem + choices）
  - 现有 PDF 渲染段 (103-117) 只看 `i.question.content` + `i.question.choices`；新增：看 `i.question.images` → render image
- **不装 Pillow**（用 reportlab 自带的 image support）
- **写测试** = 新建 `backend/tests/api/v1/test_pdf_export_with_image.py`（现有 `test_pdf_chapter_extraction` 是 PDF **解析**不是 **导出**）

## §2 4 法核源（必跑 + 必报）

| 项 | 文件 / 实际 | 4 法核源结果 |
|----|------|---------------|
| requirements.txt | `cat backend/requirements.txt` | 已有 `reportlab>=4.0,<5.0` + `pymupdf>=1.24.0` + `pdfplumber`；**没有 Pillow** — 决定**不装 Pillow**，用 reportlab 自带 |
| `question_images` model | `backend/app/models/academic.py:958` | model 已建（`__tablename__ = "question_images"`）|
| `question_images` API endpoint | `grep -rn "question_images" backend/app/api` | **核源必报**：找实际 endpoint 路径（model 已知，endpoint 待确认）|
| 现有 PDF 渲染段 | `backend/app/services/assignment_export.py:103-117` | 113 = `Paragraph(stem + position)`；115-117 = choices 渲染；**没有 image 渲染** = 新增 |
| 现有 PDF 测试 | `find backend/tests -name "test*pdf*"` | 现有 = `test_pdf_chapter_extraction.py`（解析） / `test_pdf_extractor.py`（解析）；**没有 export 端到端测试** = 新建 |
| Reportlab 嵌图 API | `reportlab.platypus.Image` / `reportlab.lib.utils.ImageReader` | 用 `platypus.Image`（更简洁；接受路径或 bytes）|

## §3 嵌图实现要点

- 在 `i.question.choices` 渲染段后 / 之前**插入** image 渲染段：
  ```python
  if i.question and i.question.images:
      for img in sorted(i.question.images, key=lambda x: x.order_index):
          img_bytes = ... # 从 endpoint 拿 bytes 或从 model 拿
          story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;", styles["Normal"]))
          story.append(Image(io.BytesIO(img_bytes), width=..., height=...))
  ```
- **图片大小**：默认宽 200pt（与 A4 等比缩放；具体值在 brief 拍）
- **位置**：题目 stem 之后、choices 之前
- **异常处理**：image 加载失败 = 渲染 fallback（题目 stem 后追加 "（图片加载失败）"）— **不静默**

## §4 必报项（per D-43-X = 对象级证据）

1. **CI run #**（ruff + mypy + pytest）+ commit SHA
2. **PDF 嵌图 API** = 哪个（`platypus.Image` / `graphics.Image` / 其他）
3. **装包 diff** = `requirements.txt` 改前 vs 改后（**预期不装新包** = 0 行 diff）
4. **改 PDF 导出服务的具体行号**（插入 / 修改）
5. **测试 = 带图题 PDF 的 pymupdf 验证**（**图像 XObject 计数 ≥ 1** per D-43-X = 对象级证据）
6. **pytest 跑测试库**全绿 + **不污染 dev 库**（per §治理.19）
7. **PDF 真值证据** = `pymupdf` 验证含图（**带图 vs 不带图对比**）+ PDF 文件大小
8. **git status + diff stat**（期望 2 文件：1 改 assignment_export.py + 1 新建 test_pdf_export_with_image.py）

## §5 派工回执必带（**不写 = 拒收**）

- commit SHA
- CI run #（ruff + mypy + pytest）
- pytest 输出（**测试库**，全绿，**显式 -e DATABASE_URL**）
- pymupdf 验证 PDF 含图像 XObject ≥ 1（**带图 vs 不带图对比**）
- `question_images` endpoint 实际路径（4 法核源必报项）
- 报告命令用 4 法核源（**不写"已支持"**）

## §6 同步说明（**不需要 subagent 做**）

- 与本 brief **独立**：
  - B1 (IA-1 导航) = 前端；本 brief = 后端 PDF
  - B2 (W1 ORDER BY) = 后端 ORDER BY；本 brief = 后端 PDF 嵌图
- A2 (0012 迁移) 排在 A1 批后；本 brief 不抢 A2 工作
- A1+1 commit `f032607` §3.2 D2 依赖改"无（与 0012 无关；可立即起）" — 本 brief 是该 D2 的实现

## §7 4 边界（**禁止触碰**）

- 不装 Pillow（用 reportlab 自带 = 决策 §2 决定）
- 不改 0012 迁移（属 A2；本 brief 与 0012 无关）
- 不改 Question model（image 已存 `question_images`）
- 不动 batch 业务
- 不改 S4 已修的字体段（commit `74500ad` 30,890 码点；不动）

---

> **【2026-10-19 14:4x 变更说明 · plans/M3-D2-W5-PDF-image-brief.md】**
>
> **修订**：新建（M3 派工 brief；A1+1 后可起；星云 14:37 批 "B1, B2, D2 可以起"）
> **内容**：1 任务 / 2 4 法核源 / 3 嵌图要点 / 4 必报项 / 5 派工回执 / 6 同步 / 7 4 边界
> **法源依据**：
> - 交接书 §4（W5 PDF 嵌图 排在可并行段）
> - A1+1 commit `f032607` §3.2 D2 依赖改"无（与 0012 无关；可立即起）" — 本 brief 是该 D2 的实现
> - D-17（subagent 写代码 / 主聊天不写大段）
> - D-43-X（4 法核源 + 对象级证据；拒收"已支持"字样）
> - §治理.19（容器 pytest 显式切测试库）
> **派工范围**：仅 `assignment_export.py` 改 + 新建 1 测试文件；其他文件不动
> **来源**：A1+1 commit `f032607` + 核源 exec 输出（requirements.txt + assignment_export.py 103-117 + 现有 PDF 测试 = 解析不是导出）
