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

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.types import TypeDecorator


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
    # W3-T2 追加：老师 → 题库导航（坑 #2，PUT 时避免级联问题）
    questions = relationship("Question", back_populates="teacher", cascade="all, delete-orphan")


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


# ============ Question（W3-T1 落地，CHARTER §3 §4 §5） ============


class Chapter(str, enum.Enum):
    """章节枚举（CHARTER §3 — 选择性必修 1 自然地理基础，全 5 章）。

    用 enum value 存 DB（ch1_earth_movement 等英文 slug），跨 SQLite/PostgreSQL 兼容。
    MVP 写死 5 章；W3-T5 老师审阅阶段如需扩展，再考虑改数据库存（CHARTER 改动门槛）。
    """

    CH1_地球运动 = "ch1_earth_movement"
    CH2_地表形态 = "ch2_landforms"
    CH3_大气运动 = "ch3_atmosphere"
    CH4_水的运动 = "ch4_water"
    CH5_整体性差异性 = "ch5_integrity_difference"


class QuestionType(str, enum.Enum):
    """题型枚举（W3 决策 2026-09-11 王星云拍板 — 只客观题）。

    SINGLE_CHOICE / MULTIPLE_CHOICE / TRUE_FALSE 三选一；essay/填空/解答题 MVP 不做。
    """

    SINGLE_CHOICE = "single_choice"       # 单选
    MULTIPLE_CHOICE = "multiple_choice"   # 多选
    TRUE_FALSE = "true_false"             # 判断


class _EnumString(TypeDecorator):
    """String 列 + ORM 层 Enum 白名单校验（跨 DB 兼容）。

    - 存储层：SQLite → TEXT；PostgreSQL → VARCHAR(length)
    - 校验层：process_bind_param 在 flush 时校验，非白名单值抛 ValueError
    - 设计动机：SQLite 无原生 ENUM；纯 Column(String) 写到非法值也不会报错。
      W3-T1 verify test 4 要求直接 `s.add(Question(question_type='essay', ...))` + commit
      必须失败，所以必须在 ORM 层挡掉，不能依赖 Pydantic/业务层 helper。

    使用：Column(_EnumString(QuestionType, length=16))
    """

    impl = String
    cache_ok = True

    def __init__(self, enum_cls: type, length: int = 16) -> None:
        super().__init__(length=length)
        self._enum_cls = enum_cls
        self._valid = frozenset(e.value for e in enum_cls)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        # str-mixin Enum 的实例本身就是 str（如 QuestionType.SINGLE_CHOICE == "single_choice"），
        # 所以 isinstance(value, str) 一并能覆盖 Enum 实例和裸字符串两种写法。
        if isinstance(value, str):
            if value not in self._valid:
                raise ValueError(
                    f"非法 {self._enum_cls.__name__} 值 {value!r}；"
                    f"必须在 {sorted(self._valid)} 之中"
                )
            return value
        raise TypeError(
            f"{self._enum_cls.__name__} 列只接受 str 或 str-mixin Enum 实例，"
            f"实际收到 {type(value).__name__}"
        )


class Question(Base):
    """题目表（W3-T1 落地）。

    关键设计：
    - options 用 SQLAlchemy JSON 类型（SQLite 自动序列化为 TEXT，PostgreSQL 存 JSONB）
    - answer 字段：单选/判断直接存选项内容字符串；多选存 JSON 字符串如 '["A","C"]'
      （统一存字符串，避免 list 与 JSON 列类型冲突；读回时上层按 question_type 解析）
    - question_type / level / chapter 用 _EnumString 做 ORM 层白名单
    - teacher_id FK → teacher.id（必须先 seed teacher 才能插入）
    - 反马太规则（W3 决策 2026-09-11）：作业生成时实时计算每档题数；
      本表只承载题目本身，反马太逻辑属于 W3-T4 作业生成模块。
    """

    __tablename__ = "question"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)
    answer = Column(String(255), nullable=False)
    question_type = Column(_EnumString(QuestionType, length=16), nullable=False)
    level = Column(_EnumString(Level, length=1), nullable=False)
    chapter = Column(_EnumString(Chapter, length=32), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teacher.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # W3-T2 追加（坑 #2）：老师 → 题目导航，避免 ORM 双向引用断链
    teacher = relationship("Teacher", back_populates="questions")