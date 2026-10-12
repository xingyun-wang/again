"""共享 API dependencies（跨 router 复用的工具）。

M2-S2 实施（D-82 后）把 ``_enforce_owner_or_404`` 从 routers/academic.py 抽出
到本模块，让 students router 也能复用。学术 / 作业 / 学生 三个 router 都依赖
同一个跨用户隔离 helper = 唯一真值源（D-79 家族）。

D-37 负面测试 fixture（conftest.py:355-390）仍可 monkeypatch 本模块的属性
（已同步更新 monkeypatch target 从 ``app.api.v1.routers.academic`` 改为
``app.api.deps``）。
"""

from __future__ import annotations

from fastapi import HTTPException

_NOT_OWNER_DETAIL = "该资源不属于当前用户"


def _enforce_owner_or_404(obj: object, user_id: int) -> None:
    """跨用户隔离硬门槛（D-29 B 项）。

    检查 obj.owner_user_id != user_id → 404（不是 403）。
    错误体统一为「该资源不属于当前用户」，避免泄漏 id 是否存在。

    Args:
        obj: 任意带 ``owner_user_id`` 属性的 ORM 实例（Subject / Textbook / Chapter / Student / ...）
        user_id: 当前请求的 user_id（X-User-Id header）

    Raises:
        HTTPException 404: obj.owner_user_id != user_id
    """
    owner_id = getattr(obj, "owner_user_id", None)
    if owner_id is None or owner_id != user_id:
        raise HTTPException(status_code=404, detail=_NOT_OWNER_DETAIL)
