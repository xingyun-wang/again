"""Circuit Breaker（自写，零外部依赖）。

设计：
- 状态机：closed → open → half_open → closed / open
- closed：正常通过；连续 N 次失败 → open
- open：直接抛 CircuitOpenError，不调下游
- half_open：冷却时间到后放行 1 次试探
    - 成功 → close（清失败计数）
    - 失败 → open（重置冷却计时）
- 内存状态，per-instance 单例（DeepSeekProvider 已被 lru_cache 单例化）
- 状态变化 + 失败/试探事件通过标准 logging 模块记录（用 logger.info）

参考：v0.5 §10 M1-B B.1 规格。
"""

from __future__ import annotations

import logging
import threading
import time
from enum import StrEnum

logger = logging.getLogger(__name__)


class CircuitState(StrEnum):
    """Circuit breaker 三态。"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """熔断器打开时抛出的错误。调用方应快速失败，不要重试。"""

    def __init__(self, message: str, retry_after: float) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class CircuitBreaker:
    """线程安全的 circuit breaker。

    参数：
        failure_threshold：连续失败多少次进入 open
        recovery_seconds：open 后多少秒进入 half_open
        name：用于日志标识
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_seconds: float = 60.0,
        name: str = "default",
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold 必须 ≥ 1")
        if recovery_seconds <= 0:
            raise ValueError("recovery_seconds 必须 > 0")
        self._failure_threshold = failure_threshold
        self._recovery_seconds = recovery_seconds
        self._name = name
        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """当前状态（线程安全读快照）。"""
        with self._lock:
            return self._state

    def _transition(self, new_state: CircuitState) -> None:
        """状态切换 + 日志。需在持锁状态下调用。"""
        if new_state == self._state:
            return
        logger.info(
            "circuit_breaker state_change name=%s %s -> %s",
            self._name,
            self._state.value,
            new_state.value,
        )
        self._state = new_state

    def _should_attempt_reset(self) -> bool:
        """检查 open 状态是否已过冷却期，是则进入 half_open。需持锁。"""
        if self._opened_at is None:
            return False
        return (time.monotonic() - self._opened_at) >= self._recovery_seconds

    def before_request(self) -> None:
        """请求前闸门检查。

        - closed：直接放行
        - open：若已过冷却期 → 切 half_open 放行；否则抛 CircuitOpenError
        - half_open：直接放行（试探调用由 caller 负责，允许多个 caller 并发时
          只放 1 个的做法需要更复杂锁，这里保持简单：half_open 不互斥；
          试探失败的 caller 会把状态重置回 open）
        """
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition(CircuitState.HALF_OPEN)
                    return
                retry_after = self._recovery_seconds - (
                    (time.monotonic() - self._opened_at) if self._opened_at else 0.0
                )
                raise CircuitOpenError(
                    f"circuit_breaker '{self._name}' is open；{retry_after:.1f}s 后重试",
                    retry_after=max(0.0, retry_after),
                )
            # half_open：放行试探

    def record_success(self) -> None:
        """请求成功后调用：清失败计数 + close（从 half_open）。"""
        with self._lock:
            self._failure_count = 0
            if self._state != CircuitState.CLOSED:
                self._transition(CircuitState.CLOSED)
            self._opened_at = None

    def record_failure(self) -> None:
        """请求失败后调用：累计失败次数；超过阈值则切 open。"""
        with self._lock:
            self._failure_count += 1
            logger.info(
                "circuit_breaker failure name=%s count=%d/%d",
                self._name,
                self._failure_count,
                self._failure_threshold,
            )
            if self._state == CircuitState.HALF_OPEN:
                # 试探失败 → 立即回 open，重置冷却
                self._opened_at = time.monotonic()
                self._transition(CircuitState.OPEN)
            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self._failure_threshold
            ):
                self._opened_at = time.monotonic()
                self._transition(CircuitState.OPEN)

    def reset(self) -> None:
        """强制 reset 到 closed（测试 / 运维用）。"""
        with self._lock:
            self._failure_count = 0
            self._opened_at = None
            self._transition(CircuitState.CLOSED)