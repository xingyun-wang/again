"""DeepSeek Provider 实现（M0）。

DeepSeek-V3 的 API 兼容 OpenAI Chat Completions 格式，因此底层走 httpx 直接打 HTTP。
为避免 M0 阶段引入 openai SDK 依赖，这里手写最小 HTTP 调用。
M1+ 若需要多 Provider 切换，可改为 openai SDK + base_url 兼容模式。
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class DeepSeekProvider(LLMProvider):
    """DeepSeek-V3 Provider。

    base_url 默认指向官方 https://api.deepseek.com。
    chat_model 默认 deepseek-chat（V3 主对话模型）。
    embedding_model 默认 deepseek-embedding（若账号未开通则需要在 M1+ 调整）。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        chat_model: str = "deepseek-chat",
        embedding_model: str = "deepseek-embedding",
        timeout: float = 60.0,
    ) -> None:
        if not api_key:
            raise ValueError("DeepSeek api_key 不能为空")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def chat(self, messages: list[dict[str, object]], **kwargs: Any) -> str:
        """调用 DeepSeek Chat Completions。

        Args:
            messages: OpenAI 风格消息列表
            **kwargs: temperature / max_tokens / top_p / stream 等

        Returns:
            模型回复文本（assistant 角色的 content）
        """
        if not messages:
            raise ValueError("messages 不能为空")

        payload: dict[str, Any] = {
            "model": self._chat_model,
            "messages": messages,
        }
        # 把 kwargs 里允许的字段塞进 payload
        for key in ("temperature", "max_tokens", "top_p", "stream", "stop"):
            if key in kwargs:
                payload[key] = kwargs[key]

        url = f"{self._base_url}/chat/completions"
        logger.debug("DeepSeek chat url=%s payload_keys=%s", url, list(payload.keys()))

        try:
            resp = httpx.post(url, headers=self._headers(), json=payload, timeout=self._timeout)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            # 把上游错误体抛出来，便于排查
            body_preview = e.response.text[:500] if e.response else ""
            raise RuntimeError(
                f"DeepSeek chat HTTP {e.response.status_code if e.response else '?'}: {body_preview}"
            ) from e
        except httpx.HTTPError as e:
            raise RuntimeError(f"DeepSeek chat 网络错误：{e}") from e

        data = resp.json()
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"DeepSeek chat 返回结构异常：{json.dumps(data)[:500]}") from e

    def embedding(self, texts: list[str]) -> list[list[float]]:
        """调用 DeepSeek Embeddings。

        Args:
            texts: 待嵌入文本列表

        Returns:
            与 texts 等长的向量列表（DeepSeek embedding 通常 1024 或 1536 维）
        """
        if not texts:
            return []

        payload: dict[str, Any] = {
            "model": self._embedding_model,
            "input": texts,
        }
        url = f"{self._base_url}/embeddings"

        try:
            resp = httpx.post(url, headers=self._headers(), json=payload, timeout=self._timeout)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            body_preview = e.response.text[:500] if e.response else ""
            raise RuntimeError(
                f"DeepSeek embedding HTTP {e.response.status_code if e.response else '?'}: {body_preview}"
            ) from e
        except httpx.HTTPError as e:
            raise RuntimeError(f"DeepSeek embedding 网络错误：{e}") from e

        data = resp.json()
        try:
            return [list(item["embedding"]) for item in data["data"]]
        except (KeyError, TypeError) as e:
            raise RuntimeError(f"DeepSeek embedding 返回结构异常：{json.dumps(data)[:500]}") from e
