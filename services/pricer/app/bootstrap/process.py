"""Process glue: metrics scrape port, run-mode checks, drain order."""

from __future__ import annotations

import asyncio
import logging

from autopulse_shared.metrics_http import MetricsHttpServer
from services.pricer.app.bootstrap.container import (
    PricerRuntime,
    shutdown_runtime,
    start_consumer,
)
from services.pricer.app.core.config import RunMode, Settings
from services.pricer.app.core.metrics import METRICS

logger = logging.getLogger(__name__)


def assert_uvicorn_run_mode(settings: Settings) -> None:
    """Reject RUN_MODE=worker; that mode belongs in the worker entrypoint."""
    if settings.run_mode == "worker":
        raise RuntimeError(
            "RUN_MODE=worker requires services.pricer.app.worker, not uvicorn"
        )


async def start_metrics_server(settings: Settings) -> MetricsHttpServer | None:
    """Bind the scrape-only /metrics port when METRICS_ENABLED."""
    if not settings.metrics_enabled:
        return None
    server = MetricsHttpServer(
        render=METRICS.render_prometheus,
        host=settings.metrics_host,
        port=settings.metrics_port,
    )
    await server.start()
    return server


async def attach_messaging_for_mode(
    runtime: PricerRuntime,
    mode: RunMode,
) -> None:
    """all = start consumer; api = HTTP only."""
    if mode == "all":
        await start_consumer(runtime)
    elif mode != "api":
        raise RuntimeError(f"Unsupported RUN_MODE={mode!r} (use api|worker|all)")


async def drain_runtime_then_stop_metrics(
    runtime: PricerRuntime | None,
    metrics: MetricsHttpServer | None,
    timeout_sec: float,
) -> bool:
    """Stop Rabbit/MySQL first; keep /metrics until that finishes.

    Always stops metrics in ``finally`` so partial startups cannot
    orphan the scrape port.
    """
    drained: bool = True
    try:
        if runtime is not None:
            try:
                await asyncio.wait_for(
                    shutdown_runtime(runtime),
                    timeout=timeout_sec,
                )
            except TimeoutError:
                drained = False
                logger.warning("Runtime shutdown timed out after %ss", timeout_sec)
    finally:
        if metrics is not None:
            await metrics.stop()
    return drained
