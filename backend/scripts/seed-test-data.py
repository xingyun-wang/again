#!/usr/bin/env python3
"""seed-test-data.py — W1-T2: 种子数据 + level 枚举边界测试。

跑法（裸跑，不需 activate venv）：
    cd backend && python3 scripts/seed-test-data.py

依赖通过探测 .venv-backend 自动加载（兼容真 venv + pip --target 两种 layout）。
幂等依赖 init-db.py 先跑（create_all 落表）。

种子内容：
- 1 个 teacher（name="测试老师"）
- 1 个 class（name="高二(1)班", grade=2）
- 5 个 student（name="学生1"..，class_id=...）

边界测试：
- 试图用 Level 枚举外的值 "X" 写入（模拟）。SQLite 没原生 ENUM，
  我们手动用 Python Enum 做白名单校验 + 抛错演示。
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

from app.database import SessionLocal, engine  # noqa: E402
from app.models import Class, Level, Student, Teacher  # noqa: E402


def _safe_level(value: str) -> Level:
    """模拟业务层对 level 的校验：非法值抛 ValueError。"""
    try:
        return Level(value)
    except ValueError as e:
        raise ValueError(f"level 非法值 '{value}' 被拒绝（必须 ∈ {set(l.value for l in Level)}）") from e


def main() -> None:
    session = SessionLocal()
    try:
        # 0. 幂等：先清空（保留 schema，只删数据），保证可重跑
        print("[seed] 清空 teacher/class/student（幂等）")
        # FK 顺序：student -> class -> teacher
        session.query(Student).delete()
        session.query(Class).delete()
        session.query(Teacher).delete()
        session.commit()

        # 1. teacher
        print("[seed] 插 teacher: 测试老师")
        teacher = Teacher(name="测试老师")
        session.add(teacher)
        session.commit()
        session.refresh(teacher)
        print(f"  → teacher.id={teacher.id}, name={teacher.name}, created_at={teacher.created_at}")

        # 2. class
        print("[seed] 插 class: 高二(1)班 (grade=2, teacher_id={})".format(teacher.id))
        klass = Class(name="高二(1)班", grade=2, teacher_id=teacher.id)
        session.add(klass)
        session.commit()
        session.refresh(klass)
        print(f"  → class.id={klass.id}, name={klass.name}, grade={klass.grade}")

        # 3. 5 students
        print("[seed] 插 5 个 student:")
        for i in range(1, 6):
            stu = Student(
                name=f"学生{i}",
                student_no=f"2026{klass.grade:02d}{i:03d}",
                class_id=klass.id,
                initial_password=f"init-pw-{i}",
            )
            session.add(stu)
            session.commit()
            session.refresh(stu)
            print(f"  → student.id={stu.id}, name={stu.name}, student_no={stu.student_no}, class_id={stu.class_id}")

        # 4. level 枚举边界测试
        print("[seed] 测试 Level 枚举边界：")
        for legal in ["D", "C", "B", "A"]:
            lv = _safe_level(legal)
            print(f"  ✓ Level('{legal}') -> {lv} (合法)")

        print("[seed] 测试非法值 'X':")
        try:
            _safe_level("X")
            print("  ✗ 应该抛错但没抛（边界测试失败）")
            sys.exit(1)
        except ValueError as e:
            print(f"  ✓ level 非法值 'X' 被拒绝 ({e})")
            print("[seed] 边界测试通过：Level 枚举白名单校验生效")

        # 5. 读回校验
        print("[seed] 读回校验：")
        from sqlalchemy import select

        t_count = session.scalar(select(Teacher).where(Teacher.id == teacher.id)) is not None
        c_count = session.scalar(select(Class).where(Class.id == klass.id)) is not None
        s_list = session.scalars(select(Student).where(Student.class_id == klass.id)).all()
        print(f"  teacher(id={teacher.id}) 存在: {t_count}")
        print(f"  class(id={klass.id}) 存在: {c_count}")
        print(f"  student(class_id={klass.id}) 数量: {len(s_list)} (期望 5)")

        print("[seed] done.")
    finally:
        session.close()


if __name__ == "__main__":
    main()