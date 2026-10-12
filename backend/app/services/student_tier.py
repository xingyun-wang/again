"""Student tier 服务（M2-S2 brief §七）。

manual override service：老师手动改 Student.current_tier + 写 audit 字段。

设计要点：
- 链路校验：Student → Class → Subject → owner_user_id（M2-S2 brief §4.1）
  走 ``Subject.owner_user_id`` 而非 ``Class.owner_user_id``（Class 表无
  owner_user_id 字段；归属链最长但可避免给 Class 加冗余字段）。
- 跨用户隔离：调 ``_enforce_owner_or_404(subject, current_user_id)``，
  越权返 404（D-29 B 项 + D-37 fail-open 可证伪）。
- audit 字段：tier_changed_by_user_id + tier_changed_at 同步写入（迁移
  0009 加的 2 字段）；既存 Student 行这两字段可能 NULL（历史未追踪）。
- 异常统一为 HTTPException：与 router 层一致；service 层也抛 HTTPException
  是因为本服务是 router 的直接依赖（不是泛 service）。
- new_tier 校验：调用方负责（Pydantic schema Literal["D","C","B","A"]）
  ；service 层仍 isinstance 检查兜底（防 service 被非 router 调用时漏校验）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypedDict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.deps import _enforce_owner_or_404
from app.models import Student, Subject, Tier


class TierOverrideResult(TypedDict):
    """override_student_tier 返回契约（TypedDict；M2-S2 brief §七）。

    显式 TypedDict 替代 dict[str, object] — 避免 router 层取值时类型宽到
    object（mypy 报错）= 给下游类型契约。
    """

    old: Tier
    new: Tier
    student_id: int
    tier_changed_by_user_id: int
    tier_changed_at: datetime


def override_student_tier(
    session: Session,
    current_user_id: int,
    student_id: int,
    new_tier: Tier,
) -> TierOverrideResult:
    """手动覆盖学生档位 + 写 audit 字段（M2-S2 brief §七）。

    链路：Student → Class → Subject → owner_user_id 校验。
    改 current_tier + 同步写 audit 字段（tier_changed_by_user_id /
    tier_changed_at）；session.commit() 落库。

    Args:
        session: SQLAlchemy Session（router 层 Depends(get_db) 注入）
        current_user_id: 当前请求 user_id（X-User-Id header 解析）
        student_id: 目标 Student.id
        new_tier: 新档位（Tier enum；调用方负责 D/C/B/A 范围）

    Returns:
        dict: ``{"old": Tier, "new": Tier, "student_id": int,
                  "tier_changed_by_user_id": int, "tier_changed_at": datetime}``

    Raises:
        HTTPException 404: student 不存在 / 跨用户隔离
        HTTPException 422: new_tier 非 Tier enum（service 层兜底）
    """
    if not isinstance(new_tier, Tier):
        raise HTTPException(
            status_code=422,
            detail=f"new_tier 必须是 Tier enum（D/C/B/A）；got {type(new_tier).__name__}",
        )

    student = session.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail=f"student {student_id} 不存在")

    # 链路校验：Student → Class → Subject → owner_user_id
    # selectin 已 lazy load class_ + subject（Student.class_.subject），无需手动 JOIN
    subject: Subject = student.class_.subject
    _enforce_owner_or_404(subject, current_user_id)

    old_tier = student.current_tier
    student.current_tier = new_tier
    student.tier_changed_by_user_id = current_user_id
    student.tier_changed_at = datetime.now(UTC)
    session.commit()
    session.refresh(student)

    return {
        "old": old_tier,
        "new": new_tier,
        "student_id": student_id,
        "tier_changed_by_user_id": current_user_id,
        "tier_changed_at": student.tier_changed_at,
    }
