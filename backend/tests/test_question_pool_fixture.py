"""F1a + F1b + F1c — test_question_pool_fixture_loads 净移动 + 真用 fixture + choice.label 必填。

C 工单 fix(test) v2 落地（2026-09-29）：
- F1a：函数体从 backend/tests/conftest.py:416-446 净移到本文件。
  conftest.py 默认不被 pytest 收集（python_files = ["test_*.py", "*_test.py"]），
  原函数永远不被执行 = 死守卫。本文件命名 test_*.py 才被收集。
- F1b：签名加 question_pool_fixtures 参数，让 pytest 真注入 fixture；
  断言返回值 total + by_difficulty 含 D/C/B/A 四键 = 验的真是 fixture 本身。
  原代码 read_text() 自欺（验 fixture 但不调 fixture）已被本文件修正。
- F1c：每个 type=='choice' 的题，其 choices[*] 必须含 label 字段（非空字符串）。
  Question.choice 表 Mapped[str] = mapped_column(String(8), nullable=False) →
  缺 label → 写库必失败。本断言是写库前的最后防线。
"""


def test_question_pool_fixture_loads(question_pool_fixtures):
    """元教训防护：fixture 必须真的能 load + JSON 合法 + schema 字段齐 + choice.label 非空。"""
    fixtures = question_pool_fixtures

    # ─── F1b：验的是 fixture 自身（不是 read_text 自欺）───
    assert isinstance(fixtures['total'], int)
    assert fixtures['total'] >= 20, f"F1b: total 应 ≥ 20(D-47 #1 + D-47 #2),实有 {fixtures['total']}"
    assert 'by_difficulty' in fixtures
    for tier in ('D', 'C', 'B', 'A'):
        assert tier in fixtures['by_difficulty'], f"F1b: by_difficulty 缺档位 {tier}"

    demo = fixtures['demo']
    pool = fixtures['pool']

    # ─── S1-0: 引用完整性判据前奏（C1/C2 成员测试用 valid_*_refs）───
    valid_chapter_refs = fixtures['demo_chapter_refs']
    valid_kp_refs = fixtures['demo_kp_refs']

    # ─── 原断言（D-47 #1 fixture schema 校验，迁过来的）───
    assert len(demo) >= 20, f"D-47 #1 应至少 20 题（D/C/B/A 各 5），实有 {len(demo)}"

    diff_counts = {tier: sum(1 for q in demo if q['difficulty'] == tier) for tier in 'DCBA'}
    for tier, count in diff_counts.items():
        assert count >= 5, f"D-47 #1 缺档位 {tier}（应有 ≥5，实有 {count}）"

    for q in demo + pool:
        assert q['difficulty'] in 'DCBA'
        assert q['type'] in ('choice', 'fill', 'subjective')
        assert 'content' in q and len(q['content']) > 0
        # ─── S1-0: 引用完整性判据（替换原 'chapter_ref' in q 弱断言；C1 chapter + C2 KP）───
        assert q['chapter_ref'] in valid_chapter_refs, \
            f"C1: {q['ref']}: chapter_ref '{q['chapter_ref']}' 不在 demo.chapters[].ref 中"
        for kp in q.get('knowledge_points', []):
            assert kp in valid_kp_refs, \
                f"C2: {q['ref']}: KP '{kp}' 不在 demo.knowledge_points[].ref 中"
        assert isinstance(q.get('knowledge_points'), list)
        if q['type'] == 'choice':
            assert 'choices' in q and len(q['choices']) >= 2
            assert sum(1 for c in q['choices'] if c.get('is_correct')) == 1, \
                f"{q['ref']}: choice 类型必须恰好 1 个 is_correct=True"
            # ─── F1c：choice.label 必填（非空字符串）───
            for c in q['choices']:
                assert 'label' in c and c['label'], \
                    f"{q['ref']}: choice 必须含 label 字段（非空字符串），实有 {c}"