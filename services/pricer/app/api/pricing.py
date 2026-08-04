"""HTTP pricing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from autopulse_shared.schemas.errors import ErrorResponse
from autopulse_shared.schemas.listing import EnrichedListing
from autopulse_shared.schemas.pricing import PricingResult
from services.pricer.app.services.pricing_service import PricingService

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.post("/estimate", response_model=PricingResult)
async def estimate_price(
    listing: EnrichedListing,
    request: Request,
) -> PricingResult:
    """Compute a price for an enriched listing without requiring a prior row."""
    pricing: PricingService = request.app.state.pricing
    return await pricing.price(listing)


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
    """Return a stored pricing result; 404 via domain exception handler."""
    pricing: PricingService = request.app.state.pricing
    return await pricing.get_result(external_id)
