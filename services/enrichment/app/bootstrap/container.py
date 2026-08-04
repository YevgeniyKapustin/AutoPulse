"""Composition root: wire repositories, orchestrator, and messaging."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aio_pika.abc import AbstractChannel, AbstractRobustConnection
from motor.motor_asyncio import AsyncIOMotorClient

from services.enrichment.app.consumers.raw_listing_consumer import RawListingConsumer
from services.enrichment.app.core.circuit_breaker import CircuitBreaker
from services.enrichment.app.core.config import Settings
from services.enrichment.app.core.metrics import METRICS
from services.enrichment.app.messaging.outbox_sink import OutboxEventSink
from services.enrichment.app.messaging.publisher import EventPublisher
from services.enrichment.app.messaging.routes import PublishRoutes
from services.enrichment.app.messaging.topology import (
    connect_robust,
    declare_topology,
    open_publisher_channel,
)
from services.enrichment.app.repositories.listing_repository import ListingRepository
from services.enrichment.app.repositories.messaging_store import (
    InboxRepository,
    OutboxRepository,
)
from services.enrichment.app.cv import CvService
from services.enrichment.app.enrichment.orchestrator import (
    EnrichmentOrchestrator,
)
from services.enrichment.app.llm import LlmService


@dataclass
class EnrichmentRuntime:
    settings: Settings
    mongo_client: AsyncIOMotorClient[dict[str, Any]]
    repository: ListingRepository
    inbox: InboxRepository
    outbox: OutboxRepository
    orchestrator: EnrichmentOrchestrator
    consumer: RawListingConsumer | None = None
    publisher_connection: AbstractRobustConnection | None = None
    publisher_channel: AbstractChannel | None = None
    _routes: PublishRoutes | None = field(default=None, repr=False)


async def build_runtime(settings: Settings) -> EnrichmentRuntime:
    """Create Mongo repos, orchestrator, and messaging route table."""
    repository, mongo_client = ListingRepository.from_settings(
        settings.mongodb_uri,
        settings.mongodb_db,
        settings.mongodb_collection_listings,
    )
    await repository.ensure_indexes()
    inbox = InboxRepository.from_client(
        mongo_client,
        settings.mongodb_db,
        settings.mongodb_collection_inbox,
    )
    await inbox.ensure_indexes()
    outbox = OutboxRepository.from_client(
        mongo_client,
        settings.mongodb_db,
        settings.mongodb_collection_outbox,
    )
    await outbox.ensure_indexes()
    orchestrator = EnrichmentOrchestrator(
        repository=repository,
        llm=LlmService(settings, breaker=CircuitBreaker()),
        cv=CvService(),
    )
    return EnrichmentRuntime(
        settings=settings,
        mongo_client=mongo_client,
        repository=repository,
        inbox=inbox,
        outbox=outbox,
        orchestrator=orchestrator,
        _routes=PublishRoutes(
            raw_created=settings.routing_key_raw_created,
            enriched_success=settings.routing_key_enriched_success,
            enrichment_failed=settings.routing_key_enrichment_failed,
        ),
    )


async def attach_publisher(runtime: EnrichmentRuntime) -> None:
    """API mode: publish/enqueue without consuming the work queue.

    Startup ``drain()`` is multi-replica safe: each outbox row is claimed
    atomically (``pending`` → ``processing``) before publish.
    """
    assert runtime._routes is not None
    connection = await connect_robust(runtime.settings)
    channel = await open_publisher_channel(connection)
    await declare_topology(channel, runtime.settings)
    exchange = await channel.get_exchange(runtime.settings.rabbitmq_exchange)
    publisher = EventPublisher(exchange, runtime._routes, metrics=METRICS)
    sink = OutboxEventSink(runtime._routes, runtime.outbox, publisher)
    runtime.orchestrator.set_publisher(sink)
    await sink.drain()
    runtime.publisher_connection = connection
    runtime.publisher_channel = channel


async def start_consumer(runtime: EnrichmentRuntime) -> RawListingConsumer:
    """Declare topology and begin consuming the enrichment work queue."""
    consumer = RawListingConsumer(
        runtime.settings,
        runtime.orchestrator,
        inbox=runtime.inbox,
        outbox=runtime.outbox,
    )
    await consumer.start()
    runtime.consumer = consumer
    return consumer


async def shutdown_runtime(runtime: EnrichmentRuntime) -> None:
    """Stop the consumer and close Rabbit/Mongo connections.

    Consumer stop first so no new Mongo work remains; then Rabbit channels.
    ``mongo_client.close()`` is sync (Motor) and only runs after that drain.
    """
    if runtime.consumer is not None:
        await runtime.consumer.stop()
        runtime.consumer = None
    channel = runtime.publisher_channel
    if channel is not None and not channel.is_closed:
        await channel.close()
        runtime.publisher_channel = None
    connection = runtime.publisher_connection
    if connection is not None and not connection.is_closed:
        await connection.close()
        runtime.publisher_connection = None
    await runtime.orchestrator.aclose()
    runtime.mongo_client.close()
