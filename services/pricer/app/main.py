"""Pricer FastAPI entrypoint (API or combined local mode)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from autopulse_shared.metrics_http import MetricsHttpServer
from services.pricer.app.admin.service import PricerAdminService
from services.pricer.app.api.admin import router as admin_router
from services.pricer.app.api.errors import register_exception_handlers
from services.pricer.app.api.health import router as health_router
from services.pricer.app.api.pricing import router as pricing_router
from services.pricer.app.bootstrap import (
    PricerRuntime,
    assert_uvicorn_run_mode,
    attach_messaging_for_mode,
    build_runtime,
    drain_runtime_then_stop_metrics,
    start_metrics_server,
)
from services.pricer.app.bootstrap.readiness import check_readiness
from services.pricer.app.core.config import Settings, get_settings
from services.pricer.app.core.logging import setup_logging
from services.pricer.app.core.middleware import RequestIdMiddleware


class PricerApp:
    """HTTP process for RUN_MODE=api|all (uvicorn entrypoint)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._metrics: MetricsHttpServer | None = None
        self._runtime: PricerRuntime | None = None

    def create(self) -> FastAPI:
        """Build the FastAPI application with routers and middleware."""
        application = FastAPI(
            title="AutoPulse Pricer",
            version="0.1.0",
            lifespan=self.lifespan,
        )
        application.add_middleware(RequestIdMiddleware)
        self._register_exception_handlers(application)
        self._register_routers(application)
        application.state.settings = self._settings
        return application

    def _register_exception_handlers(self, application: FastAPI) -> None:
        """Map domain errors to HTTP responses."""
        register_exception_handlers(application)

    def _register_routers(self, application: FastAPI) -> None:
        """Attach HTTP routers for health, pricing, and admin."""
        application.include_router(health_router)
        application.include_router(pricing_router, prefix="/api/v1")
        application.include_router(admin_router, prefix="/api/v1")

    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncIterator[None]:
        """Boot metrics/runtime; always drain on exit."""
        try:
            await self._startup(app)
            yield
        finally:
            await self._shutdown()

    async def _startup(self, app: FastAPI) -> None:
        setup_logging(
            self._settings.log_level,
            service="pricer",
            environment=self._settings.environment,
        )
        assert_uvicorn_run_mode(self._settings)
        self._metrics = await start_metrics_server(self._settings)
        self._runtime = await build_runtime(self._settings)
        await attach_messaging_for_mode(self._runtime, self._settings.run_mode)
        runtime = self._runtime
        admin = PricerAdminService(
            runtime.repository,
            readiness_probe=lambda: check_readiness(runtime),
        )
        app.state.pricing = runtime.pricing
        app.state.runtime = runtime
        app.state.admin = admin

    async def _shutdown(self) -> None:
        await drain_runtime_then_stop_metrics(
            self._runtime,
            self._metrics,
            self._settings.shutdown_timeout_sec,
        )


def create_app() -> FastAPI:
    """Build the pricer FastAPI application."""
    return PricerApp(get_settings()).create()


app = create_app()
