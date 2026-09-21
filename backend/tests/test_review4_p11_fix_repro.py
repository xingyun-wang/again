"""review4 SQLite 复现 P1-1-1 fix 有效性（pytest fixture 框架下跑，绕开 PEP 563 导入问题）。

D-37 第 3 条可证伪硬门槛：修复后必须能 commit 成功 + 5 chapters + review_status=PENDING。
"""
from __future__ import annotations

from tests.conftest import (  # type: ignore[import-not-found]
    mock_db_engine,
    mock_db_session,
)


def test_review4_sqlite_repro_p11_fix(
    mock_db_engine,  # noqa: ARG001  # fixture fixture
    mock_db_session,
):
    """修复后路径：upload_textbook_with_extraction + 等分 fallback PDF → SUCCESS。

    - 5 chapters
    - 5 chapters 全部 ch.id 非 None（fbb7275 会因 FK violation 整段 commit 失败）
    - 模板化 chapters 的 review_status=PENDING
    """
    from app.models import KnowledgeReviewStatus, User
    from app.services.textbook_upload import upload_textbook_with_extraction

    # Pre-create owner_user_id=1 (FK needs User row for chapter.owner_user_id)
    owner = User(id=1, email="owner@test.local", hashed_password="x")
    mock_db_session.add(owner)
    mock_db_session.commit()

    tb, chapters = upload_textbook_with_extraction(
        db=mock_db_session,
        file_path="/tmp/review4_test.pdf",
        name="test",
        subject_id=None,
        grade_level="senior_high",
        owner_user_id=1,
    )

    # 验收断言（不在脚本里 raise，只 print；脚本末尾人工判定）
    print(f"\n=== REVIEW4 SQLITE REPRO OUTPUT ===")
    print(f"SUCCESS: textbook_id={tb.id}, chapters={len(chapters)}")
    all_ch_ids_non_null = True
    pending_count = 0
    for ch in chapters:
        latest_review = (
            max(ch.reviews, key=lambda r: r.id) if ch.reviews else None
        )
        ch_id_ok = ch.id is not None
        if not ch_id_ok:
            all_ch_ids_non_null = False
        is_pending = (
            latest_review is not None
            and latest_review.status == KnowledgeReviewStatus.PENDING
        )
        if is_pending:
            pending_count += 1
        print(
            f"  ch id={ch.id} title={ch.title!r} "
            f"src={ch.extraction_source!r} "
            f"review_status={latest_review.status if latest_review else None} "
            f"ch_id_non_null={ch_id_ok}"
        )
    print(f"ALL_CH_IDS_NON_NULL={all_ch_ids_non_null}")
    print(f"PENDING_REVIEW_COUNT={pending_count}/{len(chapters)}")
    print(f"=== END REVIEW4 SQLITE REPRO OUTPUT ===\n")

    # 关键断言（D-37 可证伪硬门槛）：如果 commit 失败这里就 raise 了
    assert len(chapters) == 5, f"期望 5 chapters，实际 {len(chapters)}"
    assert all_ch_ids_non_null, "FAIL: ch.id 仍为 None（P1-1-1 修复未生效）"
    assert pending_count == 5, (
        f"FAIL: 期望 5 个 PENDING review，实际 {pending_count}"
    )