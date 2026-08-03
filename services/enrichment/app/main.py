"""Enrichment FastAPI entrypoint (API or combined local mode)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Response

from services.enrichment.app.api.health import router as health_router
from services.enrichment.app.api.listings import router as listings_router
from services.enrichment.app.core.config import get_settings
from services.enrichment.app.core.logging import setup_logging
from services.enrichment.app.core.metrics import METRICS
from services.enrichment.app.core.middleware import RequestIdMiddleware
from services.enrichment.app.runtime import (
    attach_publisher,
    build_runtime,
    shutdown_runtime,
    start_consumer,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(
        settings.log_level,
        service="enrichment",
        environment=settings.environment,
    )
    mode = settings.run_mode
    if mode == "worker":
        raise RuntimeError(
            "RUN_MODE=worker requires services.enrichment.app.worker, not uvicorn"
        )

    runtime = await build_runtime(settings)
    if mode == "api":
        await attach_publisher(runtime)
    elif mode == "all":
        await start_consumer(runtime)
    else:
        raise RuntimeError(f"Unsupported RUN_MODE={mode!r} (use api|worker|all)")

    app.state.orchestrator = runtime.orchestrator
    app.state.runtime = runtime
    try:
        yield
    finally:
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(
                shutdown_runtime(runtime),
                timeout=settings.shutdown_timeout_sec,
            )


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="AutoPulse Enrichment",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(RequestIdMiddleware)
    application.include_router(health_router)
    application.include_router(listings_router, prefix="/api/v1")

    @application.get("/metrics")
    async def metrics() -> Response:
        return Response(
            content=METRICS.render_prometheus(),
            media_type="text/plain; version=0.0.4",
        )

    application.state.settings = settings
    return application


app = create_app()
