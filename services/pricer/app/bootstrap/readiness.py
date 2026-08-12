"""Readiness checks against pricer backing services."""

from __future__ import annotations

from sqlalchemy import text

from services.pricer.app.bootstrap.container import PricerRuntime


async def check_readiness(runtime: PricerRuntime) -> tuple[bool, dict[str, str]]:
    """Return ``(ready, checks)`` for MySQL and (when present) RabbitMQ."""
    checks: dict[str, str] = {}

    try:
        async with runtime.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        checks["mysql"] = "ok"
    except Exception as exc:  # noqa: BLE001 — surface dep failure in probe
        checks["mysql"] = f"error: {exc}"

    if runtime.consumer is not None:
        checks["rabbitmq"] = "ok" if runtime.consumer.is_ready else "unavailable"

    ready = all(value == "ok" for value in checks.values())
    return ready, checks
