"""Question CRUD API — W3-T2。

6 个端点：
    POST   /api/questions                              body: QuestionCreate → 创建
    GET    /api/questions                              query: chapter, level, question_type, teacher_id
    GET    /api/questions/{id}                         单题详情（answer 多选反序列化为 list）
    PUT    /api/questions/{id}                         body: QuestionUpdate → 更新（局部）
    DELETE /api/questions/{id}                         删除（再 GET 404）
    GET    /api/teachers/{teacher_id}/questions        按老师列出（含 chapter/level 过滤）

设计要点：
- answer 出参按 question_type 反序列化（坑 #1）— QuestionOut model_validator 处理
- Question.teacher relationship 已在 models.py 补全（坑 #2）
- teacher_id MVP 接受 body 传入 + TODO(W5+) 注释（坑 #3，CHARTER §6 越权风险，auth 阶段改 session 注入）
- 不做的：搜索 / 全文索引 / 批量导入 / 主观题（V0.1 越界禁止）
"""
from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Chapter, Level, Question, QuestionType, Teacher
from ..schemas import QuestionCreate, QuestionOut, QuestionUpdate


router = APIRouter(prefix="/api", tags=["questions"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============ Helpers ============

def _get_question_or_404(db: Session, qid: int) -> Question:
    q = db.query(Question).filter(Question.id == qid).first()
    if not q:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"question_id={qid} 不存在",
        )
    return q


def _check_teacher_or_404(db: Session, teacher_id: int) -> None:
    """teacher_id 必须指向已存在老师，否则 404（避免 FK 抛裸 IntegrityError）。"""
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"teacher_id={teacher_id} 不存在",
        )


def _validate_answer_for_type(answer: str, qtype: QuestionType) -> None:
    """业务校验：answer 格式必须与 question_type 匹配。

    - single_choice / true_false：answer 必须 ∈ options（按值匹配）
    - multiple_choice：answer 必须是 JSON 数组字符串，且每个元素 ∈ options
    """
    # 此函数只在创建/更新时调用，options 必传，所以 caller 已经在 payload 里拿到 options。
    raise NotImplementedError  # caller 内联实现（需要 options 上下文）


# ============ POST /api/questions ============

@router.post(
    "/questions",
    response_model=QuestionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_question(payload: QuestionCreate, db: Session = Depends(get_db)):
    """创建题目。

    MVP 妥协：teacher_id 接受 body 传入（W5+ auth 阶段改为从 session 注入）。
    校验：
    - teacher_id 必须存在 → 404
    - answer 格式按 question_type 校验（options 内存在性）
    """
    # TODO(W5+): teacher_id 不接受 body 传入；从当前 session/当前老师注入；越权请求 → 403
    _check_teacher_or_404(db, payload.teacher_id)

    # 业务校验：answer ∈ options（按值匹配，兼容中文 option label）
    if payload.question_type in (QuestionType.SINGLE_CHOICE, QuestionType.TRUE_FALSE):
        if payload.answer not in payload.options:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"{payload.question_type.value} 的 answer {payload.answer!r} "
                    f"必须在 options {payload.options} 内"
                ),
            )
    elif payload.question_type == QuestionType.MULTIPLE_CHOICE:
        stripped = payload.answer.strip()
        if not (stripped.startswith("[") and stripped.endswith("]")):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="multiple_choice 的 answer 必须是 JSON 数组字符串，如 '[\"A\",\"C\"]'",
            )
        try:
            parsed = json.loads(payload.answer)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"multiple_choice 的 answer JSON 解析失败: {e}",
            )
        if not isinstance(parsed, list) or not all(isinstance(x, str) for x in parsed):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="multiple_choice 的 answer 必须是字符串数组",
            )
        invalid = [x for x in parsed if x not in payload.options]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"multiple_choice 的 answer 元素 {invalid} 不在 options {payload.options} 内",
            )

    q = Question(
        content=payload.content,
        options=payload.options,
        answer=payload.answer,
        question_type=payload.question_type,
        level=payload.level,
        chapter=payload.chapter,
        teacher_id=payload.teacher_id,
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


# ============ GET /api/questions ============

@router.get("/questions", response_model=List[QuestionOut])
def list_questions(
    chapter: Optional[Chapter] = Query(None),
    level: Optional[Level] = Query(None),
    question_type: Optional[QuestionType] = Query(None),
    teacher_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """列出题目（按 id 升序）。支持 chapter / level / question_type / teacher_id 过滤。

    过滤器均 optional，未传则不应用。所有过滤可叠加（AND 关系）。
    """
    query = db.query(Question)
    if chapter is not None:
        query = query.filter(Question.chapter == chapter)
    if level is not None:
        query = query.filter(Question.level == level)
    if question_type is not None:
        query = query.filter(Question.question_type == question_type)
    if teacher_id is not None:
        query = query.filter(Question.teacher_id == teacher_id)
    return query.order_by(Question.id).all()


# ============ GET /api/questions/{id} ============

@router.get("/questions/{qid}", response_model=QuestionOut)
def get_question(qid: int, db: Session = Depends(get_db)):
    """单题详情。多选 answer 在出参反序列化为 list[str]（QuestionOut.model_validator 处理）。"""
    return _get_question_or_404(db, qid)


# ============ PUT /api/questions/{id} ============

@router.put("/questions/{qid}", response_model=QuestionOut)
def update_question(
    qid: int,
    payload: QuestionUpdate,
    db: Session = Depends(get_db),
):
    """更新题目（局部更新：所有字段 optional）。

    校验：
    - 题目不存在 → 404
    - 如果同时改 answer 和 options：answer 必须仍在（新的）options 内
    - 只改 answer 不改 options：answer 必须仍在当前 options 内
    - 只改 options 不改 answer：answer 必须仍在新的 options 内（防止改选项漏掉旧答案）
    """
    q = _get_question_or_404(db, qid)

    new_content = payload.content if payload.content is not None else q.content
    new_options = payload.options if payload.options is not None else q.options
    new_answer = payload.answer if payload.answer is not None else q.answer

    # 业务校验：answer 必须 ∈ options（按现有 question_type 推断）
    # 注：MVP 不允许通过 PUT 改 question_type（QuestionUpdate 未暴露该字段），
    # 所以校验逻辑直接按 q.question_type 走。
    if q.question_type in (QuestionType.SINGLE_CHOICE, QuestionType.TRUE_FALSE):
        if new_answer not in new_options:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"answer {new_answer!r} 必须在 options {new_options} 内",
            )
    elif q.question_type == QuestionType.MULTIPLE_CHOICE:
        try:
            parsed = json.loads(new_answer)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"multiple_choice 的 answer JSON 解析失败: {e}",
            )
        if not isinstance(parsed, list) or not all(isinstance(x, str) for x in parsed):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="multiple_choice 的 answer 必须是字符串数组",
            )
        invalid = [x for x in parsed if x not in new_options]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"answer 元素 {invalid} 不在 options {new_options} 内",
            )

    q.content = new_content
    q.options = new_options
    q.answer = new_answer
    db.commit()
    db.refresh(q)
    return q


# ============ DELETE /api/questions/{id} ============

@router.delete("/questions/{qid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(qid: int, db: Session = Depends(get_db)):
    """删除题目。题目不存在 → 404。"""
    q = _get_question_or_404(db, qid)
    db.delete(q)
    db.commit()
    return None


# ============ GET /api/teachers/{teacher_id}/questions ============

@router.get(
    "/teachers/{teacher_id}/questions",
    response_model=List[QuestionOut],
)
def list_teacher_questions(
    teacher_id: int,
    chapter: Optional[Chapter] = Query(None),
    level: Optional[Level] = Query(None),
    db: Session = Depends(get_db),
):
    """按老师列出题目（含 chapter / level 过滤）。

    用途：老师管理自己题库的入口；MVP 阶段无 auth，老师 ID 来自路径。
    """
    _check_teacher_or_404(db, teacher_id)
    query = db.query(Question).filter(Question.teacher_id == teacher_id)
    if chapter is not None:
        query = query.filter(Question.chapter == chapter)
    if level is not None:
        query = query.filter(Question.level == level)
    return query.order_by(Question.id).all()
