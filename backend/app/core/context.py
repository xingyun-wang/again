"""Request-scoped context（contextvar）。

放这里是为了避免 logging.py / errors.py / middleware.py 之间的循环导入：
- middleware.py 设值
- logging.py / errors.py 读值
"""

from __future__ import annotations

from contextvars import ContextVar

# 每个 HTTP 请求一个唯一 id（uuid4().hex）。
# 默认 None 表示"非请求上下文"（例如 startup 阶段、后台任务）。
request_id_contextvar: ContextVar[str | None] = ContextVar("request_id", default=None)