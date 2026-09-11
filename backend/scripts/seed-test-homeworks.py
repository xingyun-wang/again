#!/usr/bin/env python3
"""seed-test-homeworks.py — W3-T3: 2 个 homework + 关联表覆盖。

跑法（裸跑，不需 activate venv）：
    cd backend && python3 scripts/seed-test-homeworks.py

依赖通过探测 .venv-backend 自动加载（兼容真 venv + pip --target 两种 layout）。
前置依赖：seed-test-data.py + seed-test-questions.py 必须先跑
          （teacher / class / question 表非空，且 id=1=D/id=2=C/id=3=B 三题存在）。
幂等：每次跑前清空 homework + homework_question 表（不影响 teacher/class/student/question）。

2 个作业覆盖矩阵：
| HW  | status     | class_id | teacher_id | title                  | 题目数 | 关联 question_ids |
|-----|------------|----------|------------|------------------------|--------|-------------------|
| HW1 | DRAFT      | 1        | 1          | 第一章小测（草稿）     | 0      | —                 |
| HW2 | GENERATED  | 1        | 1          | 第二章小测（已生成）   | 3      | id=1(D) / id=2(C) / id=3(B), position 1-2-3 |

边界测试（在 main 末尾）：
- HomeworkStatus 边界：插入非法 status='draft_v2' 应被 ORM _EnumString 拒绝
- UniqueConstraint 边界：HW2 已含 question_id=1，再加一个 (homework_id=HW2.id, question_id=1) 应被拒

注意：
- 不动 main.py / database.py / requirements.txt
- 不跑 git commit
"""
from __future__ import annotations

import sys
from datetime import datetime
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
    Class,
    Homework,
    HomeworkQuestion,
    HomeworkStatus,
    Level,
    Question,
    Teacher,
)


# 2 个作业 seed 数据（HW2 关联的 3 个 question 各自带 level 快照）
SEED_HOMEWORKS = [
    {
        "title": "第一章小测（草稿）",
        "status": HomeworkStatus.DRAFT,
        "class_id": 1,
        "teacher_id": 1,
        "questions": [],   # 空作业
    },
    {
        "title": "第二章小测（已生成）",
        "status": HomeworkStatus.GENERATED,
        "class_id": 1,
        "teacher_id": 1,
        # 按 position 顺序：(question_id, level)
        "questions": [
            (1, Level.D),  # position 1 — 基础档
            (2, Level.C),  # position 2 — 进阶档
            (3, Level.B),  # position 3 — 挑战档
        ],
    },
]


def _test_status_rejection(session, *, class_id: int, teacher_id: int) -> None:
    """ORM 层 HomeworkStatus 白名单校验（_EnumString 拒绝非法值）。"""
    print("[seed-hw] 测试非法 status='draft_v2':")
    try:
        session.add(
            Homework(class_id=class_id, teacher_id=teacher_id, title="test", status="draft_v2")
        )
        session.commit()
        print("  ✗ 应该抛错但没抛（HomeworkStatus 非法值测试失败）")
        sys.exit(1)
    except Exception as e:
        # StatementError 包了 ValueError；用 __cause__ 让根因更显眼
        cause = getattr(e, "__cause__", None) or e
        print(f"  ✓ 非法值被 ORM 层拒绝 ({type(cause).__name__}): {cause}")
        session.rollback()


def _test_unique_constraint(session, *, homework_id: int) -> None:
    """UniqueConstraint (homework_id, question_id) 拒绝重复。"""
    from sqlalchemy.exc import IntegrityError

    print(f"[seed-hw] 测试 UniqueConstraint：往 homework_id={homework_id} 重复插 question_id=1:")
    try:
        session.add(
            HomeworkQuestion(homework_id=homework_id, question_id=1, level="D", position=99)
        )
        session.commit()
        print("  ✗ 应该抛 IntegrityError 但没抛（UniqueConstraint 测试失败）")
        sys.exit(1)
    except IntegrityError as e:
        print(f"  ✓ UniqueConstraint 生效 ({type(e).__name__})")
        session.rollback()
    except Exception as e:
        # 其他异常也算部分成功（落库前就拒），但要明确告诉调用方
        print(f"  ⚠ PARTIAL: {type(e).__name__}: {e}")
        session.rollback()


def main() -> None:
    session = SessionLocal()
    try:
        # 0. 拿 teacher / class（FK 强制要求存在）
        teacher = session.scalar(select(Teacher).where(Teacher.id == 1))
        if teacher is None:
            print("[seed-hw] FAIL: teacher id=1 不存在，请先跑 seed-test-data.py")
            sys.exit(1)
        klass = session.scalar(select(Class).where(Class.id == 1))
        if klass is None:
            print("[seed-hw] FAIL: class id=1 不存在，请先跑 seed-test-data.py")
            sys.exit(1)
        print(f"[seed-hw] 使用 teacher.id={teacher.id} ({teacher.name}) + class.id={klass.id} ({klass.name})")

        # 1. 拿 HW2 关联的 3 道题（FK 强制要求存在）
        needed_qids = [1, 2, 3]
        qs = session.scalars(select(Question).where(Question.id.in_(needed_qids))).all()
        if len(qs) != len(needed_qids):
            existing = {q.id for q in qs}
            missing = [i for i in needed_qids if i not in existing]
            print(f"[seed-hw] FAIL: question {missing} 不存在，请先跑 seed-test-questions.py")
            sys.exit(1)
        # T1/T2 已知坑：_EnumString.process_result_value 未实现 → ORM 读回时 level 是裸 str
        # 而不是 Level 枚举实例；统一用 _enum_value() 兼容（hasattr(value, "value")）
        def _enum_value(v):
            return v.value if hasattr(v, "value") else v
        qid_to_level = {q.id: _enum_value(q.level) for q in qs}
        print(f"[seed-hw] 关联 question: " + ", ".join(
            f"id={q.id}(level={_enum_value(q.level)})" for q in qs
        ))

        # 2. 幂等：清空 homework_question + homework（顺序：先清关联表）
        print("[seed-hw] 清空 homework_question + homework（幂等）")
        session.query(HomeworkQuestion).delete()
        session.query(Homework).delete()
        session.commit()

        # 3. 插 2 个作业
        print(f"[seed-hw] 插 {len(SEED_HOMEWORKS)} 个作业：")
        hw_ids = {}
        for spec in SEED_HOMEWORKS:
            title = spec["title"]
            status = spec["status"]
            obj = Homework(
                class_id=spec["class_id"],
                teacher_id=spec["teacher_id"],
                title=title,
                status=status,
            )
            session.add(obj)
            session.commit()
            session.refresh(obj)
            hw_ids[title] = obj.id
            # GENERATED 状态带 generated_at 时间戳
            if status == HomeworkStatus.GENERATED:
                obj.generated_at = datetime.utcnow()
                session.commit()
            print(
                f"  → {title} id={obj.id}, status={status.value}, "
                f"class_id={obj.class_id}, teacher_id={obj.teacher_id}"
            )

        # 4. 插 HW2 的 3 个关联
        print("[seed-hw] 插 HW2 的 3 个 HomeworkQuestion：")
        hw2_id = hw_ids["第二章小测（已生成）"]
        hw2_spec = next(s for s in SEED_HOMEWORKS if s["title"] == "第二章小测（已生成）")
        for position, (qid, level) in enumerate(hw2_spec["questions"], 1):
            # 校验 level 与 question 真实 level 一致（MVP 假设作业生成时档位对齐）
            q_actual_level = qid_to_level[qid]
            spec_level = level.value if hasattr(level, "value") else level
            if q_actual_level != spec_level:
                print(
                    f"  ⚠ position {position}: spec level={spec_level} "
                    f"vs Question.level={q_actual_level}（不一致，记录但继续）"
                )
            obj = HomeworkQuestion(
                homework_id=hw2_id,
                question_id=qid,
                level=level,
                position=position,
            )
            session.add(obj)
            session.commit()
            session.refresh(obj)
            print(
                f"  → position {position}: id={obj.id}, "
                f"question_id={obj.question_id}, level={_enum_value(obj.level)}"
            )

        # 5. 读回校验：行数 + relationship 完整性
        n_hw = session.scalar(select(func.count()).select_from(Homework))
        n_hwq = session.scalar(select(func.count()).select_from(HomeworkQuestion))
        print(f"[seed-hw] 读回：homework={n_hw}, homework_question={n_hwq}")
        assert n_hw == 2, f"homework 行数 != 2 (got {n_hw})"
        assert n_hwq == 3, f"homework_question 行数 != 3 (got {n_hwq})"

        # relationship 校验：HW2.questions 应返回 3 个 HomeworkQuestion，按 position 排
        hw2 = session.scalar(select(Homework).where(Homework.id == hw2_id))
        qids_loaded = [hq.question_id for hq in hw2.questions]
        positions_loaded = [hq.position for hq in hw2.questions]
        print(f"[seed-hw] HW2.questions 关联: question_ids={qids_loaded}, positions={positions_loaded}")
        assert qids_loaded == [1, 2, 3], f"HW2.questions question_ids 顺序错: {qids_loaded}"
        assert positions_loaded == [1, 2, 3], f"HW2.questions positions 顺序错: {positions_loaded}"

        # teacher / class 双向导航
        teacher_loaded = session.scalar(select(Teacher).where(Teacher.id == teacher.id))
        teacher_hw_titles = [h.title for h in teacher_loaded.homeworks]
        class_loaded = session.scalar(select(Class).where(Class.id == klass.id))
        class_hw_titles = [h.title for h in class_loaded.homeworks]
        # HW2.questions 的 level 也要兼容读回（_EnumString 坑）
        for hq in hw2.questions:
            _ = _enum_value(hq.level)  # 触发读取，确认无异常
        print(f"[seed-hw] Teacher.homeworks: {teacher_hw_titles}")
        print(f"[seed-hw] Class.homeworks: {class_hw_titles}")
        assert sorted(teacher_hw_titles) == sorted([s["title"] for s in SEED_HOMEWORKS])
        assert sorted(class_hw_titles) == sorted([s["title"] for s in SEED_HOMEWORKS])

        # 6. 边界测试
        print("[seed-hw] ORM 层边界测试：")
        _test_status_rejection(session, class_id=klass.id, teacher_id=teacher.id)
        _test_unique_constraint(session, homework_id=hw2_id)

        print("[seed-hw] done.")
    finally:
        session.close()


if __name__ == "__main__":
    main()