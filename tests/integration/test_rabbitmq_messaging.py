"""RabbitMQ topology publish/consume smoke against a real broker."""

from __future__ import annotations

import asyncio
import json

import aio_pika
import pytest
from testcontainers.rabbitmq import RabbitMqContainer

from services.enrichment.app.core.config import Settings as EnrichmentSettings
from services.enrichment.app.messaging.topology import (
    connect_robust,
    declare_topology,
)
from tests.integration.conftest import requires_docker

pytestmark = [pytest.mark.integration, requires_docker]


@pytest.mark.asyncio
async def test_rabbitmq_publish_and_consume_raw_queue() -> None:
    with RabbitMqContainer("rabbitmq:3.13.6-management-alpine") as rabbit:
        params = rabbit.get_connection_params()
        settings = EnrichmentSettings(
            rabbitmq_host=params.host,
            rabbitmq_port=params.port,
            rabbitmq_user=params.credentials.username
            if params.credentials
            else "guest",
            rabbitmq_password=params.credentials.password
            if params.credentials
            else "guest",
            rabbitmq_vhost=params.virtual_host or "/",
            enrichment_queue_name="enrichment.raw.test",
            enrichment_dlq_name="enrichment.dlq.test",
        )
        connection = await connect_robust(settings)
        try:
            channel = await connection.channel()
            exchange, queue, _dlq = await declare_topology(channel, settings)
            body = json.dumps({"hello": "world"}).encode("utf-8")
            await exchange.publish(
                aio_pika.Message(body=body, content_type="application/json"),
                routing_key=settings.routing_key_raw_created,
            )

            async def wait_message() -> bytes:
                incoming = await queue.get(fail=False, timeout=10)
                assert incoming is not None
                async with incoming.process():
                    return incoming.body

            received = await asyncio.wait_for(wait_message(), timeout=15)
            assert json.loads(received.decode("utf-8"))["hello"] == "world"
        finally:
            await connection.close()
