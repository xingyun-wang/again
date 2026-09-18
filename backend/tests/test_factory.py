"""LLM Provider 工厂的 M0 retro 行为（M0 retro #1, #5）。

覆盖：
- placeholder api_key（"***" / "dummy"）→ warning log + 返回 provider（不 fail-fast）
- 真实 api_key → 无 warning
- @lru_cache → 同一调用复用同一实例
- cache_clear 后重新构造

注意：空 api_key 由 DeepSeekProvider.__init__ 的防御性检查抛错（layered defense），
      在 tests/test_llm_provider.py::test_factory_missing_api_key 里覆盖。
"""

from __future__ import annotations

import logging

import pytest

from app.core.llm.deepseek import DeepSeekProvider
from app.core.llm.factory import get_llm_provider, reset_llm_provider_cache


def _reset_caches() -> None:
    """清掉 settings + factory 缓存（让 monkeypatch.setenv 生效）。"""
    from app.core.config import get_settings

    get_settings.cache_clear()
    reset_llm_provider_cache()


# === placeholder 检测 ===


def test_factory_warns_on_stars_placeholder(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """api_key='***' → logger.warning + 返回 DeepSeekProvider（不 fail-fast）。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "***")
    _reset_caches()
    with caplog.at_level(logging.WARNING, logger="app.core.llm.factory"):
        provider = get_llm_provider()
    assert isinstance(provider, DeepSeekProvider)
    warnings = [r for r in caplog.records if r.name == "app.core.llm.factory"]
    assert len(warnings) == 1
    msg = warnings[0].getMessage()
    assert "DEEPSEEK_API_KEY" in msg
    assert "placeholder" in msg
    assert "401" in msg


def test_factory_warns_on_dummy_placeholder(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """api_key='dummy' → logger.warning + 返回 DeepSeekProvider（不 fail-fast）。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy")
    _reset_caches()
    with caplog.at_level(logging.WARNING, logger="app.core.llm.factory"):
        provider = get_llm_provider()
    assert isinstance(provider, DeepSeekProvider)
    warnings = [r for r in caplog.records if r.name == "app.core.llm.factory"]
    assert len(warnings) == 1
    assert "placeholder" in warnings[0].getMessage()


def test_factory_no_warning_on_real_key(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """真实 api_key → 不触发 placeholder warning。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-real-key-12345")
    _reset_caches()
    with caplog.at_level(logging.WARNING):
        provider = get_llm_provider()
    assert isinstance(provider, DeepSeekProvider)
    factory_warnings = [r for r in caplog.records if r.name == "app.core.llm.factory"]
    assert factory_warnings == []


def test_factory_warning_message_includes_value(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """warning message 应包含 api_key 实际值（便于排查 .env 配置）。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "***")
    _reset_caches()
    with caplog.at_level(logging.WARNING, logger="app.core.llm.factory"):
        get_llm_provider()
    warnings = [r for r in caplog.records if r.name == "app.core.llm.factory"]
    assert len(warnings) == 1
    # 验证 '%s' 参数注入的 api_key 值出现在 message 里
    assert "***" in warnings[0].getMessage()


# === @lru_cache 行为（M0 retro #5） ===


def test_factory_uses_lru_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """两次连续调用返回同一实例（@lru_cache 生效）。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "cache-test-key")
    _reset_caches()
    p1 = get_llm_provider()
    p2 = get_llm_provider()
    assert p1 is p2


def test_factory_cache_clear_returns_new_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """reset_llm_provider_cache() 后调用 → 新实例。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "first-key")
    _reset_caches()
    p1 = get_llm_provider()

    # 改 env + 清缓存 → 重建
    monkeypatch.setenv("DEEPSEEK_API_KEY", "second-key")
    _reset_caches()
    p2 = get_llm_provider()

    assert p1 is not p2


def test_factory_cache_clear_idempotent() -> None:
    """cache_clear 在空缓存上调用不报错。"""
    # 没调用过 factory，cache 是空的
    reset_llm_provider_cache()  # no-op, no raise
    reset_llm_provider_cache()  # 重复调用也不报错


# === 不支持的 provider 仍 fail-fast（保留既有行为）===


def test_factory_unsupported_provider_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """非 deepseek provider 仍抛 ValueError（不在 M0 retro #1 范围内）。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "any-key")
    monkeypatch.setenv("LLM_PROVIDER", "openai-not-supported-yet")
    _reset_caches()
    with pytest.raises(ValueError, match="暂不支持的 LLM provider"):
        get_llm_provider()