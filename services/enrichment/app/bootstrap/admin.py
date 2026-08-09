"""Wire ops admin aggregators for the enrichment API process."""

from __future__ import annotations

from contextlib import suppress

from services.enrichment.app.admin.pricer_client import HttpPricerAdminClient
from services.enrichment.app.admin.service import AdminService
from services.enrichment.app.bootstrap.container import EnrichmentRuntime
from services.enrichment.app.bootstrap.readiness import check_readiness
from services.enrichment.app.messaging.queue_stats import RabbitQueueStats


class AdminBundle:
    def __init__(
        self,
        service: AdminService,
        queue_stats: RabbitQueueStats,
        pricer_client: HttpPricerAdminClient,
    ) -> None:
        self.service = service
        self.queue_stats = queue_stats
        self.pricer_client = pricer_client

    async def aclose(self) -> None:
        with suppress(Exception):
            await self.queue_stats.aclose()
        with suppress(Exception):
            await self.pricer_client.aclose()


async def build_admin_bundle(runtime: EnrichmentRuntime) -> AdminBundle | None:
    """Create admin service + HTTP clients when ADMIN_UI_ENABLED."""
    if not runtime.settings.admin_ui_enabled:
        return None
    settings = runtime.settings
    queue_stats = RabbitQueueStats(
        settings.rabbitmq_management_url,
        username=settings.rabbitmq_user,
        password=settings.rabbitmq_password,
        vhost=settings.rabbitmq_vhost,
    )
    pricer_client = HttpPricerAdminClient(
        settings.pricer_base_url,
        timeout_sec=settings.pricer_admin_timeout_sec,
    )

    async def readiness_probe() -> tuple[bool, dict[str, str]]:
        return await check_readiness(runtime)

    service = AdminService(
        settings=settings,
        listings=runtime.repository,
        inbox=runtime.inbox,
        outbox=runtime.outbox,
        queues=queue_stats,
        pricer=pricer_client,
        re_enricher=runtime.orchestrator,
        readiness_probe=readiness_probe,
    )
    return AdminBundle(service, queue_stats, pricer_client)
