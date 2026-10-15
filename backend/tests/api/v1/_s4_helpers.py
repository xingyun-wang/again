"""S4 PDF 导出测试 helpers (per 复核员 B11; 避免双导入 + 路径污染).

复用 test_assignment_review.py 既有 API:
- _create_assignment_pending(client, chapter_id, user_id=1) -> int
- _create_assignment_approved(client, mock_db_session, chapter_id, user_id=1) -> int
- chapter_with_questions fixture

抽到这里 = 单一真值源 (D-43 决策室 决策);
s4 工单不动 test_assignment_review.py (避免跨工单污染)。
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.routers.assignments import router as assignments_router
from app.db.session import get_db
from tests.api.v1.test_assignment_review import (  # noqa: F401  复用既有
    _create_assignment_approved,
    _create_assignment_pending,
    chapter_with_questions,
)


def make_test_client(mock_db_session: Session) -> TestClient:
    """建 TestClient + dependency_overrides get_db.

    严格照抄 test_assignment_review.py:62-70 既有模式 (per 复核员 A8):
    必须用 generator function (yield), 不能 lambda: iter([...])
    (iter([...]) 返回迭代器对象, FastAPI 不会解包; 端点里 db = list_iterator ⇒ AttributeError).
    """
    app = FastAPI()

    def _override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.include_router(assignments_router, prefix="/api/v1")
    return TestClient(app)
