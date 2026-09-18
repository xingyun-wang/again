"""LLM Provider 单元测试。

不连真 API，把 httpx.post 整体替换为 MockTransport 入口验证调用契约。
"""

from __future__ import annotations

import httpx
import pytest

from app.core.llm.deepseek import DeepSeekProvider
from app.core.llm.factory import get_llm_provider
from app.core.llm.provider import LLMProvider


def _patch_httpx_post(handler):
    """用 MockTransport 替换 httpx.post（模块级 monkey patch）。

    Args:
        handler: 接收 (url, headers, json_payload) -> httpx.Response

    Returns:
        original（httpx.post 原值），测试结束用 _restore_httpx_post 还原
    """
    original = httpx.post

    def mock_post(url, **kwargs):  # noqa: ANN001,ANN201
        # 避开 httpx.Request 构造差异（0.28 移除 timeout 等 kwargs）
        # 直接把 httpx.post 接收的 url/headers/json 透给 handler
        resp = handler(url=url, headers=kwargs.get("headers"), payload=kwargs.get("json"))
        # httpx 0.28: Response.raise_for_status 要求 _request 已设
        # 手动绑一个 Request 让它能正常工作
        resp._request = httpx.Request("POST", url)  # noqa: SLF001
        return resp

    httpx.post = mock_post
    return original


def _restore_httpx_post(original) -> None:  # noqa: ANN001
    httpx.post = original


# === LLMProvider 抽象契约 ===


def test_llm_provider_is_abstract() -> None:
    """LLMProvider 不能直接实例化（必须有具体实现）。"""
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore[abstract]


def test_deepseek_provider_is_llm_provider() -> None:
    """DeepSeekProvider 必须是 LLMProvider 子类。"""
    p = DeepSeekProvider(api_key="test-key")
    assert isinstance(p, LLMProvider)


# === DeepSeekProvider 行为 ===


def test_deepseek_chat_success() -> None:
    """chat() 正确解析标准 OpenAI 风格响应。"""

    def handler(url, headers, payload):  # noqa: ANN001
        assert url.endswith("/chat/completions")
        # httpx 0.27+ header 名统一为大写
        assert headers["Authorization"] == "Bearer test-key"
        assert payload["model"] == "deepseek-chat"
        assert payload["messages"] == [{"role": "user", "content": "hi"}]
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "hello back"}}],
                "usage": {"total_tokens": 10},
            },
        )

    original = _patch_httpx_post(handler)
    try:
        p = DeepSeekProvider(api_key="test-key")
        out = p.chat([{"role": "user", "content": "hi"}])
        assert out == "hello back"
    finally:
        _restore_httpx_post(original)


def test_deepseek_chat_empty_messages() -> None:
    """空 messages 应抛 ValueError（不浪费一次 HTTP 调用）。"""
    p = DeepSeekProvider(api_key="test-key")
    with pytest.raises(ValueError, match="messages 不能为空"):
        p.chat([])


def test_deepseek_chat_empty_api_key() -> None:
    """空 api_key 应在构造时抛 ValueError。"""
    with pytest.raises(ValueError, match="api_key 不能为空"):
        DeepSeekProvider(api_key="")


def test_deepseek_chat_http_error() -> None:
    """上游 4xx/5xx 时 RuntimeError 含 HTTP 状态码。"""

    def handler(url, headers, payload):  # noqa: ANN001
        return httpx.Response(401, json={"error": {"message": "invalid api key"}})

    original = _patch_httpx_post(handler)
    try:
        p = DeepSeekProvider(api_key="bad-key")
        with pytest.raises(RuntimeError, match="HTTP 401"):
            p.chat([{"role": "user", "content": "hi"}])
    finally:
        _restore_httpx_post(original)


def test_deepseek_embedding_success() -> None:
    """embedding() 正确解析返回的向量列表。"""

    def handler(url, headers, payload):  # noqa: ANN001
        assert url.endswith("/embeddings")
        assert payload["input"] == ["a", "b"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {"embedding": [0.1, 0.2, 0.3], "index": 0},
                    {"embedding": [0.4, 0.5, 0.6], "index": 1},
                ]
            },
        )

    original = _patch_httpx_post(handler)
    try:
        p = DeepSeekProvider(api_key="test-key")
        vecs = p.embedding(["a", "b"])
        assert vecs == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    finally:
        _restore_httpx_post(original)


def test_deepseek_embedding_empty_input() -> None:
    """空输入直接返回空 list（不打 HTTP）。"""
    p = DeepSeekProvider(api_key="test-key")
    assert p.embedding([]) == []


# === 工厂 ===


def test_factory_returns_deepseek(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_llm_provider() 在默认配置下返回 DeepSeekProvider。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-from-monkeypatch")
    from app.core.config import get_settings as _get_settings
    from app.core.llm.factory import reset_llm_provider_cache

    _get_settings.cache_clear()
    reset_llm_provider_cache()
    provider = get_llm_provider()
    assert isinstance(provider, DeepSeekProvider)


def test_factory_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """未配置 API key 时 factory log warning + provider 抛 ValueError（layered defense）。

    M0 retro #1 之后：factory 不再 fail-fast，只 log warning。
    真正空的 api_key 由 DeepSeekProvider.__init__ 的防御性检查抛错（保留既有行为）。
    """
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    from app.core.config import get_settings as _get_settings
    from app.core.llm.factory import reset_llm_provider_cache

    _get_settings.cache_clear()
    reset_llm_provider_cache()
    # factory 层不 raise；改由 provider 抛 ValueError，message 是 "api_key 不能为空"
    with pytest.raises(ValueError, match="api_key 不能为空"):
        get_llm_provider()
