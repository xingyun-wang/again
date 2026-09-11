#!/usr/bin/env python3
"""seed-test-questions.py — W3-T1: 5 道题覆盖 + ORM 层枚举边界测试。

跑法（裸跑，不需 activate venv）：
    cd backend && python3 scripts/seed-test-questions.py

依赖通过探测 .venv-backend 自动加载（兼容真 venv + pip --target 两种 layout）。
前置依赖：seed-test-data.py 必须先跑（teacher 表非空）。
幂等：每次跑前清空 question 表（不影响 teacher/class/student）。

5 道题覆盖矩阵（Q 顺序 = chapter/level/type 组合）：
| Q  | chapter | level | type          | 验证目的                           |
|----|---------|-------|---------------|------------------------------------|
| Q1 | ch1     | D     | single_choice | 单选 + D 档 + ch1（基础入门）      |
| Q2 | ch2     | C     | multiple_choice | 多选 + C 档 + ch2（JSON 选项）   |
| Q3 | ch3     | B     | true_false    | 判断 + B 档 + ch3（选项固定 2 个） |
| Q4 | ch4     | A     | single_choice | 单选 + A 档 + ch4（最高难度）      |
| Q5 | ch5     | D     | single_choice | 再一个 D 档覆盖 ch5（验证档位可重复）|

边界测试（在 main 末尾）：
- question_type="essay" → ORM 层 _EnumString 应抛 ValueError
- level="X"             → ORM 层 _EnumString 应抛 ValueError
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# 把 .venv-backend 的 site-packages 加进 sys.path（兼容两种 layout）
VENV_DIR = BACKEND_DIR / ".venv-backend"
for _candidate in (
    VENV_DIR / "lib" / "python3.8" / "site-packages",  # 真 venv layout
    VENV_DIR,                                          # pip --target 散装 layout
):
    if _candidate.is_dir() and (_candidate / "sqlalchemy").exists():
        sys.path.insert(0, str(_candidate))
        break

from sqlalchemy import func, select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Chapter,
    Level,
    Question,
    QuestionType,
    Teacher,
)


# 5 道测试题（content 是教学上合理的地理题，按 CHARTER §3 §4 设计）
SEED_QUESTIONS = [
    {
        # Q1: ch1 + D + single_choice（基础档入门）
        "content": "地球自转的方向是？",
        "options": ["自西向东", "自东向西", "自南向北", "自北向南"],
        "answer": "自西向东",
        "question_type": QuestionType.SINGLE_CHOICE,
        "level": Level.D,
        "chapter": Chapter.CH1_地球运动,
    },
    {
        # Q2: ch2 + C + multiple_choice（验证 JSON 选项 + JSON 字符串答案）
        "content": "下列哪些属于内力作用形成的地表形态？（多选）",
        "options": ["褶皱山", "冲积扇", "火山", "三角洲"],
        # 多选用 JSON 字符串存 answer（统一字符串列存，避免 list/JSON 类型冲突）
        "answer": '["褶皱山","火山"]',
        "question_type": QuestionType.MULTIPLE_CHOICE,
        "level": Level.C,
        "chapter": Chapter.CH2_地表形态,
    },
    {
        # Q3: ch3 + B + true_false（验证判断题选项固定 2 个）
        "content": "近地面大气主要的直接热源是地面辐射。（判断）",
        "options": ["对", "错"],
        "answer": "对",
        "question_type": QuestionType.TRUE_FALSE,
        "level": Level.B,
        "chapter": Chapter.CH3_大气运动,
    },
    {
        # Q4: ch4 + A + single_choice（最高难度）
        "content": "下列水循环环节中，受人类活动影响最广泛的是？",
        "options": ["海洋蒸发", "水汽输送", "地表径流", "植物蒸腾"],
        "answer": "地表径流",
        "question_type": QuestionType.SINGLE_CHOICE,
        "level": Level.A,
        "chapter": Chapter.CH4_水的运动,
    },
    {
        # Q5: ch5 + D + single_choice（验证 D 档可重复 + 覆盖 ch5）
        "content": "下列哪一项最能体现自然地理环境的整体性？",
        "options": [
            "各要素之间相互联系、相互制约",
            "各要素之间相互独立",
            "只有气候影响植被",
            "只有地形影响河流",
        ],
        "answer": "各要素之间相互联系、相互制约",
        "question_type": QuestionType.SINGLE_CHOICE,
        "level": Level.D,
        "chapter": Chapter.CH5_整体性差异性,
    },
]


def _test_enum_rejection(session, teacher_id: int, *, field: str, bad_value, label: str) -> None:
    """对 Question 的三个枚举字段做 ORM 层拒绝测试。

    利用 Q1 + Q2 中的合法值，把目标字段替换为非法值，提交应抛 ValueError。
    注：SQLAlchemy 在 INSERT 时会用 _EnumString.process_bind_param 抛 ValueError，
    但 ORM 会用 StatementError 包装一层；所以这里捕获 Exception 更鲁棒。
    """
    base = SEED_QUESTIONS[0].copy()  # Q1: ch1 + D + single_choice
    base["teacher_id"] = teacher_id
    base[field] = bad_value

    print(f"[seed-q] 测试非法 {field}={bad_value!r}:")
    try:
        session.add(Question(**base))
        session.commit()
        print(f"  ✗ 应该抛错但没抛（{label} 测试失败）")
        sys.exit(1)
    except Exception as e:
        # 拆出根因（StatementError 包了 ValueError）方便阅读
        cause = getattr(e, "__cause__", None) or e
        print(f"  ✓ 非法值被 ORM 层拒绝 ({type(cause).__name__}): {cause}")
        session.rollback()


def main() -> None:
    session = SessionLocal()
    try:
        # 0. 拿 teacher.id（FK 强制要求 teacher 存在）
        teacher = session.scalar(select(Teacher).limit(1))
        if teacher is None:
            print("[seed-q] FAIL: teacher 表为空，请先跑 seed-test-data.py")
            sys.exit(1)
        print(f"[seed-q] 使用 teacher.id={teacher.id} ({teacher.name})")

        # 1. 幂等：清空 question 表（不影响 teacher/class/student）
        print("[seed-q] 清空 question 表（幂等）")
        session.query(Question).delete()
        session.commit()

        # 2. 插 5 道题
        print(f"[seed-q] 插 {len(SEED_QUESTIONS)} 道题：")
        for i, q in enumerate(SEED_QUESTIONS, 1):
            obj = Question(teacher_id=teacher.id, **q)
            session.add(obj)
            session.commit()
            session.refresh(obj)
            qtype = q["question_type"].value
            level = q["level"].value
            chapter = q["chapter"].value
            content_preview = q["content"][:30] + ("..." if len(q["content"]) > 30 else "")
            print(
                f"  Q{i} → id={obj.id}, "
                f"chapter={chapter}, level={level}, type={qtype}\n"
                f"      content={content_preview!r}"
            )

        # 3. 读回校验：行数 + 档位覆盖 + 章节覆盖
        n = session.scalar(select(func.count()).select_from(Question))
        all_q = session.scalars(select(Question)).all()
        levels = sorted({q.level for q in all_q})
        chapters = sorted({q.chapter for q in all_q})
        types_ = sorted({q.question_type for q in all_q})
        print(f"[seed-q] 读回：question 总数={n}")
        print(f"        level 覆盖={levels}（期望 ['A','B','C','D'] 全部）")
        print(f"        chapter 覆盖数={len(chapters)}（期望 5）")
        print(f"        type 覆盖={types_}")
        assert n == 5, f"行数 != 5 (got {n})"
        assert levels == ["A", "B", "C", "D"], f"档位覆盖不全: {levels}"
        assert len(chapters) == 5, f"章节覆盖不全: {chapters}"

        # 4. ORM 层枚举边界测试
        print("[seed-q] ORM 层枚举边界测试：")
        _test_enum_rejection(
            session, teacher.id,
            field="question_type", bad_value="essay", label="question_type 非法值",
        )
        _test_enum_rejection(
            session, teacher.id,
            field="level", bad_value="X", label="level 非法值",
        )
        _test_enum_rejection(
            session, teacher.id,
            field="chapter", bad_value="ch99_unknown", label="chapter 非法值",
        )

        print("[seed-q] done.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
