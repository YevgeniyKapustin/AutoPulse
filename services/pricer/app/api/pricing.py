"""HTTP pricing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from autopulse_shared.schemas.errors import ErrorResponse
from autopulse_shared.schemas.listing import EnrichedListing
from autopulse_shared.schemas.pricing import PricingResult
from services.pricer.app.services.ports import PricingCommand

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.post("/estimate", response_model=PricingResult)
async def estimate_price(
    listing: EnrichedListing,
    request: Request,
) -> PricingResult:
    """Compute a dry-run price (no MySQL write / outbox)."""
    pricing: PricingCommand = request.app.state.pricing
    return pricing.evaluate(listing)


@router.post("", response_model=PricingResult)
async def price_listing(
    listing: EnrichedListing,
    request: Request,
) -> PricingResult:
    """Persist a price snapshot and enqueue ``car.priced.success``."""
    pricing: PricingCommand = request.app.state.pricing
    request_id: str | None = getattr(request.state, "request_id", None)
    return await pricing.price(listing, request_id=request_id)


@router.get(
    "/{external_id}",
    response_model=PricingResult,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Pricing result for external_id was not found",
            "model": ErrorResponse,
        }
    },
)
async def get_pricing(external_id: str, request: Request) -> PricingResult:
    """Return stored pricing; 404 via domain exception handler."""
    pricing: PricingCommand = request.app.state.pricing
    return await pricing.get_result(external_id)
