"""Shared wiring for pricer API and worker processes."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from services.pricer.app.consumers.enriched_listing_consumer import (
    EnrichedListingConsumer,
)
from services.pricer.app.core.config import Settings
from services.pricer.app.db.session import (
    create_engine,
    create_schema,
    create_session_factory,
)
from services.pricer.app.repositories.pricing_repository import PricingRepository
from services.pricer.app.services.pricing_service import PricingService


@dataclass
class PricerRuntime:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    repository: PricingRepository
    pricing: PricingService
    consumer: EnrichedListingConsumer | None = None


async def build_runtime(settings: Settings) -> PricerRuntime:
    engine = create_engine(settings)
    if settings.auto_create_tables:
        await create_schema(engine)
    session_factory = create_session_factory(engine)
    repository = PricingRepository(session_factory, settings)
    pricing = PricingService(settings, repository)
    return PricerRuntime(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        repository=repository,
        pricing=pricing,
    )


async def start_consumer(runtime: PricerRuntime) -> EnrichedListingConsumer:
    consumer = EnrichedListingConsumer(
        runtime.settings,
        runtime.pricing,
        repository=runtime.repository,
    )
    await consumer.start()
    runtime.consumer = consumer
    return consumer


async def shutdown_runtime(runtime: PricerRuntime) -> None:
    if runtime.consumer is not None:
        await runtime.consumer.stop()
        runtime.consumer = None
    await runtime.engine.dispose()
