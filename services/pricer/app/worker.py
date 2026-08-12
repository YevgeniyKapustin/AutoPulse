"""Pricer worker process — RabbitMQ consumer only (no public HTTP)."""

from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import suppress

from autopulse_shared.metrics_http import MetricsHttpServer
from services.pricer.app.bootstrap import (
    PricerRuntime,
    build_runtime,
    drain_runtime_then_stop_metrics,
    start_consumer,
    start_metrics_server,
)
from services.pricer.app.core.config import Settings, get_settings
from services.pricer.app.core.logging import setup_logging

logger = logging.getLogger(__name__)


class PricerWorker:
    """Long-running consumer process for RUN_MODE=worker."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stop = asyncio.Event()
        self._metrics: MetricsHttpServer | None = None
        self._runtime: PricerRuntime | None = None

    async def run(self) -> None:
        """Start metrics + consumer, then block until SIGINT/SIGTERM."""
        try:
            setup_logging(
                self._settings.log_level,
                service="pricer",
                environment=self._settings.environment,
            )
            self._metrics = await start_metrics_server(self._settings)
            self._runtime = await build_runtime(self._settings)
            await start_consumer(self._runtime)
            self._install_signal_handlers()

            logger.info("Pricer worker running")
            await self._stop.wait()
        finally:
            await self._shutdown()

    def request_stop(self) -> None:
        """Signal the worker to begin graceful shutdown."""
        logger.info("Shutdown signal received")
        self._stop.set()

    def _install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with suppress(NotImplementedError):
                loop.add_signal_handler(sig, self.request_stop)

    async def _shutdown(self) -> None:
        drained = await drain_runtime_then_stop_metrics(
            self._runtime,
            self._metrics,
            self._settings.shutdown_timeout_sec,
        )
        if not drained:
            logger.warning("Worker shutdown timed out")


def main() -> None:
    """Run the pricer RabbitMQ consumer until SIGINT/SIGTERM."""
    worker = PricerWorker(get_settings())
    asyncio.run(worker.run())


if __name__ == "__main__":
    main()
