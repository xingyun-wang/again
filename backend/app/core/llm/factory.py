"""LLM Provider 工厂（M0）。

工厂模式：根据配置返回具体 Provider 实现。
M0 锁定 deepseek；M1+ 在此分支扩展 openai / anthropic / 国产模型。

M0 retro 修正（#1, #5）：
- 显式检测 DEEPSEEK_API_KEY 是否为 placeholder（空 / "***" / "dummy"），
  是的话 logger.warning(...) 提示，但不 fail-fast（CI 用 ci-dummy-key）
- @lru_cache(maxsize=1) 缓存 provider，避免每次 LLM 调用都重新构造
- reset_llm_provider_cache() 用于测试 / 热重载时清缓存
"""

from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import get_settings
from app.core.llm.deepseek import DeepSeekProvider
from app.core.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

# 视为"未配置 / 占位"的 api_key 值。
# 注意：大小写敏感（环境变量本身就规范），前后空格不在内（避免误报真实 key）。
_PLACEHOLDER_API_KEYS: frozenset[str] = frozenset({"", "***", "dummy"})


def _is_placeholder(api_key: str) -> bool:
    return api_key in _PLACEHOLDER_API_KEYS


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    """根据配置返回 LLM Provider 实例。

    Returns:
        LLMProvider 实例（M0 阶段固定为 DeepSeekProvider）

    Note:
        使用 @lru_cache 缓存单例。测试 / 热重载时调 reset_llm_provider_cache()。

    Note:
        DEEPSEEK_API_KEY 为 placeholder（空 / "***" / "dummy"）时仅 warning，不 fail-fast。
        CI 用 ci-dummy-key，pytest 不需要真 key；M1+ 真值由用户通过 OpenClaw secrets 提供。
    """
    settings = get_settings()
    provider_name = settings.llm_provider.lower().strip()

    if provider_name == "deepseek":
        api_key = settings.deepseek_api_key
        if _is_placeholder(api_key):
            logger.warning(
                "DEEPSEEK_API_KEY 未配置或为 placeholder '%s'，运行时将返回 401",
                api_key,
            )
        return DeepSeekProvider(
            api_key=api_key,
            base_url=settings.deepseek_base_url,
            chat_model=settings.deepseek_chat_model,
            embedding_model=settings.deepseek_embedding_model,
        )

    raise ValueError(
        f"暂不支持的 LLM provider: {provider_name}。M0 阶段只支持 deepseek。"
    )


def reset_llm_provider_cache() -> None:
    """清除 LLM 工厂缓存（测试 / 热重载时使用）。

    配合 get_settings.cache_clear() 一起用，才能让环境变量变更生效。
    """
    if hasattr(get_llm_provider, "cache_clear"):
        get_llm_provider.cache_clear()