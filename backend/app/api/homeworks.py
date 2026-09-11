"""作业生成 API — W3-T4（W3 核心）。

端点：
    POST /api/classes/{class_id}/homeworks/generate

设计：
- 老师指定每档题数（D-W3-02）
- 反马太 D 档 20% 拔高（D-W3-03 实时计算）
- 章节可选过滤（None = 全 5 章）
- 题库不足 → 422 明确报错
- teacher_id / class_id MVP body 传入（TODO W5+ 改 session 注入）

V0.1 限制：
- 不做老师审阅 / 手动调整档位（W3-T5）
- 不做作业发布 / PDF 导出（W4+）
- 不做学生端（W5+）
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Chapter, Homework, HomeworkQuestion, HomeworkStatus, Level, Question, Teacher, Class
from ..schemas import (
    HomeworkListOut,
    HomeworkOut,
    HomeworkQuestionOut,
    HomeworkQuestionUpdate,
    HomeworkReviewRequest,
    HomeworkStatusEnum,
)
from ..services.anti_matthew import anti_matthew_substitute


router = APIRouter(prefix="/api", tags=["homeworks"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============ Request / Response schema ============

class HomeworkGenerateRequest(BaseModel):
    """作业生成请求体（W3-T4）。

    teacher_id MVP body 传入 + TODO(W5+) 改 session 注入。
    questions_per_level 按 D/C/B/A 顺序不强制（dict），但只识别 D/C/B/A 4 个 key。
    chapters 可选；None = 全 5 章。
    anti_matthew 默认 True（CHARTER §4 反马太硬约束）。
    """
    teacher_id: int
    title: str = Field(min_length=1, max_length=200)
    questions_per_level: Dict[str, int]
    chapters: Optional[List[str]] = None
    anti_matthew: bool = True


class HomeworkGenerateResponse(BaseModel):
    """作业生成响应。

    homework: HomeworkOut（含 questions 关联列表）
    warnings: 反马太 warning（C 档不足等）
    """
    homework: HomeworkOut
    warnings: List[str] = []


# ============ Helpers ============

def _check_teacher_or_404(db: Session, teacher_id: int) -> None:
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"teacher_id={teacher_id} 不存在",
        )


def _check_class_or_404(db: Session, class_id: int) -> None:
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"class_id={class_id} 不存在",
        )


def _fetch_questions_per_level(
    db: Session,
    class_id: int,
    questions_per_level: Dict[str, int],
    chapters: Optional[List[str]],
) -> Dict[str, list]:
    """按档位抽题。

    返回 {"D": [...], "C": [...], "B": [...], "A": [...]}
    任一档不足 → 422 报错（含明确信息）

    注：MVP 不按 teacher 过滤（题库共享），V0.2 可加 teacher_id 过滤。
    """
    LEVELS = ["D", "C", "B", "A"]
    out = {}

    for lv in LEVELS:
        need = questions_per_level.get(lv, 0)
        if need <= 0:
            out[lv] = []
            continue

        q = db.query(Question).filter(Question.level == lv)
        if chapters:
            q = q.filter(Question.chapter.in_(chapters))

        available = q.count()
        if available < need:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"{lv} 档题库不足：需要 {need} 道，实际可用 {available} 道"
                    + (f"（限定章节 {chapters}）" if chapters else "")
                ),
            )

        out[lv] = q.order_by(Question.id).limit(need).all()

    return out


# ============ POST /api/classes/{class_id}/homeworks/generate ============

@router.post(
    "/classes/{class_id}/homeworks/generate",
    response_model=HomeworkGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_homework(
    class_id: int,
    payload: HomeworkGenerateRequest,
    db: Session = Depends(get_db),
):
    """作业生成（核心：反马太 D 档 20% 拔高）。

    流程：
    1. 校验 class_id / teacher_id 存在
    2. 按档位抽题（任一不足 → 422）
    3. D 档走反马太算法（如 anti_matthew=true）
    4. 合并所有档位的题 → 按 level 顺序（D, C, B, A）拼成 HomeworkQuestion 列表
    5. 写 Homework(status=GENERATED, generated_at=now) + HomeworkQuestion(position 1..N)
    6. 返回 HomeworkOut + warnings
    """
    # TODO(W5+): teacher_id 不接受 body 传入；从 session 注入；越权 → 403
    _check_teacher_or_404(db, payload.teacher_id)
    _check_class_or_404(db, class_id)

    # Step 1: 按档位抽题
    qpool = _fetch_questions_per_level(
        db, class_id, payload.questions_per_level, payload.chapters
    )

    # Step 2: 反马太处理（D 档）
    #   关键：反马太需要的 C 档题池不受请求档位题数限制（questions_per_level["C"] 可以是 0）
    #   反马太从全库抽 C 档题，优先按章节过滤（与 D 档同步）
    warnings: List[str] = []
    d_combined: list = []  # [(Question, current_level), ...]
    if payload.anti_matthew and qpool.get("D"):
        # 反马太专用：从全库抽 C 档题池
        c_pool_query = db.query(Question).filter(Question.level == Level.C.value)
        if payload.chapters:
            c_pool_query = c_pool_query.filter(Question.chapter.in_(payload.chapters))
        c_pool = c_pool_query.all()

        d_combined, warnings = anti_matthew_substitute(
            d_questions=qpool["D"],
            c_questions=c_pool,
        )
    else:
        d_combined = [(q, "D") for q in qpool.get("D", [])]

    # Step 3: 合并所有档位的题 → 按 D / C / B / A 顺序
    combined: list = []
    combined.extend(d_combined)
    combined.extend([(q, "C") for q in qpool.get("C", [])])
    combined.extend([(q, "B") for q in qpool.get("B", [])])
    combined.extend([(q, "A") for q in qpool.get("A", [])])

    if not combined:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="作业生成失败：所有档位题数都为 0",
        )

    # Step 4: 写 Homework + HomeworkQuestion
    hw = Homework(
        class_id=class_id,
        teacher_id=payload.teacher_id,
        title=payload.title,
        status=HomeworkStatus.GENERATED.value,
        generated_at=datetime.utcnow(),
    )
    db.add(hw)
    db.flush()  # 拿到 hw.id

    for position, (question, current_level) in enumerate(combined, start=1):
        hq = HomeworkQuestion(
            homework_id=hw.id,
            question_id=question.id,
            level=current_level,
            position=position,
        )
        db.add(hq)

    db.commit()
    db.refresh(hw)

    # Step 5: 转 HomeworkOut（含 questions 关联）
    out_questions = [
        HomeworkQuestionOut(
            id=hq.id,
            question_id=hq.question_id,
            level=hq.level,
            position=hq.position,
        )
        for hq in sorted(hw.questions, key=lambda x: x.position)
    ]

    homework_out = HomeworkOut(
        id=hw.id,
        class_id=hw.class_id,
        teacher_id=hw.teacher_id,
        title=hw.title,
        status=HomeworkStatusEnum(hw.status),
        generated_at=hw.generated_at,
        reviewed_at=hw.reviewed_at,
        published_at=hw.published_at,
        questions=out_questions,
    )

    return HomeworkGenerateResponse(homework=homework_out, warnings=warnings)


# ============ GET /api/homeworks/{id} ============

@router.get(
    "/homeworks/{hw_id}",
    response_model=HomeworkOut,
)
def get_homework(hw_id: int, db: Session = Depends(get_db)):
    """作业详情（含 questions 关联列表，按 position 升序）。"""
    hw = db.query(Homework).filter(Homework.id == hw_id).first()
    if not hw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"homework_id={hw_id} 不存在",
        )

    out_questions = [
        HomeworkQuestionOut(
            id=hq.id,
            question_id=hq.question_id,
            level=hq.level,
            position=hq.position,
        )
        for hq in sorted(hw.questions, key=lambda x: x.position)
    ]

    return HomeworkOut(
        id=hw.id,
        class_id=hw.class_id,
        teacher_id=hw.teacher_id,
        title=hw.title,
        status=HomeworkStatusEnum(hw.status),
        generated_at=hw.generated_at,
        reviewed_at=hw.reviewed_at,
        published_at=hw.published_at,
        questions=out_questions,
    )


# ============ GET /api/classes/{class_id}/homeworks ============

@router.get(
    "/classes/{class_id}/homeworks",
    response_model=List[HomeworkListOut],
)
def list_class_homeworks(
    class_id: int,
    status_filter: Optional[HomeworkStatusEnum] = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    """列作业（可选按 status 过滤）。

    返回轻量列表（不嵌 questions）+ question_count（SQL count）。
    """
    _check_class_or_404(db, class_id)

    query = db.query(Homework).filter(Homework.class_id == class_id)
    if status_filter is not None:
        query = query.filter(Homework.status == status_filter.value)

    out = []
    for hw in query.order_by(Homework.id.desc()).all():
        q_count = db.query(HomeworkQuestion).filter(
            HomeworkQuestion.homework_id == hw.id
        ).count()
        out.append(HomeworkListOut(
            id=hw.id,
            class_id=hw.class_id,
            teacher_id=hw.teacher_id,
            title=hw.title,
            status=HomeworkStatusEnum(hw.status),
            generated_at=hw.generated_at,
            reviewed_at=hw.reviewed_at,
            published_at=hw.published_at,
            question_count=q_count,
        ))
    return out


# ============ POST /api/homeworks/{id}/review ============

@router.post(
    "/homeworks/{hw_id}/review",
    response_model=HomeworkOut,
)
def review_homework(
    hw_id: int,
    payload: HomeworkReviewRequest,
    db: Session = Depends(get_db),
):
    """老师审阅 + 手动调整档位。

    流程：
    1. 校验作业存在
    2. 校验 status 必须是 GENERATED 或 REVIEWED（不能从 DRAFT 直接审，也不能从 PUBLISHED 改）
    3. 按 homework_question_id 找到每条 HomeworkQuestion，更新 level
    4. status → REVIEWED + reviewed_at = now
    5. 写库 + 返回 HomeworkOut

    设计决策（D-W3-03）：不自动重算反马太——老师手动调整是最终判断。
    """
    hw = db.query(Homework).filter(Homework.id == hw_id).first()
    if not hw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"homework_id={hw_id} 不存在",
        )

    if hw.status not in (HomeworkStatus.GENERATED.value, HomeworkStatus.REVIEWED.value):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"作业状态 {hw.status} 不允许审阅（需 GENERATED 或 REVIEWED）",
        )

    # 校验每条 homework_question_id 都属于这个 hw
    hq_ids_in_hw = {hq.id for hq in hw.questions}
    for upd in payload.questions:
        if upd.homework_question_id not in hq_ids_in_hw:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"homework_question_id={upd.homework_question_id} 不属于作业 {hw_id}",
            )

    # 按 id 找 HomeworkQuestion + 更新 level
    hq_by_id = {hq.id: hq for hq in hw.questions}
    for upd in payload.questions:
        hq = hq_by_id[upd.homework_question_id]
        hq.level = upd.new_level.value if hasattr(upd.new_level, "value") else upd.new_level

    hw.status = HomeworkStatus.REVIEWED.value
    hw.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(hw)

    out_questions = [
        HomeworkQuestionOut(
            id=hq.id,
            question_id=hq.question_id,
            level=hq.level,
            position=hq.position,
        )
        for hq in sorted(hw.questions, key=lambda x: x.position)
    ]

    return HomeworkOut(
        id=hw.id,
        class_id=hw.class_id,
        teacher_id=hw.teacher_id,
        title=hw.title,
        status=HomeworkStatusEnum(hw.status),
        generated_at=hw.generated_at,
        reviewed_at=hw.reviewed_at,
        published_at=hw.published_at,
        questions=out_questions,
    )


# ============ POST /api/homeworks/{id}/publish ============

@router.post(
    "/homeworks/{hw_id}/publish",
    response_model=HomeworkOut,
)
def publish_homework(hw_id: int, db: Session = Depends(get_db)):
    """发布作业（仅 REVIEWED 状态可发布）。

    流程：
    1. 校验作业存在
    2. 校验 status == REVIEWED（不能从 GENERATED 直接 publish；必须先审阅）
    3. status → PUBLISHED + published_at = now
    """
    hw = db.query(Homework).filter(Homework.id == hw_id).first()
    if not hw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"homework_id={hw_id} 不存在",
        )

    if hw.status != HomeworkStatus.REVIEWED.value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"作业状态 {hw.status} 不允许发布（需 REVIEWED）",
        )

    hw.status = HomeworkStatus.PUBLISHED.value
    hw.published_at = datetime.utcnow()
    db.commit()
    db.refresh(hw)

    out_questions = [
        HomeworkQuestionOut(
            id=hq.id,
            question_id=hq.question_id,
            level=hq.level,
            position=hq.position,
        )
        for hq in sorted(hw.questions, key=lambda x: x.position)
    ]

    return HomeworkOut(
        id=hw.id,
        class_id=hw.class_id,
        teacher_id=hw.teacher_id,
        title=hw.title,
        status=HomeworkStatusEnum(hw.status),
        generated_at=hw.generated_at,
        reviewed_at=hw.reviewed_at,
        published_at=hw.published_at,
        questions=out_questions,
    )
