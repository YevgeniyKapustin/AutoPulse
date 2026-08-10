"""Wire dealer pipeline UI services."""

from __future__ import annotations

from contextlib import suppress

from services.enrichment.app.admin.pricer_client import HttpPricerAdminClient
from services.enrichment.app.bootstrap.container import EnrichmentRuntime
from services.enrichment.app.dealer.crawler_client import HttpCrawlerClient
from services.enrichment.app.dealer.service import DealerService


class DealerBundle:
    def __init__(
        self,
        service: DealerService,
        pricer_client: HttpPricerAdminClient,
        crawler_client: HttpCrawlerClient,
    ) -> None:
        self.service = service
        self.pricer_client = pricer_client
        self.crawler_client = crawler_client

    async def aclose(self) -> None:
        with suppress(Exception):
            await self.pricer_client.aclose()
        with suppress(Exception):
            await self.crawler_client.aclose()


async def build_dealer_bundle(runtime: EnrichmentRuntime) -> DealerBundle | None:
    """Create dealer service when DEALER_UI_ENABLED."""
    if not runtime.settings.dealer_ui_enabled:
        return None
    pricer_client = HttpPricerAdminClient(
        runtime.settings.pricer_base_url,
        timeout_sec=runtime.settings.pricer_admin_timeout_sec,
    )
    crawler_client = HttpCrawlerClient(
        runtime.settings.crawler_base_url,
        timeout_sec=runtime.settings.crawler_timeout_sec,
    )
    service = DealerService(
        ingestor=runtime.orchestrator,
        listings=runtime.orchestrator,
        pricer=pricer_client,
        crawler=crawler_client,
    )
    return DealerBundle(service, pricer_client, crawler_client)
