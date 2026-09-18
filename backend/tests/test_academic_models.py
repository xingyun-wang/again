"""academic models 单元测试（M1-A 阶段 1：v0.5 §4.1 + §4.2）。

测试覆盖：
1. Subject → Class → Student 链式 CRUD
2. enum 合法性（GradeLevel / Tier / KnowledgeReviewStatus）+ 持久化字符串值
3. 关系双向访问（Student.class_ ↔ Class.students 等）
4. FK RESTRICT 行为（删 Class 触发 FK 异常）
5. Textbook → Chapter → KnowledgePoint / KeyPoint / Difficulty / TeachingSuggestion / Review
6. StudentKnowledgePoint 唯一约束 + cascade delete-orphan
7. Chapter 唯一约束 (textbook_id, chapter_number)
8. KnowledgeReview status 流转：pending → approved / modified
9. alembic 0002 migration 文件可 import + upgrade/downgrade 可调用

测试用 SQLite in-memory。alembic round-trip 用真 PG（如果可用），否则 skip。

# 关于 lazy="selectin" 的测试注意事项：
#   selectin 在 parent 加载时一次性把 collection 拉出来缓存。fixture A 创建 X，
#   fixture B 依赖 A 创建 X 的子 Y 后，A.x_collection 还是空 list（缓存）。
#   测试访问 A.x_collection 会拿到 stale []。
#   解法：子 fixture commit 后 `session.expire(parent, [attr_names])`，让下一次访问重发 SQL。
"""

from __future__ import annotations

import contextlib
import importlib.util
import os
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Chapter,
    Class,
    Difficulty,
    GradeLevel,
    KeyPoint,
    KnowledgePoint,
    KnowledgeReview,
    KnowledgeReviewStatus,
    Student,
    StudentKnowledgePoint,
    Subject,
    TeachingSuggestion,
    Textbook,
    Tier,
)

# ─────────────────────────── fixtures ───────────────────────────


@pytest.fixture()
def engine() -> Generator[sa.Engine, None, None]:
    """每个测试一个全新的 SQLite in-memory engine + 建表 + 启用 FK enforcement。"""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    # SQLite 默认不 enforce FK；PRAGMA 必须在每条新连接上设置
    @event.listens_for(eng, "connect")
    def _enable_fk(dbapi_conn: Any, _conn_record: Any) -> None:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    from app.db.base import Base

    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def session(engine: sa.Engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def sample_subject(session: Session) -> Subject:
    s = Subject(name="初中数学", grade_level=GradeLevel.JUNIOR_HIGH)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


@pytest.fixture()
def sample_class(session: Session, sample_subject: Subject) -> Class:
    c = Class(
        name="初一 (3) 班",
        grade_level=GradeLevel.JUNIOR_HIGH,
        subject_id=sample_subject.id,
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    # 让 sample_subject.classes 在下次访问时重新加载（selectin cache stale）
    session.expire(sample_subject, ["classes"])
    return c


@pytest.fixture()
def sample_student(session: Session, sample_class: Class) -> Student:
    s = Student(
        name="王小星",
        class_id=sample_class.id,
        grade_level=GradeLevel.JUNIOR_HIGH,
        current_tier=Tier.B,
    )
    session.add(s)
    session.commit()
    session.refresh(s)
    # 让 sample_class.students 在下次访问时重新加载
    session.expire(sample_class, ["students"])
    return s


# ─────────────────────────── 1. CRUD 链式 ───────────────────────


def test_subject_class_student_chain_create_and_read(
    session: Session, sample_student: Student
) -> None:
    """Subject → Class → Student 三层创建，从 session 重新读回，数据一致。"""
    stmt = select(Student).where(Student.name == "王小星")
    got = session.execute(stmt).scalar_one()

    assert got.id == sample_student.id
    assert got.current_tier == Tier.B
    assert got.grade_level == GradeLevel.JUNIOR_HIGH

    # 双向：Student → Class → Subject
    assert got.class_.name == "初一 (3) 班"
    assert got.class_.subject.name == "初中数学"
    assert got.class_.subject.grade_level == GradeLevel.JUNIOR_HIGH

    # 时间戳非空
    assert isinstance(got.created_at, datetime)
    assert isinstance(got.updated_at, datetime)


# ─────────────────────────── 2. enum 合法性 ──────────────────────


def test_grade_level_enum_values() -> None:
    """GradeLevel 只有两个合法值。"""
    assert {g.value for g in GradeLevel} == {"junior_high", "senior_high"}
    assert GradeLevel("junior_high") is GradeLevel.JUNIOR_HIGH
    assert GradeLevel("senior_high") is GradeLevel.SENIOR_HIGH


def test_grade_level_enum_rejects_unknown_value() -> None:
    """非法值抛 ValueError。"""
    with pytest.raises(ValueError):
        GradeLevel("primary_school")  # type: ignore[arg-type]


def test_tier_enum_values() -> None:
    """Tier 必须严格 D/C/B/A（v0.5 §3.2）。"""
    assert {t.value for t in Tier} == {"D", "C", "B", "A"}
    assert Tier("D") is Tier.D
    assert Tier("A") is Tier.A


def test_tier_enum_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        Tier("S")  # type: ignore[arg-type]


def test_knowledge_review_status_enum_values() -> None:
    """KnowledgeReviewStatus 三态：pending / approved / modified。"""
    assert {s.value for s in KnowledgeReviewStatus} == {"pending", "approved", "modified"}
    assert KnowledgeReviewStatus("pending") is KnowledgeReviewStatus.PENDING


def test_knowledge_review_status_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        KnowledgeReviewStatus("rejected")  # type: ignore[arg-type]


def test_enum_persistence_stores_string_value(session: Session) -> None:
    """写入 enum 字段，DB 里存的是字符串值（D/C/B/A 等）而非枚举名。"""
    subj = Subject(name="高中物理", grade_level=GradeLevel.SENIOR_HIGH)
    session.add(subj)
    session.commit()

    raw = session.execute(
        sa.text("SELECT grade_level FROM subjects WHERE id = :id"), {"id": subj.id}
    ).scalar_one()
    assert raw == "senior_high"  # 字符串值，不是 "SENIOR_HIGH" 枚举名


def test_tier_persistence_stores_letter(session: Session, sample_class: Class) -> None:
    stu = Student(
        name="李雷",
        class_id=sample_class.id,
        grade_level=GradeLevel.JUNIOR_HIGH,
        current_tier=Tier.D,
    )
    session.add(stu)
    session.commit()

    raw = session.execute(
        sa.text("SELECT current_tier FROM students WHERE id = :id"), {"id": stu.id}
    ).scalar_one()
    assert raw == "D"


# ─────────────────────────── 3. 关系双向访问 ─────────────────────


def test_class_students_back_populates(sample_class: Class, sample_student: Student) -> None:
    """Class.students → Student 列表，反向 Student.class_ → Class。"""
    # sample_class fixture 已 expire(students)，下次访问会重发 SQL
    assert len(sample_class.students) == 1
    assert sample_class.students[0].id == sample_student.id
    assert sample_class.students[0].class_.id == sample_class.id


def test_subject_classes_back_populates(
    sample_subject: Subject, sample_class: Class
) -> None:
    # sample_subject fixture 自身创建时不依赖 sample_class，但 sample_class fixture
    # 已 expire(sample_subject, ["classes"])，下次访问重发 SQL
    assert len(sample_subject.classes) == 1
    assert sample_subject.classes[0].id == sample_class.id
    assert sample_subject.classes[0].subject.id == sample_subject.id


def test_student_knowledge_points_back_populates(
    session: Session, sample_student: Student
) -> None:
    """Student.knowledge_points ↔ StudentKnowledgePoint.student 双向。"""
    # 先建一个 chapter + KP
    textbook = Textbook(name="人教版数学七上", file_path="/data/textbooks/rjb-7s.pdf")
    session.add(textbook)
    session.flush()
    chapter = Chapter(textbook_id=textbook.id, chapter_number=1, title="有理数")
    session.add(chapter)
    session.flush()
    kp = KnowledgePoint(
        chapter_id=chapter.id,
        name="正负数概念",
        concept="正负数表示相反意义的量",
        teaching_order=1,
    )
    session.add(kp)
    session.flush()

    # 建关联
    skp = StudentKnowledgePoint(
        student_id=sample_student.id,
        knowledge_point_id=kp.id,
        mastery_score=0.85,
    )
    session.add(skp)
    session.commit()
    session.expire(sample_student, ["knowledge_points"])  # 让 SKP 可见
    session.refresh(kp, ["student_links"])

    # 反向访问：student.knowledge_points → list
    assert len(sample_student.knowledge_points) == 1
    assert sample_student.knowledge_points[0].mastery_score == pytest.approx(0.85)

    # 双向：StudentKnowledgePoint.student → Student
    skp_row = sample_student.knowledge_points[0]
    assert skp_row.student.id == sample_student.id

    # 反向：KnowledgePoint.student_links → list
    assert len(kp.student_links) == 1
    assert kp.student_links[0].student_id == sample_student.id


def test_chapter_relationships_cover_all_5_subtypes(session: Session) -> None:
    """Chapter 5 个子表全部双向访问通：KP / KeyPoint / Difficulty / TeachingSuggestion / Review。"""
    textbook = Textbook(name="人教版数学七上", file_path="/data/rjb-7s.pdf")
    session.add(textbook)
    session.flush()
    chapter = Chapter(textbook_id=textbook.id, chapter_number=2, title="整式")
    session.add(chapter)
    session.flush()

    kp1 = KnowledgePoint(chapter_id=chapter.id, name="单项式", concept="数字与字母乘积", teaching_order=1)
    kp2 = KnowledgePoint(chapter_id=chapter.id, name="多项式", concept="若干单项式之和", teaching_order=2)
    session.add_all([kp1, kp2])

    key = KeyPoint(chapter_id=chapter.id, content="理解同类项概念", source="teacher")
    diff = Difficulty(chapter_id=chapter.id, content="符号容易混淆", source="ai")
    sugg = TeachingSuggestion(chapter_id=chapter.id, content="用具体例子引入", source="ai")
    rev = KnowledgeReview(
        chapter_id=chapter.id, status=KnowledgeReviewStatus.PENDING, notes="AI 抽取待审"
    )
    session.add_all([key, diff, sugg, rev])
    session.commit()
    session.expire(chapter, ["knowledge_points", "key_points", "difficulties",
                              "teaching_suggestions", "reviews"])

    assert {kp.name for kp in chapter.knowledge_points} == {"单项式", "多项式"}
    assert len(chapter.key_points) == 1
    assert len(chapter.difficulties) == 1
    assert len(chapter.teaching_suggestions) == 1
    assert len(chapter.reviews) == 1

    # 反向：KeyPoint.chapter → Chapter
    assert chapter.key_points[0].chapter.id == chapter.id


# ─────────────────────────── 4. FK RESTRICT 行为 ─────────────────


def test_delete_class_with_students_raises_fk_error(
    session: Session, sample_class: Class, sample_student: Student
) -> None:
    """有 Student 的 Class 不能删（FK RESTRICT），预期抛 IntegrityError。

    必须依赖 sample_student fixture 让 student 真在 DB 里。
    """
    session.delete(sample_class)
    with pytest.raises(IntegrityError):
        session.flush()


def test_delete_subject_with_classes_raises_fk_error(
    session: Session, sample_subject: Subject, sample_class: Class
) -> None:
    """有 Class 的 Subject 不能删（FK RESTRICT）。"""
    session.delete(sample_subject)
    with pytest.raises(IntegrityError):
        session.flush()


def test_delete_empty_class_succeeds(session: Session, sample_subject: Subject) -> None:
    """没有 Student 的 Class 可以删（验证 RESTRICT 不是 blanket block）。"""
    empty = Class(
        name="空班级",
        grade_level=GradeLevel.JUNIOR_HIGH,
        subject_id=sample_subject.id,
    )
    session.add(empty)
    session.commit()
    cid = empty.id

    session.delete(empty)
    session.commit()

    assert session.get(Class, cid) is None


def test_delete_textbook_with_null_subject_succeeds(session: Session) -> None:
    """subject_id=NULL 的 Textbook 删除时不会牵动 Subject（验证 SET NULL 一侧无反向约束）。"""
    tb = Textbook(name="未归类教材", file_path="/tmp/orphan.pdf", subject_id=None)
    session.add(tb)
    session.commit()
    session.delete(tb)
    session.commit()


# ─────────────────────────── 5. 唯一约束 ─────────────────────────


def test_student_knowledge_point_unique_pair(
    session: Session, sample_student: Student
) -> None:
    """(student_id, knowledge_point_id) 唯一：同一对重复插入应失败。"""
    textbook = Textbook(name="人教版数学七上", file_path="/data/rjb-7s.pdf")
    session.add(textbook)
    session.flush()
    chapter = Chapter(textbook_id=textbook.id, chapter_number=1, title="有理数")
    session.add(chapter)
    session.flush()
    kp = KnowledgePoint(chapter_id=chapter.id, name="正负数", concept="...", teaching_order=1)
    session.add(kp)
    session.flush()

    skp1 = StudentKnowledgePoint(
        student_id=sample_student.id, knowledge_point_id=kp.id, mastery_score=0.5
    )
    session.add(skp1)
    session.commit()

    skp2 = StudentKnowledgePoint(
        student_id=sample_student.id, knowledge_point_id=kp.id, mastery_score=0.9
    )
    session.add(skp2)
    with pytest.raises(IntegrityError):
        session.flush()


def test_chapter_unique_textbook_chapter_number(session: Session) -> None:
    """(textbook_id, chapter_number) 唯一：同教材不能有两个 chapter_number=1。"""
    textbook = Textbook(name="人教版数学七上", file_path="/data/rjb-7s.pdf")
    session.add(textbook)
    session.flush()

    c1 = Chapter(textbook_id=textbook.id, chapter_number=1, title="第一章")
    session.add(c1)
    session.commit()

    c2 = Chapter(textbook_id=textbook.id, chapter_number=1, title="重复第一章")
    session.add(c2)
    with pytest.raises(IntegrityError):
        session.flush()


# ─────────────────────────── 6. KnowledgeReview 流转 ─────────────


def test_knowledge_review_status_transitions(session: Session) -> None:
    """pending → approved → modified（字段值切换，不触发 schema 迁移）。"""
    textbook = Textbook(name="教材", file_path="/x.pdf")
    session.add(textbook)
    session.flush()
    chapter = Chapter(textbook_id=textbook.id, chapter_number=1, title="ch1")
    session.add(chapter)
    session.flush()

    rev = KnowledgeReview(chapter_id=chapter.id, status=KnowledgeReviewStatus.PENDING)
    session.add(rev)
    session.commit()
    session.refresh(rev)

    assert rev.status is KnowledgeReviewStatus.PENDING
    assert rev.reviewed_at is None

    # pending → approved
    rev.status = KnowledgeReviewStatus.APPROVED
    rev.reviewed_by = "teacher@school.cn"
    rev.reviewed_at = datetime(2026, 9, 17, 12, 0, 0)
    session.commit()
    session.refresh(rev)
    assert rev.status is KnowledgeReviewStatus.APPROVED
    assert rev.reviewed_by == "teacher@school.cn"

    # approved → modified
    rev.status = KnowledgeReviewStatus.MODIFIED
    rev.notes = "补一条修改说明"
    session.commit()
    session.refresh(rev)
    assert rev.status is KnowledgeReviewStatus.MODIFIED
    assert rev.notes == "补一条修改说明"


# ─────────────────────────── 7. cascade all, delete-orphan ───────


def test_delete_student_cascades_to_skp(
    session: Session, sample_student: Student
) -> None:
    """Student 删除时，其 StudentKnowledgePoint 应被 cascade 清掉（ORM 级）。"""
    textbook = Textbook(name="教材", file_path="/x.pdf")
    session.add(textbook)
    session.flush()
    chapter = Chapter(textbook_id=textbook.id, chapter_number=1, title="ch1")
    session.add(chapter)
    session.flush()
    kp = KnowledgePoint(chapter_id=chapter.id, name="kp", concept="c", teaching_order=1)
    session.add(kp)
    session.flush()

    skp = StudentKnowledgePoint(student_id=sample_student.id, knowledge_point_id=kp.id)
    session.add(skp)
    session.commit()
    skp_id = skp.id

    # 让 sample_student.knowledge_points 重新加载，cascade 才能看到 skp
    session.expire(sample_student, ["knowledge_points"])

    session.delete(sample_student)
    session.commit()

    assert session.get(StudentKnowledgePoint, skp_id) is None


# ─────────────────────────── 8. alembic migration 文件 ───────────


def test_migration_module_importable() -> None:
    """0002 migration 文件本身可作为模块 import，暴露 upgrade/downgrade。"""
    # alembic.versions 不是 Python package（没 __init__.py），
    # 用 importlib.util 直接按文件路径加载。
    versions_dir = Path(__file__).resolve().parent.parent / "alembic" / "versions"
    migration_path = versions_dir / "0002_academic_models.py"
    assert migration_path.exists(), f"找不到 migration: {migration_path}"

    spec = importlib.util.spec_from_file_location(
        "alembic_version_0002_academic_models", str(migration_path)
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert hasattr(mod, "upgrade")
    assert hasattr(mod, "downgrade")
    assert mod.revision == "0002_academic_models"
    assert mod.down_revision == "0001_initial"
    assert callable(mod.upgrade)
    assert callable(mod.downgrade)


# ─────────────────────────── 9. PG round-trip（可选） ───────────


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="PG round-trip 需要 DATABASE_URL=postgresql+psycopg://...（环境变量未设置）",
)
def test_pg_alembic_upgrade_downgrade_round_trip() -> None:
    """真 PG 上跑 alembic upgrade head → 列出 11 表 → downgrade -1 → upgrade head。

    依赖外部 DATABASE_URL 指向 PG。CI / 决策室手动跑用。
    """
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

    # 先确保 baseline（PG 空库没有 alembic_version 时 down to base 会报错，吞掉）
    with contextlib.suppress(Exception):
        command.downgrade(cfg, "base")

    command.upgrade(cfg, "head")

    eng = create_engine(os.environ["DATABASE_URL"])
    insp = sa.inspect(eng)
    tables = set(insp.get_table_names())
    expected = {
        "subjects",
        "classes",
        "textbooks",
        "students",
        "chapters",
        "knowledge_points",
        "key_points",
        "difficulties",
        "teaching_suggestions",
        "knowledge_reviews",
        "student_knowledge_points",
        "alembic_version",
    }
    assert expected.issubset(tables), f"缺表：{expected - tables}"

    # round-trip：downgrade 然后 upgrade
    command.downgrade(cfg, "-1")
    command.upgrade(cfg, "head")

    tables_after = set(sa.inspect(eng).get_table_names())
    assert expected.issubset(tables_after)