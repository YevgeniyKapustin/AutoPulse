"""Circuit breaker helpers for external LLM / Vision APIs."""

from collections.abc import Awaitable, Callable
from enum import StrEnum
from time import monotonic
from typing import TypeVar

T = TypeVar("T")


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    pass


class CircuitBreaker:
    """Minimal in-memory circuit breaker."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_sec: float = 30.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.failures = 0
        self.state = CircuitState.CLOSED
        self.opened_at: float | None = None

    def before_call(self) -> None:
        if self.state == CircuitState.OPEN:
            assert self.opened_at is not None
            if monotonic() - self.opened_at >= self.recovery_timeout_sec:
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitOpenError("Circuit breaker is OPEN")

    def record_success(self) -> None:
        self.failures = 0
        self.state = CircuitState.CLOSED
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = monotonic()

    async def call(self, func: Callable[[], Awaitable[T]]) -> T:
        self.before_call()
        try:
            result = await func()
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result
