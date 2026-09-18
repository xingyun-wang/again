"""统一日志配置（M0 retro #3 基建）。

- configure_logging() 由 lifespan 在启动时调用一次
- 生产环境（APP_ENV=production）：JSON 格式（手写 JsonFormatter，不引入 python-json-logger）
- 开发环境（APP_ENV=development / staging）：纯文本格式
- 日志级别从 settings.log_level 读（默认 INFO）
- 自动注入 request_id（从 request_id_contextvar 读取）

格式约定：
- JSON：{"timestamp","level","logger","message"[,"exception"][,"request_id"]}
- Plain：2026-09-17 12:34:56 [INFO] app.api.health: ...
"""

from __future__ import annotations

import json
import logging
import logging.config

from app.core.config import get_settings

# LogRecord 自带的内部字段，避免在 extra 中重复出现
_STANDARD_LOGRECORD_FIELDS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "asctime",
        "taskName",
    }
)


class PlainFormatter(logging.Formatter):
    """纯文本格式化器（开发模式）。"""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


class JsonFormatter(logging.Formatter):
    """JSON 格式化器（生产模式）。

    输出字段：
    - timestamp（ISO-ish，本地时区）
    - level（INFO/WARNING/...）
    - logger（logger 名）
    - message（已格式化好的文本）
    - exception（异常 traceback，若有）
    - request_id（从 contextvar 读取，若有）

    用户通过 logger.info("...", extra={"foo": ...}) 传入的额外字段也会被带上。
    """

    def __init__(self) -> None:
        super().__init__(datefmt="%Y-%m-%d %H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        # 延迟导入避免模块加载循环（logging.py 可能被早期模块触发）
        from app.core.context import request_id_contextvar

        log_data: dict[str, object] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        # 注入 request_id（如果 RequestIDMiddleware 已设）
        try:
            rid = request_id_contextvar.get()
        except LookupError:
            rid = None
        if rid:
            log_data["request_id"] = rid
        # 注入用户自定义 extras
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOGRECORD_FIELDS and not key.startswith("_"):
                log_data[key] = value
        return json.dumps(log_data, default=str, ensure_ascii=False)


def configure_logging() -> None:
    """根据 settings 配置 root logger。

    由 lifespan 在启动时调用一次。重复调用会覆盖已有配置。
    """
    settings = get_settings()
    level_name = settings.log_level.upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        level = logging.INFO

    env = settings.app_env.lower()
    if env == "production":
        formatter_class = "app.core.logging.JsonFormatter"
    else:
        formatter_class = "app.core.logging.PlainFormatter"

    config: dict[str, object] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": formatter_class,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stderr",
            },
        },
        "root": {
            "handlers": ["console"],
            "level": level,
        },
    }
    logging.config.dictConfig(config)