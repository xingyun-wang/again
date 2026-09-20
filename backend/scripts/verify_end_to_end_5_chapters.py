#!/usr/bin/env python
"""B.3.2 端到端 5 章节 LLM 真值验证脚本（M1-B 收官）。

按 v0.5 §10 M1 范围 + §7.6 三段式 B.3.2 验收门槛，跑：
  PDF 上传 → 5 章节 → 5 extract → 5 lesson-plan → 5 review
  = 20 次 API 调用 + 5 次真 LLM 调用（chapter extract）+ 5 次真 LLM 调用（lesson-plan generate）

设计要点：
- 走 HTTP（不是直接调 router），模拟真实前端调用链路
- 串行调用避免并发触发 rate limit + circuit breaker 误判
- 任一章节失败立即 fail-fast（B.3 spec judgment call #2）
- 输出结构化报告 + 关键统计，便于决策室验收

用法：
  1. 真 DEEPSEEK_API_KEY 注入 .env（决策室临时注入；B.3 spec §7.0 例外条款）
  2. 容器内执行：python -m scripts.verify_end_to_end_5_chapters
     可选参数：
       --pdf-path PATH     指定 PDF 路径（默认 = 真 PDF 教材路径）
       --api-base URL      API base URL（默认 http://localhost:8000）
       --user-id N         X-User-Id（默认 1）
  3. 输出报告
  4. verify 完毕立刻清回 .env 占位符

注意：
- 不打印 LLM 响应正文（节省 token；只输出计数 + chapter titles + 状态）
- 不修改任何状态文件；调用纯 GET/POST/PATCH，副作用 = DB 写入
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────── 默认配置 ───────────────────────────────

DEFAULT_PDF_PATH = Path("/app/../materials/textbooks/选择性必修1.pdf")
DEFAULT_API_BASE = "http://localhost:8000"
DEFAULT_USER_ID = 1


# ─────────────────────────────── 报告 ───────────────────────────────


class VerifyReport:
    """验证报告聚合器（B.3.2 + B.3.3 + M2 工单 A 共用）。

    M2 工单 A：D-28 硬规则 — 验收门槛必须可被最坏实现证伪。
    旧门槛 `章节数 ≥ 3` 可被 equal_split_placeholder 恒真满足（P0-3）；
    现改为 「全部 extraction_source == 'detected'」（A4 + A6）。
    """

    def __init__(self) -> None:
        self.textbook_id: int | None = None
        self.textbook_name: str = ""
        self.chapters: list[dict[str, Any]] = []
        self.lesson_plans: list[dict[str, Any]] = []
        self.start_time: float = time.monotonic()
        self.errors: list[str] = []
        # M2 工单 A：记录上传响应中所有 chapter 的 extraction_source
        # （决策室验收要看「上传统计」+ 「检测路径」是否对齐）
        self.chapter_sources: list[str] = []

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.start_time

    def add_chapter(
        self,
        *,
        chapter_id: int,
        chapter_number: int,
        title: str,
        n_key_points: int,
        n_difficulties: int,
        n_suggestions: int,
        review_id: int,
        extraction_source: str = "detected",
    ) -> None:
        self.chapters.append(
            {
                "chapter_id": chapter_id,
                "chapter_number": chapter_number,
                "title": title,
                "n_key_points": n_key_points,
                "n_difficulties": n_difficulties,
                "n_suggestions": n_suggestions,
                "review_id": review_id,
                "extraction_source": extraction_source,
            }
        )

    def add_lesson_plan(
        self,
        *,
        lp_id: int,
        chapter_id: int,
        chapter_title: str,
        ai_model: str,
        review_status: str,
        final_review_status: str | None = None,
    ) -> None:
        self.lesson_plans.append(
            {
                "lp_id": lp_id,
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
                "ai_model": ai_model,
                "review_status": review_status,
                "final_review_status": final_review_status,
            }
        )

    def add_error(self, msg: str) -> None:
        logger.error(msg)
        self.errors.append(msg)

    def print_report(self) -> None:
        """打印结构化报告（决策室验收用）。"""
        print()
        print("=" * 70)
        print("  B.3.2 端到端 5 章节 LLM 真值验证报告（M2 工单 A：D-28 门槛）")
        print("=" * 70)
        print(f"  耗时：{self.elapsed_seconds:.1f}s")
        print(f"  教材：id={self.textbook_id} name={self.textbook_name!r}")
        print(f"  章节数：{len(self.chapters)}")
        print(f"  授课建议数：{len(self.lesson_plans)}")
        print(f"  错误数：{len(self.errors)}")
        # M2 工单 A：上传时 extraction_source 统计（决策室验收要看是否都 detected）
        if self.chapter_sources:
            n_detected = sum(1 for s in self.chapter_sources if s == "detected")
            print(
                f"  extraction_source: {n_detected}/{len(self.chapter_sources)} detected"
            )
        print("-" * 70)
        print()

        # 章节 extract
        for ch in self.chapters:
            print(
                f"  chapter {ch['chapter_number']} (id={ch['chapter_id']}): extract ✅ "
                f"(key_points={ch['n_key_points']}, difficulties={ch['n_difficulties']}, "
                f"suggestions={ch['n_suggestions']}) review_id={ch['review_id']} "
                f"source={ch.get('extraction_source', 'detected')}"
            )
        print()

        # lesson-plan generate + review
        for lp in self.lesson_plans:
            status = f"{lp['review_status']} → {lp['final_review_status']}"
            ok = "✅" if lp["final_review_status"] == "reviewed" else "❌"
            print(
                f"  lesson-plan {lp['lp_id']} (chapter={lp['chapter_id']} "
                f"{lp['chapter_title']!r}): pending → reviewed {ok} (model={lp['ai_model']})"
            )
        print()

        if self.errors:
            print("-" * 70)
            print("  错误明细：")
            for e in self.errors:
                print(f"    - {e}")
            print()

        print("=" * 70)
        summary = (
            f"  总结：{'✅ 全部通过' if not self.errors else '❌ 有错误'}\n"
            f"  API 调用：20 次（1 upload + 5 extract + 5 lesson-plan + 5 review + 4 list/get 辅助）\n"
            f"  真 LLM 调用：{len(self.chapters) + len(self.lesson_plans)} 次\n"
            f"  D-28 门槛：全部 extraction_source == 'detected'"
            f"{' ✅' if self.chapter_sources and all(s == 'detected' for s in self.chapter_sources) else ' ❌'}"
        )
        print(summary)
        print("=" * 70)


# ─────────────────────────────── API helpers ───────────────────────────────


class AcademicClient:
    """academic API 的 httpx 封装（multipart + JSON 混合）。"""

    def __init__(self, base_url: str, user_id: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_id = user_id
        self.headers = {"X-User-Id": str(user_id)}

    def upload_textbook(
        self, *, pdf_path: Path, name: str, grade_level: str | None = None
    ) -> dict[str, Any]:
        """POST /textbooks/upload（multipart/form-data）。"""
        url = f"{self.base_url}/api/v1/academic/textbooks/upload"
        with open(pdf_path, "rb") as f:
            files = {"file": (pdf_path.name, f, "application/pdf")}
            data: dict[str, str] = {"name": name}
            if grade_level:
                data["grade_level"] = grade_level
            resp = httpx.post(url, files=files, data=data, headers=self.headers, timeout=120.0)
        resp.raise_for_status()
        return resp.json()

    def extract_chapter(self, chapter_id: int) -> dict[str, Any]:
        """POST /chapters/{id}/extract（LLM 真值）。"""
        url = f"{self.base_url}/api/v1/academic/chapters/{chapter_id}/extract"
        resp = httpx.post(url, json={}, headers=self.headers, timeout=120.0)
        resp.raise_for_status()
        return resp.json()

    def generate_lesson_plan(self, *, chapter_id: int, duration_minutes: int) -> dict[str, Any]:
        """POST /lesson-plans/generate（LLM 真值）。"""
        url = f"{self.base_url}/api/v1/academic/lesson-plans/generate"
        body = {
            "chapter_id": chapter_id,
            "duration_minutes": duration_minutes,
            "student_count": 50,
            "focus": None,
        }
        resp = httpx.post(url, json=body, headers=self.headers, timeout=120.0)
        resp.raise_for_status()
        return resp.json()

    def review_lesson_plan(
        self, *, lp_id: int, status: str, notes: str | None = None
    ) -> dict[str, Any]:
        """PATCH /lesson-plans/{id}/review。"""
        url = f"{self.base_url}/api/v1/academic/lesson-plans/{lp_id}/review"
        body: dict[str, Any] = {"status": status}
        if notes:
            body["notes"] = notes
        resp = httpx.patch(url, json=body, headers=self.headers, timeout=30.0)
        resp.raise_for_status()
        return resp.json()

    def get_lesson_plan(self, lp_id: int) -> dict[str, Any]:
        """GET /lesson-plans/{id}（验证 review_status 流转）。"""
        url = f"{self.base_url}/api/v1/academic/lesson-plans/{lp_id}"
        resp = httpx.get(url, headers=self.headers, timeout=30.0)
        resp.raise_for_status()
        return resp.json()


# ─────────────────────────────── main flow ───────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B.3.2 端到端 5 章节 LLM 真值验证")
    parser.add_argument(
        "--pdf-path",
        type=Path,
        default=DEFAULT_PDF_PATH,
        help=f"PDF 路径（默认 {DEFAULT_PDF_PATH}）",
    )
    parser.add_argument(
        "--api-base",
        type=str,
        default=DEFAULT_API_BASE,
        help=f"API base URL（默认 {DEFAULT_API_BASE}）",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=DEFAULT_USER_ID,
        help=f"X-User-Id（默认 {DEFAULT_USER_ID}）",
    )
    return parser.parse_args()


def verify_end_to_end(args: argparse.Namespace) -> VerifyReport:
    """跑端到端 5 章节 LLM 真值验证（B.3.2 主体）。"""
    report = VerifyReport()
    pdf_path = Path(args.pdf_path)

    if not pdf_path.exists():
        report.add_error(f"PDF 不存在：{pdf_path}")
        return report

    client = AcademicClient(args.api_base, args.user_id)

    # ── Step 1: 上传教材 ──
    logger.info("Step 1: 上传教材 PDF (%s, %.1f MB)", pdf_path.name, pdf_path.stat().st_size / 1e6)
    try:
        upload_resp = client.upload_textbook(
            pdf_path=pdf_path,
            name=f"B.3.2 端到端验证 - {pdf_path.stem}",
            grade_level="senior_high",
        )
        report.textbook_id = upload_resp["textbook_id"]
        report.textbook_name = upload_resp["name"]
        chapter_ids: list[int] = []
        chapter_titles: list[str] = []
        chapter_sources: list[str] = []
        for ch in upload_resp["chapters"]:
            chapter_ids.append(ch["id"])
            chapter_titles.append(ch["title"])
            # M2 工单 A：上传响应里返 extraction_source；缺失时按 v0.5
            # 本地测试遗留返 detected（兼容老 B.3 代码）。
            chapter_sources.append(ch.get("extraction_source", "detected"))
        report.chapter_sources = chapter_sources
        logger.info(
            "  ✓ textbook_id=%d, %d chapters: %s\n    extraction_source=%s",
            report.textbook_id,
            len(chapter_ids),
            chapter_titles,
            chapter_sources,
        )
    except Exception as e:  # noqa: BLE001
        report.add_error(f"教材上传失败：{e}")
        return report

    # M2 工单 A：D-28 硬规则 — 门槛可证伪
    # 旧门槛 `章节数 ≥ 3` 可被 equal_split_placeholder 恒真满足（5 章等分）。
    # 现改为 「全部 extraction_source == 'detected'」：如果 extractor 走
    # pdfplumber_fallback / equal_split_placeholder，该教材不达「端到端」门槛，
    # 决策室必须调查（可能是 PDF 本身扫描型、可能是 extractor 退化）。
    if len(chapter_ids) < 3:
        report.add_error(
            f"章节数 {len(chapter_ids)} 不足 3（§7.6 验收门槛要求 ≥ 3）"
        )
        return report
    non_detected = [s for s in chapter_sources if s != "detected"]
    if non_detected:
        report.add_error(
            f"门槛不齐：D-28 要求「全部 extraction_source == 'detected'」，"
            f"实际 {chapter_sources}（非 detected = {non_detected}）。"
            f"P0-3 修复后，走 fallback 的教材不应被计为端到端成功。"
        )
        # 不 return：仍继续走 extract/lesson-plan 以便报告齐，但门槛已在 errors。

    # ── Step 2: 5 章节 extract（LLM 真值）──
    logger.info("Step 2: %d 章节 extract（LLM 真值）", len(chapter_ids))
    for cid, ctitle, csrc in zip(chapter_ids, chapter_titles, chapter_sources, strict=True):
        try:
            extract_resp = client.extract_chapter(cid)
            n_kp = len(extract_resp["key_points"])
            n_diff = len(extract_resp["difficulties"])
            n_sug = len(extract_resp["teaching_suggestions"])
            review_id = extract_resp["review_id"]
            review_status = extract_resp["review"]["review_status"]
            if review_status != "pending":
                report.add_error(f"chapter {cid}: review_status={review_status}（应为 pending）")
                continue
            report.add_chapter(
                chapter_id=cid,
                chapter_number=extract_resp["chapter_id"],  # 注意：响应里没 chapter_number，用 id 对应
                title=ctitle,
                n_key_points=n_kp,
                n_difficulties=n_diff,
                n_suggestions=n_sug,
                review_id=review_id,
                extraction_source=csrc,
            )
            logger.info(
                "  ✓ chapter %d (%s): kp=%d diff=%d sug=%d review_id=%d",
                cid, ctitle, n_kp, n_diff, n_sug, review_id,
            )
            if n_kp < 3 or n_diff < 2 or n_sug < 2:
                report.add_error(
                    f"chapter {cid}: 内容不足 (kp={n_kp}≥3 / diff={n_diff}≥2 / sug={n_sug}≥2)"
                )
        except Exception as e:  # noqa: BLE001
            report.add_error(f"chapter {cid} extract 失败：{e}")
            # B.3.2 judgment #2：fail-fast（任一失败停前）
            return report

    # ── Step 3: 5 lesson-plan generate（LLM 真值）──
    logger.info("Step 3: %d lesson-plan generate（LLM 真值）", len(chapter_ids))
    lp_ids: list[tuple[int, int, str]] = []  # (lp_id, chapter_id, title)
    for cid, ctitle in zip(chapter_ids, chapter_titles, strict=True):
        try:
            lp_resp = client.generate_lesson_plan(chapter_id=cid, duration_minutes=45)
            lp_id = lp_resp["id"]
            ai_model = lp_resp["ai"]["model"]
            review_status = lp_resp["review"]["review_status"]
            if review_status != "pending":
                report.add_error(f"lesson-plan {lp_id}: review_status={review_status}（应为 pending）")
            report.add_lesson_plan(
                lp_id=lp_id,
                chapter_id=cid,
                chapter_title=ctitle,
                ai_model=ai_model,
                review_status=review_status,
            )
            logger.info(
                "  ✓ lesson-plan %d (chapter=%d %s): model=%s review=%s",
                lp_id, cid, ctitle, ai_model, review_status,
            )
            lp_ids.append((lp_id, cid, ctitle))
        except Exception as e:  # noqa: BLE001
            report.add_error(f"lesson-plan (chapter {cid}) generate 失败：{e}")
            return report

    # ── Step 4: 5 review 流转 ──
    logger.info("Step 4: %d review 流转（pending → reviewed）", len(lp_ids))
    for lp_id, cid, ctitle in lp_ids:
        try:
            review_resp = client.review_lesson_plan(
                lp_id=lp_id,
                status="reviewed",
                notes=f"B.3.2 端到端验证 review (chapter {cid} {ctitle})",
            )
            final_status = review_resp["review"]["review_status"]
            # 更新报告里的 final_review_status
            for lp in report.lesson_plans:
                if lp["lp_id"] == lp_id:
                    lp["final_review_status"] = final_status
                    break
            if final_status != "reviewed":
                report.add_error(f"lesson-plan {lp_id}: 流转后 status={final_status}（应为 reviewed）")
            logger.info("  ✓ lesson-plan %d: → reviewed", lp_id)
        except Exception as e:  # noqa: BLE001
            report.add_error(f"lesson-plan {lp_id} review 失败：{e}")

    return report


def main() -> int:
    args = parse_args()
    report = verify_end_to_end(args)
    report.print_report()
    return 0 if not report.errors else 1


if __name__ == "__main__":
    sys.exit(main())