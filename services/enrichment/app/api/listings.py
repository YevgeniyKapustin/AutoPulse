"""HTTP ingress for raw listings (publishes to RabbitMQ)."""

from __future__ import annotations

from typing import Literal, TypedDict

from fastapi import APIRouter, Request, status

from autopulse_shared.schemas.errors import ErrorResponse
from autopulse_shared.schemas.listing import EnrichedListing, RawListing
from services.enrichment.app.services.enrichment_orchestrator import (
    EnrichmentOrchestrator,
)

router = APIRouter(prefix="/listings", tags=["listings"])


class IngestAcceptedResponse(TypedDict):
    status: Literal["accepted"]
    event_id: str


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def ingest_raw_listing(
    listing: RawListing,
    request: Request,
) -> IngestAcceptedResponse:
    """Accept raw listing JSON and enqueue enrichment."""
    request_id: str | None = getattr(request.state, "request_id", None)
    orchestrator: EnrichmentOrchestrator = request.app.state.orchestrator
    event_id: str = await orchestrator.enqueue_raw(listing, request_id=request_id)
    return {"status": "accepted", "event_id": event_id}


@router.get(
    "/{external_id}",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Listing for external_id was not found",
            "model": ErrorResponse,
        }
    },
)
async def get_listing_state(external_id: str, request: Request) -> EnrichedListing:
    """Return the current enriched listing document for ``external_id``."""
    orchestrator: EnrichmentOrchestrator = request.app.state.orchestrator
    return await orchestrator.get_state(external_id)
