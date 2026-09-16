"""应用配置（pydantic-settings）。

环境变量集中管理，类型安全，方便测试和部署。
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用设置。读取优先级：环境变量 > .env > 默认值。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用
    app_name: str = Field(default="tiered-homework-backend", description="应用名")
    app_version: str = Field(default="0.1.0", description="版本号")
    app_env: str = Field(default="development", description="环境：development / staging / production")

    # CORS
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost",
        description="逗号分隔的允许 origin",
    )

    # 数据库
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@postgres:5432/tiered_homework",
        description="SQLAlchemy 连接串",
    )

    # LLM Provider（M0 锁定 deepseek；M1+ 由配置切换）
    llm_provider: str = Field(default="deepseek", description="Provider 名")
    deepseek_api_key: str = Field(default="", description="DeepSeek API Key")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", description="DeepSeek base URL")
    deepseek_chat_model: str = Field(default="deepseek-chat", description="对话模型")
    deepseek_embedding_model: str = Field(default="deepseek-embedding", description="Embedding 模型")

    @property
    def cors_origins_list(self) -> list[str]:
        """把逗号分隔的 CORS 配置转成 list。"""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """单例读取配置（lru_cache 保证只解析一次）。"""
    return Settings()
