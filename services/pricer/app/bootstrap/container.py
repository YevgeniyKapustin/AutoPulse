"""Composition root: wire MySQL, pricing service, and consumers."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass, field

from aio_pika.abc import AbstractChannel, AbstractRobustConnection
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from services.pricer.app.consumers.enriched_listing_consumer import (
    EnrichedListingConsumer,
)
from services.pricer.app.core.config import Settings
from services.pricer.app.core.metrics import METRICS
from services.pricer.app.db.session import (
    create_engine,
    create_schema,
    create_session_factory,
)
from services.pricer.app.messaging.outbox_publisher import OutboxPublisher
from services.pricer.app.messaging.retry import PricerRetryPublisher
from services.pricer.app.messaging.topology import (
    connect_robust,
    declare_topology,
    open_publisher_channel,
)
from services.pricer.app.repositories.pricing_repository import PricingRepository
from services.pricer.app.services.engine_factory import build_pricing_engine
from services.pricer.app.services.pricing_service import PricingService

logger = logging.getLogger(__name__)


@dataclass
class PricerRuntime:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    repository: PricingRepository
    pricing: PricingService
    consumer: EnrichedListingConsumer | None = None
    publisher_connection: AbstractRobustConnection | None = None
    publisher_channel: AbstractChannel | None = None
    outbox_publisher: OutboxPublisher | None = None
    retry_publisher: PricerRetryPublisher | None = None
    _outbox_drain_task: asyncio.Task[None] | None = field(default=None, repr=False)
    _outbox_drain_stop: asyncio.Event | None = field(default=None, repr=False)


async def build_runtime(settings: Settings) -> PricerRuntime:
    """Create MySQL engine, pricing service, and repository."""
    engine = create_engine(settings)
    try:
        if settings.auto_create_tables:
            await create_schema(engine)
        session_factory = create_session_factory(engine)
        repository = PricingRepository(session_factory, settings)
        pricing = PricingService(
            repository,
            build_pricing_engine(settings),
        )
        return PricerRuntime(
            settings=settings,
            engine=engine,
            session_factory=session_factory,
            repository=repository,
            pricing=pricing,
        )
    except Exception:
        await engine.dispose()
        raise


async def start_consumer(runtime: PricerRuntime) -> EnrichedListingConsumer:
    """Attach Rabbit publisher resources and begin consuming."""
    await _stop_outbox_drainer(runtime)
    if runtime.consumer is not None:
        await runtime.consumer.stop()
        runtime.consumer = None
    await _close_publisher(runtime)

    connection = await connect_robust(runtime.settings)
    pub_channel: AbstractChannel | None = None
    consume_channel: AbstractChannel | None = None
    try:
        pub_channel = await open_publisher_channel(connection)
        pub_topology = await declare_topology(pub_channel, runtime.settings)
        outbox = OutboxPublisher(
            pub_topology.exchange,
            runtime.repository,
            metrics=METRICS,
        )
        await outbox.drain()
        retry_publisher = PricerRetryPublisher(
            pub_topology.exchange,
            runtime.settings,
            metrics=METRICS,
        )
        runtime.publisher_connection = connection
        runtime.publisher_channel = pub_channel
        runtime.outbox_publisher = outbox
        runtime.retry_publisher = retry_publisher
        _start_outbox_drainer(runtime, outbox)

        consume_channel = await connection.channel()
        await consume_channel.set_qos(
            prefetch_count=runtime.settings.rabbitmq_prefetch,
        )
        work_topology = await declare_topology(consume_channel, runtime.settings)
        consumer = EnrichedListingConsumer(
            runtime.settings,
            runtime.pricing,
            inbox=runtime.repository,
            outbox_publisher=outbox,
            retry_publisher=retry_publisher,
            metrics=METRICS,
        )
        await consumer.start(
            channel=consume_channel,
            queue=work_topology.work_queue,
        )
    except Exception:
        if consume_channel is not None and not consume_channel.is_closed:
            await consume_channel.close()
        if pub_channel is not None and not pub_channel.is_closed:
            await pub_channel.close()
        if not connection.is_closed:
            await connection.close()
        raise

    runtime.consumer = consumer
    return consumer


async def shutdown_runtime(runtime: PricerRuntime) -> None:
    """Stop the consumer and dispose Rabbit/MySQL resources."""
    await _stop_outbox_drainer(runtime)
    if runtime.consumer is not None:
        await runtime.consumer.stop()
        runtime.consumer = None
    if runtime.outbox_publisher is not None:
        with suppress(Exception):
            await runtime.outbox_publisher.drain()
    await _close_publisher(runtime)
    await runtime.engine.dispose()


async def _close_publisher(runtime: PricerRuntime) -> None:
    runtime.retry_publisher = None
    runtime.outbox_publisher = None
    channel = runtime.publisher_channel
    if channel is not None and not channel.is_closed:
        await channel.close()
    runtime.publisher_channel = None
    connection = runtime.publisher_connection
    if connection is not None and not connection.is_closed:
        await connection.close()
    runtime.publisher_connection = None


def _start_outbox_drainer(runtime: PricerRuntime, publisher: OutboxPublisher) -> None:
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
                await publisher.drain()
            except Exception:
                logger.exception("Periodic pricer outbox drain failed")

    runtime._outbox_drain_stop = stop
    runtime._outbox_drain_task = asyncio.create_task(
        _loop(),
        name="pricer-outbox-drain",
    )


async def _stop_outbox_drainer(runtime: PricerRuntime) -> None:
    stop = runtime._outbox_drain_stop
    task = runtime._outbox_drain_task
    runtime._outbox_drain_stop = None
    runtime._outbox_drain_task = None
    if stop is not None:
        stop.set()
    if task is not None:
        with suppress(asyncio.CancelledError, Exception):
            await task
