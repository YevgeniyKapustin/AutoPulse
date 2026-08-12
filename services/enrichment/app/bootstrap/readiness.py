"""Readiness checks against enrichment backing services."""

from __future__ import annotations

from services.enrichment.app.bootstrap.container import EnrichmentRuntime


async def check_readiness(
    runtime: EnrichmentRuntime,
) -> tuple[bool, dict[str, str]]:
    """Return ``(ready, checks)`` for MongoDB and RabbitMQ."""
    checks: dict[str, str] = {}

    try:
        await runtime.mongo_client.admin.command("ping")
        checks["mongodb"] = "ok"
    except Exception as exc:  # noqa: BLE001 — surface dep failure in probe
        checks["mongodb"] = f"error: {exc}"

    rabbit_ok = False
    publisher = runtime.publisher_connection
    channel = runtime.publisher_channel
    if publisher is not None and not publisher.is_closed:
        rabbit_ok = channel is not None and not channel.is_closed
    elif runtime.consumer is not None:
        rabbit_ok = runtime.consumer.is_ready
    checks["rabbitmq"] = "ok" if rabbit_ok else "unavailable"

    ready = all(value == "ok" for value in checks.values())
    return ready, checks
