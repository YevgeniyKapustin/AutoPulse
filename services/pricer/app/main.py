"""Market Pricer Service — FastAPI entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.pricer.app.api.health import router as health_router
from services.pricer.app.api.pricing import router as pricing_router
from services.pricer.app.consumers.enriched_listing_consumer import (
    EnrichedListingConsumer,
)
from services.pricer.app.core.config import get_settings
from services.pricer.app.core.logging import setup_logging
from services.pricer.app.core.middleware import RequestIdMiddleware
from services.pricer.app.services.pricing_service import PricingService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.log_level)
    pricing = PricingService(settings)
    consumer = EnrichedListingConsumer(settings, pricing)
    await consumer.start()
    app.state.pricing = pricing
    app.state.consumer = consumer
    try:
        yield
    finally:
        await consumer.stop()


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
    application.state.settings = settings
    return application


app = create_app()
