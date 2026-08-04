"""RabbitMQ topology: topic exchange, quorum work queue, retry TTL, DLQ."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aio_pika import ExchangeType, connect_robust as aio_connect_robust
from aio_pika.abc import (
    AbstractChannel,
    AbstractExchange,
    AbstractQueue,
    AbstractRobustConnection,
)

from services.enrichment.app.core.config import Settings


@dataclass(frozen=True, slots=True)
class DeclaredTopology:
    exchange: AbstractExchange
    work_queue: AbstractQueue
    dlq: AbstractQueue
    retry_queue: AbstractQueue


def _queue_type_args(settings: Settings) -> dict[str, Any]:
    if settings.rabbitmq_quorum_queues:
        return {"x-queue-type": "quorum"}
    return {}


async def declare_topology(
    channel: AbstractChannel,
    settings: Settings,
) -> DeclaredTopology:
    exchange = await channel.declare_exchange(
        settings.rabbitmq_exchange,
        ExchangeType.TOPIC,
        durable=True,
    )

    type_args = _queue_type_args(settings)

    dlq = await channel.declare_queue(
        settings.enrichment_dlq_name,
        durable=True,
        arguments=type_args or None,
    )
    await dlq.bind(exchange, routing_key=settings.routing_key_enrichment_dlq)

    # Failed consumers reject → DLQ. TTL retry queue dead-letters back to work.
    work_args: dict[str, Any] = {
        **type_args,
        "x-dead-letter-exchange": settings.rabbitmq_exchange,
        "x-dead-letter-routing-key": settings.routing_key_enrichment_dlq,
    }
    work_queue = await channel.declare_queue(
        settings.enrichment_queue_name,
        durable=True,
        arguments=work_args,
    )
    await work_queue.bind(exchange, routing_key=settings.routing_key_raw_created)

    retry_args: dict[str, Any] = {
        **type_args,
        "x-dead-letter-exchange": settings.rabbitmq_exchange,
        "x-dead-letter-routing-key": settings.routing_key_raw_created,
    }
    retry_queue = await channel.declare_queue(
        settings.enrichment_retry_queue_name,
        durable=True,
        arguments=retry_args,
    )
    await retry_queue.bind(
        exchange,
        routing_key=settings.routing_key_enrichment_retry,
    )

    return DeclaredTopology(
        exchange=exchange,
        work_queue=work_queue,
        dlq=dlq,
        retry_queue=retry_queue,
    )


async def connect_robust(settings: Settings) -> AbstractRobustConnection:
    return await aio_connect_robust(
        settings.rabbitmq_url,
        timeout=settings.rabbitmq_connect_timeout_sec,
        heartbeat=settings.rabbitmq_heartbeat_sec,
        client_properties={
            "connection_name": settings.rabbitmq_connection_name,
        },
    )


async def open_publisher_channel(
    connection: AbstractRobustConnection,
) -> AbstractChannel:
    return await connection.channel(
        publisher_confirms=True,
        on_return_raises=True,
    )
