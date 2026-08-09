"""Composition root: wire repositories, orchestrator, and messaging."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from aio_pika.abc import AbstractChannel, AbstractRobustConnection
from motor.motor_asyncio import AsyncIOMotorClient

from services.enrichment.app.consumers.raw_listing_consumer import RawListingConsumer
from services.enrichment.app.core.config import Settings
from services.enrichment.app.core.metrics import METRICS
from services.enrichment.app.cv.factory import build_cv_service
from services.enrichment.app.enrichment.orchestrator import (
    EnrichmentOrchestrator,
)
from services.enrichment.app.llm import LlmService
from services.enrichment.app.messaging.outbox_sink import OutboxEventSink
from services.enrichment.app.messaging.publisher import EventPublisher
from services.enrichment.app.messaging.retry import EnrichmentRetryPublisher
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

logger = logging.getLogger(__name__)


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
    retry_publisher: EnrichmentRetryPublisher | None = None
    outbox_sink: OutboxEventSink | None = None
    _routes: PublishRoutes | None = field(default=None, repr=False)
    _outbox_drain_task: asyncio.Task[None] | None = field(default=None, repr=False)
    _outbox_drain_stop: asyncio.Event | None = field(default=None, repr=False)


async def build_runtime(settings: Settings) -> EnrichmentRuntime:
    """Create Mongo repos, orchestrator, and messaging route table."""
    mongo_client: AsyncIOMotorClient[dict[str, Any]] | None = None
    try:
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
            llm=LlmService(settings),
            cv=build_cv_service(settings),
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
    except Exception:
        if mongo_client is not None:
            mongo_client.close()
        raise


async def attach_publisher(runtime: EnrichmentRuntime) -> None:
    """Wire Rabbit publisher + outbox sink onto the orchestrator.

    Idempotent: closes a prior publisher connection first so
    reconnect/restart does not leak channels.
    """
    assert runtime._routes is not None
    await _stop_outbox_drainer(runtime)
    await _close_publisher(runtime)

    connection = await connect_robust(runtime.settings)
    channel: AbstractChannel | None = None
    try:
        channel = await open_publisher_channel(connection)
        topology = await declare_topology(channel, runtime.settings)
        publisher = EventPublisher(topology.exchange, runtime._routes, metrics=METRICS)
        sink = OutboxEventSink(runtime._routes, runtime.outbox, publisher)
        runtime.orchestrator.set_publisher(sink)
        await sink.drain()
        runtime.publisher_connection = connection
        runtime.publisher_channel = channel
        runtime.outbox_sink = sink
        runtime.retry_publisher = EnrichmentRetryPublisher(
            topology.exchange,
            runtime.settings,
            metrics=METRICS,
        )
        _start_outbox_drainer(runtime, sink)
    except Exception:
        if channel is not None and not channel.is_closed:
            await channel.close()
        if not connection.is_closed:
            await connection.close()
        raise


async def start_consumer(runtime: EnrichmentRuntime) -> RawListingConsumer:
    """Attach messaging if needed, then start the work-queue consumer.

    Opens a dedicated consume channel and transfers ownership to
    ``RawListingConsumer.start`` (closed on ``stop``).
    """
    if runtime.publisher_connection is None:
        await attach_publisher(runtime)
    assert runtime.publisher_connection is not None
    assert runtime.retry_publisher is not None

    # Close a previous consume channel before opening another (no zombie
    # chans).
    if runtime.consumer is not None:
        await runtime.consumer.stop()
        runtime.consumer = None

    channel = await runtime.publisher_connection.channel()
    try:
        await channel.set_qos(prefetch_count=runtime.settings.rabbitmq_prefetch)
        topology = await declare_topology(channel, runtime.settings)

        consumer = RawListingConsumer(
            runtime.settings,
            runtime.orchestrator,
            runtime.retry_publisher,
            inbox=runtime.inbox,
            metrics=METRICS,
        )
        await consumer.start(channel=channel, queue=topology.work_queue)
    except Exception:
        if not channel.is_closed:
            await channel.close()
        raise
    runtime.consumer = consumer
    return consumer


async def shutdown_runtime(runtime: EnrichmentRuntime) -> None:
    """Stop the consumer and close Rabbit/Mongo connections.

    Consumer stop first so no new Mongo work remains; then Rabbit
    channels. ``mongo_client.close()`` is sync and runs after drain.
    """
    await _stop_outbox_drainer(runtime)
    if runtime.consumer is not None:
        await runtime.consumer.stop()
        runtime.consumer = None
    if runtime.outbox_sink is not None:
        with suppress(Exception):
            await runtime.outbox_sink.drain()
    await _close_publisher(runtime)
    await runtime.orchestrator.aclose()
    runtime.mongo_client.close()


async def _close_publisher(runtime: EnrichmentRuntime) -> None:
    runtime.retry_publisher = None
    runtime.outbox_sink = None
    channel = runtime.publisher_channel
    if channel is not None and not channel.is_closed:
        await channel.close()
    runtime.publisher_channel = None
    connection = runtime.publisher_connection
    if connection is not None and not connection.is_closed:
        await connection.close()
    runtime.publisher_connection = None


def _start_outbox_drainer(runtime: EnrichmentRuntime, sink: OutboxEventSink) -> None:
    stop = asyncio.Event()
    interval = runtime.settings.outbox_drain_interval_sec

    async def _loop() -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                return
            except TimeoutError:
                pass
            try:
                await sink.drain()
            except Exception:
                logger.exception("Periodic outbox drain failed")

    runtime._outbox_drain_stop = stop
    runtime._outbox_drain_task = asyncio.create_task(_loop(), name="outbox-drain")


async def _stop_outbox_drainer(runtime: EnrichmentRuntime) -> None:
    stop = runtime._outbox_drain_stop
    task = runtime._outbox_drain_task
    runtime._outbox_drain_stop = None
    runtime._outbox_drain_task = None
    if stop is not None:
        stop.set()
    if task is not None:
        with suppress(asyncio.CancelledError, Exception):
            await task
