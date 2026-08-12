"""Integration: Rabbit delivery → enrich → Mongo + outbox → ACK."""

from __future__ import annotations

import asyncio

import pytest
from testcontainers.mongodb import MongoDbContainer
from testcontainers.rabbitmq import RabbitMqContainer

from autopulse_shared.schemas.events import RawListingEvent
from autopulse_shared.schemas.listing import RawListing
from services.enrichment.app.bootstrap.container import (
    build_runtime,
    shutdown_runtime,
    start_consumer,
)
from services.enrichment.app.core.config import Settings
from services.enrichment.app.messaging.publisher import EventPublisher
from services.enrichment.app.messaging.routes import PublishRoutes
from services.enrichment.app.messaging.topology import (
    connect_robust,
    declare_topology,
    open_publisher_channel,
)
from tests.integration.conftest import requires_docker

pytestmark = [pytest.mark.integration, requires_docker]


def _settings(
    mongo_uri: str,
    rabbit: RabbitMqContainer,
) -> Settings:
    params = rabbit.get_connection_params()
    return Settings(
        llm_api_key="",
        metrics_enabled=False,
        mongodb_uri=mongo_uri,
        mongodb_db="autopulse_it",
        mongodb_collection_listings="listings_it",
        mongodb_collection_inbox="inbox_it",
        mongodb_collection_outbox="outbox_it",
        rabbitmq_host=params.host,
        rabbitmq_port=params.port,
        rabbitmq_user=params.credentials.username if params.credentials else "guest",
        rabbitmq_password=(
            params.credentials.password if params.credentials else "guest"
        ),
        rabbitmq_vhost=params.virtual_host or "/",
        rabbitmq_quorum_queues=True,
        enrichment_queue_name="enrichment.raw.it",
        enrichment_dlq_name="enrichment.dlq.it",
        enrichment_retry_queue_name="enrichment.retry.it",
        outbox_drain_interval_sec=60.0,
        rabbitmq_connection_name="autopulse-enrichment-it",
    )


@pytest.mark.asyncio
async def test_raw_event_enriched_and_acked_end_to_end() -> None:
    with (
        MongoDbContainer("mongo:7.0.16") as mongo,
        RabbitMqContainer("rabbitmq:3.13.6-management-alpine") as rabbit,
    ):
        settings = _settings(mongo.get_connection_url(), rabbit)
        runtime = await build_runtime(settings)
        try:
            await start_consumer(runtime)
            assert runtime.publisher_connection is not None
            assert runtime._routes is not None

            pub_connection = await connect_robust(settings)
            try:
                channel = await open_publisher_channel(pub_connection)
                topology = await declare_topology(channel, settings)
                publisher = EventPublisher(
                    topology.exchange,
                    PublishRoutes(
                        raw_created=settings.routing_key_raw_created,
                        enriched_success=settings.routing_key_enriched_success,
                        enrichment_failed=settings.routing_key_enrichment_failed,
                    ),
                )
                event = RawListingEvent(
                    listing=RawListing(
                        external_id="it-car-1",
                        description="M-Sport package, panorama roof",
                        asking_price=12_000,
                    ),
                    event_id="it-evt-1",
                )
                await publisher.publish_raw(event)

                async def wait_enriched() -> None:
                    while True:
                        listing = await runtime.repository.get_optional("it-car-1")
                        if listing is not None and listing.is_fully_enriched:
                            return
                        await asyncio.sleep(0.1)

                await asyncio.wait_for(wait_enriched(), timeout=20)

                listing = await runtime.repository.get("it-car-1")
                assert listing.llm_done and listing.cv_done
                assert "M-Sport" in listing.options.packages

                inbox = await runtime.inbox._collection.find_one(
                    {"event_id": "it-evt-1"},
                )
                assert inbox is not None
                assert inbox["status"] == "completed"

                outbox_count = await runtime.outbox._collection.count_documents(
                    {"status": "published"},
                )
                assert outbox_count >= 1
            finally:
                await pub_connection.close()
        finally:
            await shutdown_runtime(runtime)
