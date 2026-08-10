"""Enrichment FastAPI entrypoint (API or combined local mode)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from autopulse_shared.metrics_http import MetricsHttpServer
from services.enrichment.app.api.admin import router as admin_api_router
from services.enrichment.app.api.admin_ui import router as admin_ui_router
from services.enrichment.app.api.dealer_ui import router as dealer_ui_router
from services.enrichment.app.api.errors import register_exception_handlers
from services.enrichment.app.api.health import router as health_router
from services.enrichment.app.api.listings import router as listings_router
from services.enrichment.app.bootstrap import (
    EnrichmentRuntime,
    assert_uvicorn_run_mode,
    attach_messaging_for_mode,
    build_runtime,
    drain_runtime_then_stop_metrics,
    start_metrics_server,
)
from services.enrichment.app.bootstrap.admin import (
    AdminBundle,
    build_admin_bundle,
)
from services.enrichment.app.bootstrap.dealer import (
    DealerBundle,
    build_dealer_bundle,
)
from services.enrichment.app.core.config import Settings, get_settings
from services.enrichment.app.core.logging import setup_logging
from services.enrichment.app.core.middleware import RequestIdMiddleware

_ADMIN_STATIC = Path(__file__).resolve().parent / "admin" / "static"
_DEALER_STATIC = Path(__file__).resolve().parent / "dealer" / "static"


class EnrichmentApp:
    """HTTP process for RUN_MODE=api|all (uvicorn entrypoint)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._metrics: MetricsHttpServer | None = None
        self._runtime: EnrichmentRuntime | None = None
        self._admin_bundle: AdminBundle | None = None
        self._dealer_bundle: DealerBundle | None = None

    def create(self) -> FastAPI:
        """Build the FastAPI application with routers and middleware."""
        application = FastAPI(
            title="AutoPulse Enrichment",
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
        """Attach HTTP routers for health, listings, admin, dealer."""
        application.include_router(health_router)
        application.include_router(listings_router, prefix="/api/v1")
        if self._settings.dealer_ui_enabled:
            application.include_router(dealer_ui_router)
            application.mount(
                "/dealer/static",
                StaticFiles(directory=str(_DEALER_STATIC)),
                name="dealer-static",
            )
        if self._settings.admin_ui_enabled:
            application.include_router(admin_api_router, prefix="/api/v1")
            application.include_router(admin_ui_router)
            application.mount(
                "/admin/static",
                StaticFiles(directory=str(_ADMIN_STATIC)),
                name="admin-static",
            )

    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncIterator[None]:
        """Boot metrics, runtime, and messaging; drain in reverse on
        shutdown."""
        try:
            await self._startup(app)
            yield
        finally:
            await self._shutdown()

    async def _startup(self, app: FastAPI) -> None:
        setup_logging(
            self._settings.log_level,
            service="enrichment",
            environment=self._settings.environment,
        )
        assert_uvicorn_run_mode(self._settings)
        self._metrics = await start_metrics_server(self._settings)
        self._runtime = await build_runtime(self._settings)
        await attach_messaging_for_mode(self._runtime, self._settings.run_mode)
        self._admin_bundle = await build_admin_bundle(self._runtime)
        self._dealer_bundle = await build_dealer_bundle(self._runtime)
        app.state.orchestrator = self._runtime.orchestrator
        app.state.runtime = self._runtime
        app.state.admin = (
            None if self._admin_bundle is None else self._admin_bundle.service
        )
        app.state.dealer = (
            None if self._dealer_bundle is None else self._dealer_bundle.service
        )

    async def _shutdown(self) -> None:
        if self._dealer_bundle is not None:
            with suppress(Exception):
                await self._dealer_bundle.aclose()
            self._dealer_bundle = None
        if self._admin_bundle is not None:
            with suppress(Exception):
                await self._admin_bundle.aclose()
            self._admin_bundle = None
        await drain_runtime_then_stop_metrics(
            self._runtime,
            self._metrics,
            self._settings.shutdown_timeout_sec,
        )


def create_app() -> FastAPI:
    """Build the enrichment FastAPI application."""
    return EnrichmentApp(get_settings()).create()


app = create_app()
