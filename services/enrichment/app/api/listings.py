"""HTTP ingress for raw listings (also publishes to RabbitMQ)."""

from fastapi import APIRouter, Request, status

from autopulse_shared.schemas.listing import EnrichedListing, RawListing
from services.enrichment.app.services.enrichment_orchestrator import (
    EnrichmentOrchestrator,
)

router = APIRouter(prefix="/listings", tags=["listings"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def ingest_raw_listing(
    listing: RawListing,
    request: Request,
) -> dict[str, str]:
    """Accept raw listing JSON and enqueue enrichment (stub publish)."""
    request_id = getattr(request.state, "request_id", None)
    orchestrator: EnrichmentOrchestrator = request.app.state.orchestrator
    event_id = await orchestrator.enqueue_raw(listing, request_id=request_id)
    return {"status": "accepted", "event_id": event_id}


@router.get("/{external_id}")
async def get_listing_state(external_id: str, request: Request) -> EnrichedListing:
    orchestrator: EnrichmentOrchestrator = request.app.state.orchestrator
    return await orchestrator.get_state(external_id)
