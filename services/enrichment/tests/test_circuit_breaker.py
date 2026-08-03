from services.enrichment.app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


def test_circuit_opens_after_threshold() -> None:
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_sec=60)
    breaker.record_failure()
    assert breaker.state == CircuitState.CLOSED
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN


def test_open_circuit_raises() -> None:
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_sec=60)
    breaker.record_failure()
    try:
        breaker.before_call()
        raised = False
    except CircuitOpenError:
        raised = True
    assert raised
