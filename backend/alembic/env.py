"""Alembic env 配置。

支持从 app.core.config.get_settings() 读取 DATABASE_URL，方便环境切换。

# v0.5 M1-A 阶段 1 加的 judgment（§1.3）：
# - compare_type=True：autogenerate 时识别 enum / column 类型变化
# - render_as_batch=False：PG 不需要 batch mode（batch 是 SQLite ALTER TABLE 用）
# - PG native enum 在 migration 里显式 create_type / drop_type，避免
#   同一 enum 类型在多个 migration 里被重复创建（sa.Enum 加 create_type=False
#   是 ORM model 层的标准做法，env.py 不再干预；migration 层每个 enum 独立
#   控制 create_type 即可）。
"""

from __future__ import annotations

# 把项目根加进 sys.path
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import models  # noqa: E402,F401  # 注册所有 model 到 Base.metadata
from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402

config = context.config

# 用 settings 覆盖 alembic.ini 里的 url
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：输出 SQL 不连库。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=False,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连库执行 migration。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=False,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()