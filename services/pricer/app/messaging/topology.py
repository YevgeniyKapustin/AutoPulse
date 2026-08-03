"""RabbitMQ topology for the pricer service."""

from __future__ import annotations

from typing import Any

from aio_pika import ExchangeType, connect_robust as aio_connect_robust
from aio_pika.abc import (
    AbstractChannel,
    AbstractExchange,
    AbstractQueue,
    AbstractRobustConnection,
)

from services.pricer.app.core.config import Settings


async def declare_topology(
    channel: AbstractChannel,
    settings: Settings,
) -> tuple[AbstractExchange, AbstractQueue, AbstractQueue]:
    exchange = await channel.declare_exchange(
        settings.rabbitmq_exchange,
        ExchangeType.TOPIC,
        durable=True,
    )

    dlq_args: dict[str, Any] = {}
    work_args: dict[str, Any] = {
        "x-dead-letter-exchange": settings.rabbitmq_exchange,
        "x-dead-letter-routing-key": settings.routing_key_pricer_dlq,
    }
    if settings.rabbitmq_quorum_queues:
        dlq_args["x-queue-type"] = "quorum"
        work_args["x-queue-type"] = "quorum"

    dlq = await channel.declare_queue(
        settings.pricer_dlq_name,
        durable=True,
        arguments=dlq_args or None,
    )
    await dlq.bind(exchange, routing_key=settings.routing_key_pricer_dlq)

    queue = await channel.declare_queue(
        settings.pricer_queue_name,
        durable=True,
        arguments=work_args,
    )
    await queue.bind(exchange, routing_key=settings.routing_key_enriched_success)
    return exchange, queue, dlq


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
