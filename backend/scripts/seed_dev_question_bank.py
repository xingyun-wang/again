"""Seed dev 题库 from backend/tests/fixtures/questions_pool.jsonl.

=== 决策 (载曜 2026-10-16 08:24, per 星云拍) ===
- Source : backend/tests/fixtures/questions_pool.jsonl (200 题 / D 100 + C 100 / 全 choice)
- Target : D 池 ≥ 30 + C 池 ≥ 30 (B/A 删 per 星云拍; pool 本身 B/A=0 自洽)
- Action : 整池全入 (200 道; 超目标 70 道余量)
- chapter_id = 1 (Phase 1 UPDATE 后 extraction_source=equal_split_placeholder)
- owner_user_id = 1 (现有 user)
- knowledge_points: 丢 (fixture 是 demo KP 引用, DB 无对应 KP row)

=== D-43-X §9 4 法核源 (写脚本前必跑) ===
1. 字段真值: Question(owner/chapter/content/difficulty/type) + Choice(qid/label/content/is_correct/order_index) (见 4 法核源 §0)
2. enum 真值: question_difficulty_enum(D/C/B/A) + question_type_enum(choice/fill/subjective) (见下方 PG enum 核源)
3. FK 引用链: chapter_id → chapters.id=1 + owner_user_id → users.id=1 (4 法核源 §N5 已验)
4. 容器连接: DATABASE_URL = postgresql+psycopg://postgres:postgres@postgres:5432/tiered_homework (4 法核源 §S4 已验)

=== 不可重复 (idempotency) ===
- 跑前 SELECT count(*) FROM questions WHERE chapter_id=1; > 0 → 拒跑
- 如需 reseed: DELETE FROM questions WHERE chapter_id=1; 后重跑

=== Phase 1 + 附带问 现状 (本脚本前) ===
- chapters.id=1 extraction_source: manual → equal_split_placeholder (双判据核源过)
- subjects.id=1: name=数学 → 高中地理; grade_level=junior_high → senior_high
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

import psycopg

# 容器内 (cwd=/app) 或 host (cwd=project root) 都能跑
CANDIDATE_POOL_PATHS = (
    Path("/app/tests/fixtures/questions_pool.jsonl"),
    Path("backend/tests/fixtures/questions_pool.jsonl"),
)

# 跟 docker-compose.yml backend env DATABASE_URL 对齐
DB_DSN = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@postgres:5432/tiered_homework",
).replace("postgresql+psycopg://", "postgresql://")

CHAPTER_ID = 1
USER_ID = 1
TARGET_D = 30
TARGET_C = 30
SKIP_TIERS = ("B", "A")  # per 星云拍 "B/A 删档"
VALID_EXTRACTION_SOURCES = (
    "detected", "pdfplumber_fallback", "equal_split_placeholder", "scanned_pdf_empty",
)


def find_pool() -> Path:
    for p in CANDIDATE_POOL_PATHS:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"pool.jsonl not found in: {[str(p) for p in CANDIDATE_POOL_PATHS]}"
    )


def main() -> int:
    pool_path = find_pool()
    pool_size = pool_path.stat().st_size
    print(f"[seed] pool = {pool_path} ({pool_size} B)")

    with psycopg.connect(DB_DSN, autocommit=False) as conn:
        with conn.cursor() as cur:
            # 4 法核源 #3: chapter + user 真存在
            cur.execute("SELECT count(*) FROM chapters WHERE id = %s", (CHAPTER_ID,))
            n_chapter = cur.fetchone()[0]
            if n_chapter != 1:
                return _fail(f"chapter id={CHAPTER_ID} count={n_chapter} (expected 1)")
            cur.execute("SELECT count(*) FROM users WHERE id = %s", (USER_ID,))
            n_user = cur.fetchone()[0]
            if n_user != 1:
                return _fail(f"user id={USER_ID} count={n_user} (expected 1)")

            # 4 法核源 #2: extraction_source 必 = 4 合法值之一 (Phase 1 决策落地校验)
            cur.execute(
                "SELECT extraction_source FROM chapters WHERE id = %s", (CHAPTER_ID,),
            )
            ext_src = cur.fetchone()[0]
            if ext_src not in VALID_EXTRACTION_SOURCES:
                return _fail(
                    f"chapter extraction_source='{ext_src}' 不在 4 合法值 {VALID_EXTRACTION_SOURCES}"
                )

            # Idempotency check
            cur.execute(
                "SELECT count(*) FROM questions WHERE chapter_id = %s", (CHAPTER_ID,),
            )
            existing = cur.fetchone()[0]
            if existing > 0:
                print(
                    f"[seed] ABORT: chapter {CHAPTER_ID} 已有 {existing} 道题; 拒跑避免重复."
                )
                print(f"[seed] 如需 reseed, 先跑: DELETE FROM questions WHERE chapter_id={CHAPTER_ID};")
                return 1

            # 读 pool + 4 法核源 #1: 字段真值
            rows = []
            with pool_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    q = json.loads(line)
                    assert "difficulty" in q, f"missing difficulty: {q.get('ref')}"
                    assert q["difficulty"] in ("D", "C", "B", "A"), (
                        f"bad difficulty={q['difficulty']}: {q.get('ref')}"
                    )
                    assert "type" in q, f"missing type: {q.get('ref')}"
                    assert q["type"] in ("choice", "fill", "subjective"), (
                        f"bad type={q['type']}: {q.get('ref')}"
                    )
                    assert "content" in q and q["content"], f"empty content: {q.get('ref')}"
                    assert "choices" in q and len(q["choices"]) >= 2, (
                        f"choice < 2: {q.get('ref')}"
                    )
                    if q["difficulty"] in SKIP_TIERS:  # B/A 删 per 决策
                        continue
                    rows.append(q)

            counts = Counter(r["difficulty"] for r in rows)
            print(
                f"[seed] pool filtered: D={counts.get('D', 0)} + C={counts.get('C', 0)} "
                f"(B/A 跳过 per 决策)"
            )

            # 4 法核源 #2: 写入用 PG 原生 enum 强类型
            insert_q = """
                INSERT INTO questions
                    (owner_user_id, chapter_id, content, difficulty, type)
                VALUES
                    (%s, %s, %s, %s::question_difficulty_enum, %s::question_type_enum)
                RETURNING id
            """
            insert_c = """
                INSERT INTO choices
                    (question_id, label, content, is_correct, order_index)
                VALUES
                    (%s, %s, %s, %s, %s)
            """

            n_questions = 0
            n_choices = 0
            for r in rows:
                cur.execute(insert_q, (
                    USER_ID, CHAPTER_ID, r["content"], r["difficulty"], r["type"],
                ))
                qid = cur.fetchone()[0]
                n_questions += 1
                for c in r["choices"]:
                    cur.execute(insert_c, (
                        qid, c["label"], c["content"],
                        bool(c["is_correct"]), int(c["order_index"]),
                    ))
                    n_choices += 1
            conn.commit()

            # B2 双判据: 改后真值 (跟写入预期对比)
            cur.execute(
                """
                SELECT difficulty, count(*) FROM questions
                WHERE chapter_id = %s GROUP BY difficulty ORDER BY difficulty
                """,
                (CHAPTER_ID,),
            )
            db_counts = dict(cur.fetchall())
            print(f"[seed] DB 真值: {db_counts}")
            print(f"[seed] DONE: {n_questions} questions + {n_choices} choices inserted")

            ok = True
            if db_counts.get("D", 0) < TARGET_D:
                print(f"[seed] FAIL: D 池 {db_counts.get('D', 0)} < {TARGET_D} 目标")
                ok = False
            if db_counts.get("C", 0) < TARGET_C:
                print(f"[seed] FAIL: C 池 {db_counts.get('C', 0)} < {TARGET_C} 目标")
                ok = False
            if ok:
                print(
                    f"[seed] B2 判据 命中: D 池={db_counts.get('D', 0)} ≥ {TARGET_D} ✓ "
                    f"+ C 池={db_counts.get('C', 0)} ≥ {TARGET_C} ✓"
                )
                return 0
            return 5


def _fail(msg: str) -> int:
    print(f"[seed] FAIL: {msg}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
