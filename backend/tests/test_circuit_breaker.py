"""Circuit Breaker + DeepSeek retry 行为测试（M1-B B.1）。

覆盖：
1. CircuitBreaker 三态切换（closed / open / half_open）
2. 阈值触发 open、试探成功→closed、试探失败→open
3. DeepSeekProvider 在 429 时由 tenacity 重试
4. DeepSeekProvider 在连续失败后被 breaker 拒
5. CircuitOpenError 不被 retry（避免在熔断期浪费配额）
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from app.core.llm.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState
from app.core.llm.deepseek import DeepSeekProvider

# =========================================================
# 1) CircuitBreaker 状态机
# =========================================================


def test_breaker_starts_closed() -> None:
    """初始状态应为 closed。"""
    cb = CircuitBreaker(failure_threshold=3, recovery_seconds=1.0, name="t1")
    assert cb.state == CircuitState.CLOSED
    cb.before_request()  # 不应抛


def test_breaker_threshold_triggers_open() -> None:
    """连续失败达到阈值 → open。"""
    cb = CircuitBreaker(failure_threshold=3, recovery_seconds=60.0, name="t2")
    for _ in range(3):
        cb.record_failure()
    assert cb.state == CircuitState.OPEN


def test_breaker_open_rejects_request() -> None:
    """open 状态下 before_request 抛 CircuitOpenError。"""
    cb = CircuitBreaker(failure_threshold=2, recovery_seconds=60.0, name="t3")
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    with pytest.raises(CircuitOpenError) as ei:
        cb.before_request()
    assert ei.value.retry_after > 0


def test_breaker_half_open_after_recovery() -> None:
    """open 后过 recovery_seconds → half_open 放行一次试探。"""
    cb = CircuitBreaker(failure_threshold=2, recovery_seconds=0.05, name="t4")
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    time.sleep(0.1)  # 等冷却
    cb.before_request()  # 应转入 half_open，不抛
    assert cb.state == CircuitState.HALF_OPEN


def test_breaker_half_open_success_closes() -> None:
    """half_open 试探成功 → closed。"""
    cb = CircuitBreaker(failure_threshold=2, recovery_seconds=0.05, name="t5")
    cb.record_failure()
    cb.record_failure()
    time.sleep(0.1)
    cb.before_request()  # → half_open
    cb.record_success()
    assert cb.state == CircuitState.CLOSED


def test_breaker_half_open_failure_reopens() -> None:
    """half_open 试探失败 → open（重新计时）。"""
    cb = CircuitBreaker(failure_threshold=2, recovery_seconds=0.05, name="t6")
    cb.record_failure()
    cb.record_failure()
    time.sleep(0.1)
    cb.before_request()  # → half_open
    assert cb.state == CircuitState.HALF_OPEN
    cb.record_failure()
    assert cb.state == CircuitState.OPEN


def test_breaker_success_resets_failure_count() -> None:
    """closed 状态成功调用 → 失败计数清零（间歇性失败不累积）。"""
    cb = CircuitBreaker(failure_threshold=3, recovery_seconds=60.0, name="t7")
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    # 现在又允许 3 次失败
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()  # 第 3 次
    assert cb.state == CircuitState.OPEN


def test_breaker_reset() -> None:
    """reset() 强制回到 closed。"""
    cb = CircuitBreaker(failure_threshold=1, recovery_seconds=60.0, name="t8")
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    cb.reset()
    assert cb.state == CircuitState.CLOSED


def test_breaker_invalid_params() -> None:
    """非法参数 → ValueError。"""
    with pytest.raises(ValueError, match="failure_threshold"):
        CircuitBreaker(failure_threshold=0, recovery_seconds=1.0)
    with pytest.raises(ValueError, match="recovery_seconds"):
        CircuitBreaker(failure_threshold=1, recovery_seconds=0)


# =========================================================
# 2) DeepSeekProvider retry 行为（用 monkeypatch 替 httpx.post）
# =========================================================


@pytest.fixture
def patch_httpx_post() -> Iterator[Any]:
    """提供可控的 httpx.post 替换工具。"""
    original = httpx.post

    def _set_handler(handler):
        def mock_post(url, **kwargs):  # noqa: ANN001,ANN201
            resp = handler(url=url, headers=kwargs.get("headers"), payload=kwargs.get("json"))
            resp._request = httpx.Request("POST", url)  # noqa: SLF001
            return resp

        httpx.post = mock_post

    yield _set_handler
    httpx.post = original


def test_chat_retries_on_429_then_succeeds(patch_httpx_post, monkeypatch: pytest.MonkeyPatch) -> None:
    """chat 遇 429 应由 tenacity 重试直到成功（或耗尽 3 次）。"""
    # 把 retry wait 缩到 0，加速测试
    import app.core.llm.deepseek as ds

    monkeypatch.setattr(ds, "_RETRY_WAIT_INITIAL", 0.0, raising=False)
    monkeypatch.setattr(ds, "_RETRY_WAIT_MULTIPLIER", 0.0, raising=False)

    calls: list[int] = []

    def handler(url, headers, payload):  # noqa: ANN001
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(429, json={"error": {"message": "rate limit"}})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "ok-after-retry"}}]},
        )

    patch_httpx_post(handler)
    # 注入独立 breaker，避免污染其他测试
    p = DeepSeekProvider(
        api_key="k", circuit_breaker=CircuitBreaker(failure_threshold=5, recovery_seconds=60.0)
    )
    out = p.chat([{"role": "user", "content": "hi"}])
    assert out == "ok-after-retry"
    assert len(calls) == 3  # 第 1、2 次 429，第 3 次 200


def test_chat_gives_up_after_max_attempts(patch_httpx_post, monkeypatch: pytest.MonkeyPatch) -> None:
    """3 次都是 429 → tenacity 用尽 → 抛 RuntimeError（含 HTTP 429）。"""
    import app.core.llm.deepseek as ds

    monkeypatch.setattr(ds, "_RETRY_WAIT_INITIAL", 0.0, raising=False)
    monkeypatch.setattr(ds, "_RETRY_WAIT_MULTIPLIER", 0.0, raising=False)

    def handler(url, headers, payload):  # noqa: ANN001
        return httpx.Response(429, json={"error": {"message": "rate limit"}})

    patch_httpx_post(handler)
    p = DeepSeekProvider(
        api_key="k", circuit_breaker=CircuitBreaker(failure_threshold=5, recovery_seconds=60.0)
    )
    with pytest.raises(RuntimeError, match="HTTP 429"):
        p.chat([{"role": "user", "content": "hi"}])


def test_chat_401_does_not_retry(patch_httpx_post, monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP 401 是认证错误，浪费配额，只调 1 次。"""
    import app.core.llm.deepseek as ds

    monkeypatch.setattr(ds, "_RETRY_WAIT_INITIAL", 0.0, raising=False)
    monkeypatch.setattr(ds, "_RETRY_WAIT_MULTIPLIER", 0.0, raising=False)

    calls: list[int] = []

    def handler(url, headers, payload):  # noqa: ANN001
        calls.append(1)
        return httpx.Response(401, json={"error": {"message": "invalid api key"}})

    patch_httpx_post(handler)
    p = DeepSeekProvider(
        api_key="bad", circuit_breaker=CircuitBreaker(failure_threshold=5, recovery_seconds=60.0)
    )
    with pytest.raises(RuntimeError, match="HTTP 401"):
        p.chat([{"role": "user", "content": "hi"}])
    assert len(calls) == 1  # 没重试


def test_chat_503_is_retryable(patch_httpx_post, monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP 503 属于上游繁忙，应重试。"""
    import app.core.llm.deepseek as ds

    monkeypatch.setattr(ds, "_RETRY_WAIT_INITIAL", 0.0, raising=False)
    monkeypatch.setattr(ds, "_RETRY_WAIT_MULTIPLIER", 0.0, raising=False)

    calls: list[int] = []

    def handler(url, headers, payload):  # noqa: ANN001
        calls.append(1)
        if len(calls) < 2:
            return httpx.Response(503, json={"error": {"message": "service unavailable"}})
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
        )

    patch_httpx_post(handler)
    p = DeepSeekProvider(
        api_key="k", circuit_breaker=CircuitBreaker(failure_threshold=5, recovery_seconds=60.0)
    )
    assert p.chat([{"role": "user", "content": "hi"}]) == "ok"
    assert len(calls) == 2


# =========================================================
# 3) Circuit breaker 集成（DeepSeekProvider 用）
# =========================================================


def test_provider_breaker_opens_after_threshold(
    patch_httpx_post, monkeypatch: pytest.MonkeyPatch
) -> None:
    """连续 5 次失败 → 第 6 次直接被 CircuitOpenError 拒。"""
    import app.core.llm.deepseek as ds

    monkeypatch.setattr(ds, "_RETRY_WAIT_INITIAL", 0.0, raising=False)
    monkeypatch.setattr(ds, "_RETRY_WAIT_MULTIPLIER", 0.0, raising=False)

    def handler(url, headers, payload):  # noqa: ANN001
        return httpx.Response(429, json={"error": {"message": "rate limit"}})

    patch_httpx_post(handler)
    # 阈值 5，恢复期 60s
    breaker = CircuitBreaker(failure_threshold=5, recovery_seconds=60.0)
    p = DeepSeekProvider(api_key="k", circuit_breaker=breaker)

    # 5 次失败（每次 chat 内部 tenacity 已经重试 3 次，但 chat 整体算 1 次 breaker 失败）
    for _ in range(5):
        with pytest.raises(RuntimeError, match="HTTP 429"):
            p.chat([{"role": "user", "content": "hi"}])
    assert breaker.state == CircuitState.OPEN

    # 第 6 次：breaker 直接拒（httpx.post 不会被调用）
    with pytest.raises(CircuitOpenError):
        p.chat([{"role": "user", "content": "hi"}])


def test_provider_breaker_recovers_after_recovery_seconds(
    patch_httpx_post, monkeypatch: pytest.MonkeyPatch
) -> None:
    """open 后过 recovery_seconds → half_open；成功 → close。"""
    import app.core.llm.deepseek as ds

    monkeypatch.setattr(ds, "_RETRY_WAIT_INITIAL", 0.0, raising=False)
    monkeypatch.setattr(ds, "_RETRY_WAIT_MULTIPLIER", 0.0, raising=False)

    call_count = {"n": 0}
    state = {"mode": "fail"}

    def handler(url, headers, payload):  # noqa: ANN001
        call_count["n"] += 1
        if state["mode"] == "fail":
            return httpx.Response(429, json={"error": {"message": "rate limit"}})
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "recovered"}}]}
        )

    patch_httpx_post(handler)
    breaker = CircuitBreaker(failure_threshold=3, recovery_seconds=0.1)
    p = DeepSeekProvider(api_key="k", circuit_breaker=breaker)

    # 触发 3 次失败 → open
    for _ in range(3):
        with pytest.raises(RuntimeError):
            p.chat([{"role": "user", "content": "hi"}])
    assert breaker.state == CircuitState.OPEN

    # 等冷却
    time.sleep(0.15)

    # 切到成功模式 → 下一次应放行（half_open 试探成功 → close）
    state["mode"] = "ok"
    out = p.chat([{"role": "user", "content": "hi"}])
    assert out == "recovered"
    assert breaker.state == CircuitState.CLOSED


def test_provider_breaker_half_open_failure_reopens(
    patch_httpx_post, monkeypatch: pytest.MonkeyPatch
) -> None:
    """half_open 试探失败 → 立即回 open。"""
    import app.core.llm.deepseek as ds

    monkeypatch.setattr(ds, "_RETRY_WAIT_INITIAL", 0.0, raising=False)
    monkeypatch.setattr(ds, "_RETRY_WAIT_MULTIPLIER", 0.0, raising=False)

    def handler(url, headers, payload):  # noqa: ANN001
        return httpx.Response(503, json={"error": {"message": "down"}})

    patch_httpx_post(handler)
    breaker = CircuitBreaker(failure_threshold=2, recovery_seconds=0.05)
    p = DeepSeekProvider(api_key="k", circuit_breaker=breaker)

    for _ in range(2):
        with pytest.raises(RuntimeError):
            p.chat([{"role": "user", "content": "hi"}])
    assert breaker.state == CircuitState.OPEN

    time.sleep(0.1)  # 等冷却 → 切 half_open
    with pytest.raises(RuntimeError, match="HTTP 503"):
        p.chat([{"role": "user", "content": "hi"}])
    assert breaker.state == CircuitState.OPEN  # 试探失败 → 再次 open


def test_breaker_state_changes_logged(
    patch_httpx_post,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """breaker 状态变化应被 logger.info 记录。"""
    import app.core.llm.deepseek as ds

    monkeypatch.setattr(ds, "_RETRY_WAIT_INITIAL", 0.0, raising=False)
    monkeypatch.setattr(ds, "_RETRY_WAIT_MULTIPLIER", 0.0, raising=False)

    def handler(url, headers, payload):  # noqa: ANN001
        return httpx.Response(503, json={"error": {"message": "down"}})

    patch_httpx_post(handler)
    breaker = CircuitBreaker(failure_threshold=2, recovery_seconds=0.05, name="log-test")
    p = DeepSeekProvider(api_key="k", circuit_breaker=breaker)

    with caplog.at_level(logging.INFO, logger="app.core.llm.circuit_breaker"):
        for _ in range(2):
            with pytest.raises(RuntimeError):
                p.chat([{"role": "user", "content": "hi"}])

    state_change_msgs = [
        r.message for r in caplog.records
        if "state_change" in r.message and "closed -> open" in r.message
    ]
    assert len(state_change_msgs) >= 1


def test_embedding_retries_on_network_error(
    patch_httpx_post, monkeypatch: pytest.MonkeyPatch
) -> None:
    """embedding 遇 httpx.ConnectError 应重试。"""
    import app.core.llm.deepseek as ds

    monkeypatch.setattr(ds, "_RETRY_WAIT_INITIAL", 0.0, raising=False)
    monkeypatch.setattr(ds, "_RETRY_WAIT_MULTIPLIER", 0.0, raising=False)

    call_count = {"n": 0}

    def handler(url, headers, payload):  # noqa: ANN001
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise httpx.ConnectError("connection reset", request=httpx.Request("POST", url))
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}]})

    patch_httpx_post(handler)
    p = DeepSeekProvider(
        api_key="k", circuit_breaker=CircuitBreaker(failure_threshold=5, recovery_seconds=60.0)
    )
    vecs = p.embedding(["hello"])
    assert vecs == [[0.1, 0.2]]
    assert call_count["n"] == 2


def test_circuit_open_error_is_not_retried(
    patch_httpx_post, monkeypatch: pytest.MonkeyPatch
) -> None:
    """熔断器已开 → CircuitOpenError 不被 tenacity 重试（直接抛）。"""
    import app.core.llm.deepseek as ds

    monkeypatch.setattr(ds, "_RETRY_WAIT_INITIAL", 0.0, raising=False)
    monkeypatch.setattr(ds, "_RETRY_WAIT_MULTIPLIER", 0.0, raising=False)

    # breaker 强制设为 open
    breaker = CircuitBreaker(failure_threshold=1, recovery_seconds=60.0)
    breaker.record_failure()  # → open
    assert breaker.state == CircuitState.OPEN

    call_count = {"n": 0}

    def handler(url, headers, payload):  # noqa: ANN001
        call_count["n"] += 1
        return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})

    patch_httpx_post(handler)
    p = DeepSeekProvider(api_key="k", circuit_breaker=breaker)
    with pytest.raises(CircuitOpenError):
        p.chat([{"role": "user", "content": "hi"}])
    assert call_count["n"] == 0  # 下游一次都没被调