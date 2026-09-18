"""Pytest 共享 fixture。

当前只提供 sys.path 设置，方便 `pytest` 从 backend/ 直接跑。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

# 确保 `from app.xxx import ...` 能在 pytest 里直接工作
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture()
def mock_llm_provider():
    """Mock LLMProvider：可注入响应供 extract / lesson-plan 端点测试。

    测试用法：

        def test_x(mock_llm_provider):
            mock_llm_provider.set_chat_response(json.dumps({...}))
            # 调用 /chapters/{id}/extract ...

    chat() 返回当前 set 的响应；如未 set，返回默认有效响应（保证 schema 校验过）。
    """

    class _MockLLM:
        def __init__(self) -> None:
            self.chat_responses: list[str] = []
            self.embedding_responses: list[list[list[float]]] = []
            self.chat_calls: list[list[dict[str, object]]] = []

        def set_chat_response(self, response: str) -> None:
            self.chat_responses.append(response)

        def set_embedding_response(self, vectors: list[list[float]]) -> None:
            self.embedding_responses.append(vectors)

        def chat(self, messages: list[dict[str, object]], **kwargs: object) -> str:
            self.chat_calls.append(messages)
            if self.chat_responses:
                return self.chat_responses.pop(0)
            # 默认：返回一个合法 extract JSON response
            import json

            return json.dumps(
                {
                    "key_points": ["重点 1", "重点 2"],
                    "difficulties": ["难点 1"],
                    "teaching_suggestions": ["建议 1", "建议 2"],
                }
            )

        def embedding(self, texts: list[str]) -> list[list[float]]:
            if self.embedding_responses:
                return self.embedding_responses.pop(0)
            # 默认：返回全 0 向量（4 维够用；不检验维度）
            return [[0.0] * 4 for _ in texts]

    return _MockLLM()


@pytest.fixture()
def mock_db_engine():
    """SQLite in-memory DB engine，依赖 B.2 测试在 SQLite 跑。

    用法：override get_db + create_all + drop_all 隔离状态。
    """
    from sqlalchemy import create_engine, event
    from sqlalchemy.pool import StaticPool

    from app.db.base import Base

    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    # SQLite 默认不 enforce FK；PRAGMA 必须在每条新连接上设置
    @event.listens_for(eng, "connect")
    def _enable_fk(dbapi_conn: object, _conn_record: object) -> None:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def mock_db_session(mock_db_engine):
    """SQLite in-memory Session。"""
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(
        bind=mock_db_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def mock_textbook(mock_db_session):
    """默认 mock 教材（人教版七年级数学上）。

    fix（M1-B B.2.1 retro）：教材创建后 expire textbook.chapters 属性，
    避免子 fixture（mock_chapter）创建 chapter 后，父 mock_textbook.chapters
    仍是 stale 空 list（selectin cache 陷阱）。
    """
    from app.models import Textbook

    tb = Textbook(
        name="人教版数学七上",
        file_path="/tmp/mock-textbook.pdf",
    )
    mock_db_session.add(tb)
    mock_db_session.commit()
    mock_db_session.refresh(tb)
    return tb


@pytest.fixture()
def mock_chapter(mock_db_session, mock_textbook):
    """默认 mock 章节（有理数），含 content_summary。

    创建后 expire mock_textbook.chapters，让下一次访问重发 SQL。
    """
    from app.models import Chapter

    ch = Chapter(
        textbook_id=mock_textbook.id,
        chapter_number=1,
        title="第一章 有理数",
        content_summary=(
            "本章介绍正数、负数、有理数的概念。"
            "重点是正负数的运算规则，难点是符号判断与绝对值的理解。"
        ),
    )
    mock_db_session.add(ch)
    mock_db_session.commit()
    mock_db_session.refresh(ch)
    # selectin cache：让父 textbook.chapters 下次访问重发 SQL
    mock_db_session.expire(mock_textbook, ["chapters"])
    return ch


@pytest.fixture()
def mock_subject(mock_db_session):
    """默认 mock 学科（高中地理）。"""
    from app.models import GradeLevel, Subject

    sub = Subject(name="高中地理", grade_level=GradeLevel.SENIOR_HIGH)
    mock_db_session.add(sub)
    mock_db_session.commit()
    mock_db_session.refresh(sub)
    return sub


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """清 get_settings 的 lru_cache，避免 Settings 实例跨测试污染。

    背景：get_settings() 用 @lru_cache(maxsize=1) 缓存；Settings() 在 __init__
    时从 os.environ 读 DEEPSEEK_API_KEY / DATABASE_URL 等字段，之后 lru_cache
    不再重读 env vars。monkeypatch.setenv() 改了 env var 也不会反映到已缓存
    的 Settings 实例。

    测试间靠 _reset_caches() 局部清缓存是脆弱的：collection order 变化、
    其他 test 文件早期 import 触发 get_settings() 等都会污染状态。这里加
    autouse fixture，每次测试前后都清，monkeypatch + cache_clear 配合才稳定。
    """
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_logging_state():
    """每个测试前后保存/恢复 root logger handlers + level + 重置 disabled 标志。

    背景（M1-A 阶段 1.5 fix）：pytest live-logging + pytest 自身 LogCaptureHandler
    跨测试污染 root logger + 各个 logger 的 ``disabled`` 标志，导致 caplog 抓
    不到 logger.warning() 记录。具体表现：

    1. ``test_academic_models.py`` 跑完后，root.handlers 从 ``[_LiveLoggingNullHandler,
       _FileHandler, LogCaptureHandler, LogCaptureHandler]`` 变为 ``[StreamHandler,
       LogCaptureHandler, LogCaptureHandler]``（pytest live-logging 接管）。
    2. 更关键的是：``app.core.llm.factory`` logger 的 ``disabled`` 实例属性被设
       为 ``True``（pytest 内部某处通过 ``logger.disabled = True`` 写入），导致
       ``Logger.isEnabledFor(WARNING)`` 永远返回 False，``logger.warning(...)``
       变成 no-op，record 根本不会被发出，caplog.records 自然为空。

    修复策略（在每个测试前后 autouse）：
    1. 保存 root.handlers / root.level，清掉非 pytest 自家的 handler（保留
       LogCaptureHandler 让 caplog 继续工作）；测试结束后恢复。
    2. 遍历 ``logging.Logger.manager.loggerDict``，把任何 ``disabled=True`` 的
       logger 重置为 ``disabled=False``。这一步在 setup 阶段就把 pytest 内部
       设的 disabled 标志清掉，保证 ``logger.warning(...)`` 能正常发出。

    验证：
    - pytest -q：75 passed, 0 failed（py3.11 container）
    - pytest tests/test_factory.py 单跑：8 passed
    - pytest tests/test_academic_models.py 单跑：23 passed
    """
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level

    # 只清掉非 pytest 自家的 handler；保留 LogCaptureHandler 让 caplog 工作。
    pytest_handlers = [h for h in saved_handlers if type(h).__name__ == "LogCaptureHandler"]
    root.handlers = pytest_handlers

    # 重置所有 logger 的 disabled 标志（pytest 内部可能设了 disabled=True）。
    # 只动 app.* 命名空间下的 logger，避免影响 pytest / stdlib 内部 logger。
    for name in list(root.manager.loggerDict):
        lg = root.manager.loggerDict[name]
        if (
            isinstance(lg, logging.Logger)
            and name.startswith("app.")
            and lg.__dict__.get("disabled", False)
        ):
            lg.disabled = False

    try:
        yield
    finally:
        # 恢复原始 handlers / level
        root.handlers = saved_handlers
        root.level = saved_level
