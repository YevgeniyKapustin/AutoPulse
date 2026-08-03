"""RabbitMQ topology: topic exchange, work queue, DLQ."""

from __future__ import annotations

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractRobustQueue

from services.enrichment.app.core.config import Settings

async def declare_topology(
    channel: AbstractChannel,
    settings: Settings,
) -> tuple[AbstractExchange, AbstractRobustQueue, AbstractRobustQueue]:
    exchange = await channel.declare_exchange(
        settings.rabbitmq_exchange,
        ExchangeType.TOPIC,
        durable=True,
    )

    dlq = await channel.declare_queue(settings.enrichment_dlq_name, durable=True)
    await dlq.bind(exchange, routing_key=settings.routing_key_enrichment_dlq)

    queue = await channel.declare_queue(
        settings.enrichment_queue_name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": settings.rabbitmq_exchange,
            "x-dead-letter-routing-key": settings.routing_key_enrichment_dlq,
        },
    )
    await queue.bind(exchange, routing_key=settings.routing_key_raw_created)
    return exchange, queue, dlq


async def connect_robust(settings: Settings) -> aio_pika.RobustConnection:
    return await aio_pika.connect_robust(settings.rabbitmq_url)
