"""LLM Provider 工厂（M0）。

工厂模式：根据配置返回具体 Provider 实现。
M0 锁定 deepseek；M1+ 在此分支扩展 openai / anthropic / 国产模型。
"""

from __future__ import annotations

from app.core.config import get_settings
from app.core.llm.deepseek import DeepSeekProvider
from app.core.llm.provider import LLMProvider


def get_llm_provider() -> LLMProvider:
    """根据配置返回 LLM Provider 实例。

    Returns:
        LLMProvider 实例（M0 阶段固定为 DeepSeekProvider）

    Raises:
        ValueError: 配置的 provider 暂不支持
    """
    settings = get_settings()
    provider_name = settings.llm_provider.lower().strip()

    if provider_name == "deepseek":
        if not settings.deepseek_api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY 未配置。请在 .env 或环境变量中设置后再启动。"
            )
        return DeepSeekProvider(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            chat_model=settings.deepseek_chat_model,
            embedding_model=settings.deepseek_embedding_model,
        )

    raise ValueError(
        f"暂不支持的 LLM provider: {provider_name}。M0 阶段只支持 deepseek。"
    )


def reset_llm_provider_cache() -> None:
    """清除 LLM 工厂缓存（测试 / 热重载时使用）。"""
    if hasattr(get_llm_provider, "cache_clear"):
        get_llm_provider.cache_clear()