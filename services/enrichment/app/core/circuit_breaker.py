"""Circuit breaker helpers for external LLM / Vision APIs."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from enum import StrEnum
from time import monotonic
from typing import TypeVar

from services.enrichment.app.core.metrics import METRICS, MetricsRecorder

T = TypeVar("T")

logger = logging.getLogger(__name__)

METRIC_CIRCUIT_TRANSITIONS = "autopulse_circuit_breaker_transitions_total"


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    pass


class CircuitBreaker:
    """In-memory async circuit breaker (asyncio-safe).

    Callers should invoke ``record_failure`` only for infrastructure errors
    (timeouts, 5xx, rate limits). Application/parse errors should call
    ``record_success`` or leave the circuit unchanged.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_sec: float = 30.0,
        metrics: MetricsRecorder = METRICS,
        name: str = "default",
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.failures = 0
        self.state = CircuitState.CLOSED
        self.opened_at: float | None = None
        self._metrics = metrics
        self._name = name
        self._lock = asyncio.Lock()

    async def before_call(self) -> None:
        async with self._lock:
            if self.state != CircuitState.OPEN:
                return
            assert self.opened_at is not None
            if monotonic() - self.opened_at >= self.recovery_timeout_sec:
                self._transition(CircuitState.HALF_OPEN)
                return
            raise CircuitOpenError("Circuit breaker is OPEN")

    async def record_success(self) -> None:
        async with self._lock:
            self.failures = 0
            self.opened_at = None
            self._transition(CircuitState.CLOSED)

    async def record_failure(self) -> None:
        async with self._lock:
            self.failures += 1
            if self.failures >= self.failure_threshold:
                self.opened_at = monotonic()
                self._transition(CircuitState.OPEN)

    async def call(self, func: Callable[[], Awaitable[T]]) -> T:
        await self.before_call()
        try:
            result = await func()
        except Exception:
            await self.record_failure()
            raise
        await self.record_success()
        return result

    def _transition(self, new_state: CircuitState) -> None:
        if new_state == self.state:
            return
        old_state = self.state
        self.state = new_state
        logger.warning(
            "Circuit breaker name=%s %s -> %s failures=%s",
            self._name,
            old_state,
            new_state,
            self.failures,
        )
        self._metrics.inc(
            METRIC_CIRCUIT_TRANSITIONS,
            breaker=self._name,
            from_state=str(old_state),
            to_state=str(new_state),
        )
