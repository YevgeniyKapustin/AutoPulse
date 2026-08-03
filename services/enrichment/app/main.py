"""Data Enrichment Service — FastAPI entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.enrichment.app.api.health import router as health_router
from services.enrichment.app.api.listings import router as listings_router
from services.enrichment.app.core.config import get_settings
from services.enrichment.app.core.logging import setup_logging
from services.enrichment.app.core.middleware import RequestIdMiddleware
from services.enrichment.app.consumers.raw_listing_consumer import RawListingConsumer
from services.enrichment.app.repositories.listing_repository import ListingRepository
from services.enrichment.app.services.cv_service import CvService
from services.enrichment.app.services.enrichment_orchestrator import (
    EnrichmentOrchestrator,
)
from services.enrichment.app.services.llm_service import LlmService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.log_level)
    orchestrator = EnrichmentOrchestrator(
        repository=ListingRepository(),
        llm=LlmService(),
        cv=CvService(),
    )
    consumer = RawListingConsumer(settings)
    await consumer.start()
    app.state.orchestrator = orchestrator
    app.state.consumer = consumer
    try:
        yield
    finally:
        await consumer.stop()


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
    application.state.settings = settings
    return application


app = create_app()
