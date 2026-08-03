"""MySQL pricing repository against a real MySQL container."""

from __future__ import annotations

import pytest
from testcontainers.mysql import MySqlContainer

from autopulse_shared.schemas.pricing import PricingResult
from services.pricer.app.db.session import (
    create_engine,
    create_schema,
    create_session_factory,
)
from services.pricer.app.core.config import Settings
from services.pricer.app.repositories.pricing_repository import PricingRepository
from tests.integration.conftest import requires_docker

pytestmark = [pytest.mark.integration, requires_docker]


@pytest.mark.asyncio
async def test_mysql_pricing_upsert_and_get() -> None:
    with MySqlContainer("mysql:8.4.3") as mysql:
        host = mysql.get_container_host_ip()
        port = int(mysql.get_exposed_port(3306))
        settings = Settings(
            mysql_host=host,
            mysql_port=port,
            mysql_user=mysql.username,
            mysql_password=mysql.password,
            mysql_database=mysql.dbname,
            auto_create_tables=True,
        )
        engine = create_engine(settings)
        try:
            await create_schema(engine)
            repo = PricingRepository(create_session_factory(engine))
            result = PricingResult(
                external_id="mysql-1",
                bid_price=10_000,
                recommended_dealer_bid=8_800,
                estimated_turnover_days=21,
                target_margin_pct=12.0,
                price_low=8_360,
                price_high=9_240,
            )
            await repo.save(result)
            loaded = await repo.get("mysql-1")
            assert loaded.recommended_dealer_bid == 8_800
            await repo.save(result.model_copy(update={"recommended_dealer_bid": 8_500}))
            assert (await repo.get("mysql-1")).recommended_dealer_bid == 8_500
        finally:
            await engine.dispose()
