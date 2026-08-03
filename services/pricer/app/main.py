"""Pricer FastAPI entrypoint (API or combined local mode)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Response

from services.pricer.app.api.health import router as health_router
from services.pricer.app.api.pricing import router as pricing_router
from services.pricer.app.core.config import get_settings
from services.pricer.app.core.logging import setup_logging
from services.pricer.app.core.metrics import METRICS
from services.pricer.app.core.middleware import RequestIdMiddleware
from services.pricer.app.runtime import (
    build_runtime,
    shutdown_runtime,
    start_consumer,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.log_level)
    mode = settings.run_mode
    if mode == "worker":
        raise RuntimeError(
            "RUN_MODE=worker requires services.pricer.app.worker, not uvicorn"
        )

    runtime = await build_runtime(settings)
    if mode == "all":
        await start_consumer(runtime)
    elif mode != "api":
        raise RuntimeError(f"Unsupported RUN_MODE={mode!r} (use api|worker|all)")

    app.state.pricing = runtime.pricing
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
        title="AutoPulse Pricer",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(RequestIdMiddleware)
    application.include_router(health_router)
    application.include_router(pricing_router, prefix="/api/v1")

    @application.get("/metrics")
    async def metrics() -> Response:
        return Response(
            content=METRICS.render_prometheus(),
            media_type="text/plain; version=0.0.4",
        )

    application.state.settings = settings
    return application


app = create_app()
