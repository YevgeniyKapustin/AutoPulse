"""Data Enrichment Service — FastAPI entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.enrichment.app.api.health import router as health_router
from services.enrichment.app.api.listings import router as listings_router
from services.enrichment.app.consumers.raw_listing_consumer import RawListingConsumer
from services.enrichment.app.core.circuit_breaker import CircuitBreaker
from services.enrichment.app.core.config import get_settings
from services.enrichment.app.core.logging import setup_logging
from services.enrichment.app.core.middleware import RequestIdMiddleware
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

    repository, mongo_client = ListingRepository.from_settings(
        settings.mongodb_uri,
        settings.mongodb_db,
        settings.mongodb_collection_listings,
    )
    await repository.ensure_indexes()

    llm = LlmService(settings, breaker=CircuitBreaker())
    cv = CvService()
    orchestrator = EnrichmentOrchestrator(
        repository=repository,
        llm=llm,
        cv=cv,
    )
    consumer = RawListingConsumer(settings, orchestrator)
    await consumer.start()

    app.state.orchestrator = orchestrator
    app.state.consumer = consumer
    app.state.mongo_client = mongo_client
    try:
        yield
    finally:
        await consumer.stop()
        mongo_client.close()


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
