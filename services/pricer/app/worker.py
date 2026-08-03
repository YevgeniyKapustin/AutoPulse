"""Pricer worker process — consumes RabbitMQ only (no HTTP)."""

from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import suppress

from services.pricer.app.core.config import get_settings
from services.pricer.app.core.logging import setup_logging
from services.pricer.app.runtime import (
    build_runtime,
    shutdown_runtime,
    start_consumer,
)

logger = logging.getLogger(__name__)


async def _run() -> None:
    settings = get_settings()
    setup_logging(
        settings.log_level,
        service="pricer",
        environment=settings.environment,
    )
    runtime = await build_runtime(settings)
    await start_consumer(runtime)
    stop = asyncio.Event()

    def _request_stop() -> None:
        logger.info("Shutdown signal received")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, _request_stop)

    logger.info("Pricer worker running")
    try:
        await stop.wait()
    finally:
        try:
            await asyncio.wait_for(
                shutdown_runtime(runtime),
                timeout=settings.shutdown_timeout_sec,
            )
        except TimeoutError:
            logger.warning("Worker shutdown timed out")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
