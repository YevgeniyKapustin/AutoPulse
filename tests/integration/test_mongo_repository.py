"""Mongo listing repository against a real MongoDB container."""

from __future__ import annotations

import pytest
from testcontainers.mongodb import MongoDbContainer

from autopulse_shared.schemas.listing import EnrichedListing, ListingSource
from services.enrichment.app.repositories.listing_repository import ListingRepository
from tests.integration.conftest import requires_docker

pytestmark = [pytest.mark.integration, requires_docker]


@pytest.mark.asyncio
async def test_mongo_upsert_and_get() -> None:
    with MongoDbContainer("mongo:7.0.16") as mongo:
        uri = mongo.get_connection_url()
        repo, client = ListingRepository.from_settings(
            uri,
            "autopulse_test",
            "listings",
        )
        try:
            await repo.ensure_indexes()
            listing = EnrichedListing(
                external_id="mongo-1",
                source=ListingSource.MANUAL,
                title="Test car",
                asking_price=1000,
                llm_done=True,
                cv_done=True,
            )
            await repo.upsert(listing)
            loaded = await repo.get("mongo-1")
            assert loaded.external_id == "mongo-1"
            assert loaded.is_fully_enriched
            assert await repo.get_optional("missing") is None
        finally:
            client.close()
