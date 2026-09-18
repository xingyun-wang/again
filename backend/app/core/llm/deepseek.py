"""DeepSeek Provider 实现（M0 + M1-B B.1 增强）。

DeepSeek-V3 的 API 兼容 OpenAI Chat Completions 格式，因此底层走 httpx 直接打 HTTP。
为避免 M0 阶段引入 openai SDK 依赖，这里手写最小 HTTP 调用。
M1+ 若需要多 Provider 切换，可改为 openai SDK + base_url 兼容模式。

M1-B B.1 增强：
- tenacity 指数退避重试（1s / 2s / 4s，最多 3 次）
- 集成 CircuitBreaker：连续 5 次失败 → 拒绝 60s → 半开试探
- retryable 错误：HTTP 429 / 503 / 网络超时 / 连接重置
- non-retryable：HTTP 401 / 400 / 422（认证/请求错误，重试浪费配额）
- 非 retryable 的 HTTPError 走 RuntimeError 通道，不计入 breaker（避免假阳性熔断）
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.llm.circuit_breaker import CircuitBreaker, CircuitOpenError
from app.core.llm.provider import LLMProvider

logger = logging.getLogger(__name__)


# --- 重试/熔断策略常量（M1-B B.1 规格）---
_MAX_ATTEMPTS = 3  # 1 次初次 + 2 次重试；规格"最多 3 次尝试"=包含初次
_RETRY_WAIT_INITIAL = 1.0  # 1s
_RETRY_WAIT_MULTIPLIER = 2.0  # 1s / 2s / 4s
_CIRCUIT_FAILURE_THRESHOLD = 5
_CIRCUIT_RECOVERY_SECONDS = 60.0
_RETRYABLE_HTTP_STATUSES: frozenset[int] = frozenset({429, 503})


def _is_retryable_exception(exc: BaseException) -> bool:
    """tenacity 的 retry predicate。

    规则：
    - CircuitOpenError：熔断器已开，不再重试（避免在熔断期浪费尝试）
    - httpx.TimeoutException / ConnectError：网络层，重试有意义
    - httpx.HTTPStatusError：仅 429/503 重试；其他（401/400/422）属于客户端错误，
      重试只是浪费配额，立即失败
    - RuntimeError（DeepSeek 自身包装错误）：含 401/400/422 → 不重试；
      含 429/503 或网络错误 → 重试
    """
    if isinstance(exc, CircuitOpenError):
        return False
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_HTTP_STATUSES
    if isinstance(exc, RuntimeError):
        msg = str(exc)
        # DeepSeek wrapper 形如 "DeepSeek chat HTTP 429: ..." 或 "...网络错误：..."
        if "网络错误" in msg:
            return True
        return any(f"HTTP {code}" in msg for code in _RETRYABLE_HTTP_STATUSES)
    return False


def _log_retry(retry_state: RetryCallState) -> None:
    """tenacity 重试前的日志钩子。"""
    logger.info(
        "DeepSeek retry attempt=%s next_wait=%.1fs exc=%s",
        retry_state.attempt_number,
        getattr(retry_state.next_action, "sleep", 0.0) if retry_state.next_action else 0.0,
        type(retry_state.outcome.exception()).__name__ if retry_state.outcome else "n/a",
    )


class DeepSeekProvider(LLMProvider):
    """DeepSeek-V3 Provider（带 retry + circuit breaker）。

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
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("DeepSeek api_key 不能为空")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._timeout = timeout
        # 默认共享一个 breaker（按 provider 名标识）
        self._breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=_CIRCUIT_FAILURE_THRESHOLD,
            recovery_seconds=_CIRCUIT_RECOVERY_SECONDS,
            name="deepseek",
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    # --- tenacity 重试装饰器（chat 用）---
    @retry(
        retry=retry_if_exception(_is_retryable_exception),
        wait=wait_exponential(
            multiplier=_RETRY_WAIT_INITIAL, max=4.0, exp_base=_RETRY_WAIT_MULTIPLIER
        ),
        stop=stop_after_attempt(_MAX_ATTEMPTS),
        before_sleep=_log_retry,
        reraise=True,
    )
    def _chat_once(self, payload: dict[str, Any]) -> httpx.Response:
        """单次 chat HTTP 调用；被 tenacity 包裹，失败按 _is_retryable_exception 重试。"""
        url = f"{self._base_url}/chat/completions"
        resp = httpx.post(url, headers=self._headers(), json=payload, timeout=self._timeout)
        resp.raise_for_status()
        return resp

    @retry(
        retry=retry_if_exception(_is_retryable_exception),
        wait=wait_exponential(
            multiplier=_RETRY_WAIT_INITIAL, max=4.0, exp_base=_RETRY_WAIT_MULTIPLIER
        ),
        stop=stop_after_attempt(_MAX_ATTEMPTS),
        before_sleep=_log_retry,
        reraise=True,
    )
    def _embedding_once(self, payload: dict[str, Any]) -> httpx.Response:
        """单次 embedding HTTP 调用；同上。"""
        url = f"{self._base_url}/embeddings"
        resp = httpx.post(url, headers=self._headers(), json=payload, timeout=self._timeout)
        resp.raise_for_status()
        return resp

    def chat(self, messages: list[dict[str, object]], **kwargs: Any) -> str:
        """调用 DeepSeek Chat Completions（含 retry + circuit breaker）。

        Args:
            messages: OpenAI 风格消息列表
            **kwargs: temperature / max_tokens / top_p / stream 等

        Returns:
            模型回复文本（assistant 角色的 content）

        Raises:
            ValueError: messages 为空
            CircuitOpenError: 熔断器开启中
            RuntimeError: 上游 4xx/5xx 或返回结构异常（非 retryable）
        """
        if not messages:
            raise ValueError("messages 不能为空")

        payload: dict[str, Any] = {
            "model": self._chat_model,
            "messages": messages,
        }
        for key in ("temperature", "max_tokens", "top_p", "stream", "stop"):
            if key in kwargs:
                payload[key] = kwargs[key]

        url = f"{self._base_url}/chat/completions"
        logger.debug("DeepSeek chat url=%s payload_keys=%s", url, list(payload.keys()))

        # 熔断器闸门：open 状态直接抛 CircuitOpenError，不调下游
        self._breaker.before_request()
        try:
            resp = self._chat_once(payload)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as e:
            # tenacity 耗尽尝试后会 reraise 最后一个原始异常
            if isinstance(e, httpx.HTTPStatusError):
                body_preview = e.response.text[:500] if e.response else ""
                # 仅 retryable 状态码（429/503）才会到这里；其他应被 _is_retryable 拦截
                wrapped = RuntimeError(
                    f"DeepSeek chat HTTP {e.response.status_code}: {body_preview}"
                )
            elif isinstance(e, (httpx.TimeoutException, httpx.ConnectError)):
                wrapped = RuntimeError(f"DeepSeek chat 网络错误：{e}")
            else:
                wrapped = RuntimeError(f"DeepSeek chat 错误：{e}")
            self._breaker.record_failure()
            raise wrapped from e

        # 成功路径 → 通知 breaker
        self._breaker.record_success()

        data = resp.json()
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as e:
            # 响应结构异常：不计入 breaker（不是下游故障，是契约漂移）
            raise RuntimeError(f"DeepSeek chat 返回结构异常：{json.dumps(data)[:500]}") from e

    def embedding(self, texts: list[str]) -> list[list[float]]:
        """调用 DeepSeek Embeddings（含 retry + circuit breaker）。

        Args:
            texts: 待嵌入文本列表

        Returns:
            与 texts 等长的向量列表

        Raises:
            CircuitOpenError: 熔断器开启中
            RuntimeError: 上游错误或返回结构异常
        """
        if not texts:
            return []

        payload: dict[str, Any] = {
            "model": self._embedding_model,
            "input": texts,
        }

        self._breaker.before_request()
        try:
            resp = self._embedding_once(payload)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as e:
            if isinstance(e, httpx.HTTPStatusError):
                body_preview = e.response.text[:500] if e.response else ""
                wrapped = RuntimeError(
                    f"DeepSeek embedding HTTP {e.response.status_code}: {body_preview}"
                )
            elif isinstance(e, (httpx.TimeoutException, httpx.ConnectError)):
                wrapped = RuntimeError(f"DeepSeek embedding 网络错误：{e}")
            else:
                wrapped = RuntimeError(f"DeepSeek embedding 错误：{e}")
            self._breaker.record_failure()
            raise wrapped from e

        self._breaker.record_success()

        data = resp.json()
        try:
            return [list(item["embedding"]) for item in data["data"]]
        except (KeyError, TypeError) as e:
            raise RuntimeError(f"DeepSeek embedding 返回结构异常：{json.dumps(data)[:500]}") from e