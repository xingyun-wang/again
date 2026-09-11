"""ORM models — W1-T2 schema 落地。

三张表：teacher / class / student
外加 Level 枚举（D/C/B/A，对应 CHARTER §4 档位）。

约束（CHARTER §3）：
- 单师多班，单班 50 人；学科 = 高二地理；MVP = 选择性必修 1 全 5 章。

注意：
- SQLite 无原生 ENUM，用 String(1) 字段 + Python Enum 校验（写入时抛错）
- ORM 模型名 Class 在 SQLAlchemy 里会自动用表名 class_（SQLite CLI 用 "class" 加引号）
- 顺序依赖：teacher → class → student（FK 强制）
- 反马太规则：CHARTER §4 — D 档强制 20% 拔高（T2 只注释，业务逻辑见 W3）
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class Level(str, enum.Enum):
    """档位枚举（CHARTER §4）。

    字母升序 = 难度升序：D 基础 → C 进阶 → B 挑战 → A 扩展。
    用 str 混入是为了 SQLAlchemy 直接存字符串值（D/C/B/A），不是 enum 的 repr。
    """

    D = "D"  # 基础
    C = "C"  # 进阶
    B = "B"  # 挑战
    A = "A"  # 扩展


class Teacher(Base):
    """教师表。

    MVP 范围：一个教师可带多个班级（class.teacher_id → teacher.id）。
    """

    __tablename__ = "teacher"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    classes = relationship("Class", back_populates="teacher", cascade="all, delete-orphan")


class Class(Base):
    """班级表。

    反马太规则（CHARTER §4，业务逻辑 W3 实现）：
    D 档作业里必须强制混入 20% 的 C 档题，防止"差生永远做简单题"。
    本注释是规则声明，T2 只注释不实现业务逻辑。
    """

    __tablename__ = "class"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    grade = Column(Integer, nullable=False, default=2)  # MVP 默认 2（高二）
    teacher_id = Column(Integer, ForeignKey("teacher.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    teacher = relationship("Teacher", back_populates="classes")
    students = relationship("Student", back_populates="class_", cascade="all, delete-orphan")


class Student(Base):
    """学生表。

    initial_password 是初始密码，T4 改密功能会用上。
    student_no 在同一 class_id 内唯一（unique constraint 见 __table_args__）。
    """

    __tablename__ = "student"
    __table_args__ = (
        # 学号在班级内唯一（不同班级可重号）
        UniqueConstraint("class_id", "student_no", name="uq_student_class_no"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    student_no = Column(String(32), nullable=False)
    class_id = Column(Integer, ForeignKey("class.id"), nullable=False)
    initial_password = Column(String(128), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    class_ = relationship("Class", back_populates="students")