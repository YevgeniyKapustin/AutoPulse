"""Crawler FastAPI application."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from services.crawler.app.adapters import AdapterRegistry
from services.crawler.app.api.health import router as health_router
from services.crawler.app.api.ingest import router as ingest_router
from services.crawler.app.core.config import Settings, get_settings
from services.crawler.app.core.logging import setup_logging
from services.crawler.app.core.middleware import RequestIdMiddleware
from services.crawler.app.messaging.publisher import EnrichmentHttpPublisher
from services.crawler.app.service import IngestService


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    setup_logging(
        service="crawler",
        environment=cfg.environment,
        level=cfg.log_level,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        publisher = EnrichmentHttpPublisher(
            cfg.enrichment_base_url,
            timeout_sec=cfg.enrichment_timeout_sec,
        )
        app.state.publisher = publisher
        app.state.ingest = IngestService(
            registry=AdapterRegistry(),
            publisher=publisher,
        )
        try:
            yield
        finally:
            await publisher.aclose()

    application = FastAPI(title="AutoPulse Crawler", lifespan=lifespan)
    application.add_middleware(RequestIdMiddleware)
    application.state.settings = cfg
    application.include_router(health_router)
    application.include_router(ingest_router, prefix="/api/v1")
    return application


app = create_app()
