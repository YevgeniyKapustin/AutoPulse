import pytest

from services.enrichment.app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


@pytest.mark.asyncio
async def test_circuit_opens_after_threshold() -> None:
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_sec=60)
    await breaker.record_failure()
    assert breaker.state == CircuitState.CLOSED
    await breaker.record_failure()
    assert breaker.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_open_circuit_raises() -> None:
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_sec=60)
    await breaker.record_failure()
    with pytest.raises(CircuitOpenError):
        await breaker.before_call()


@pytest.mark.asyncio
async def test_open_recovers_to_half_open() -> None:
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_sec=0)
    await breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    await breaker.before_call()
    assert breaker.state == CircuitState.HALF_OPEN
