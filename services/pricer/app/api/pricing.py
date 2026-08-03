from fastapi import APIRouter, Request

from autopulse_shared.schemas.listing import EnrichedListing
from autopulse_shared.schemas.pricing import PricingResult
from services.pricer.app.services.pricing_service import PricingService

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.post("/estimate", response_model=PricingResult)
async def estimate_price(
    listing: EnrichedListing,
    request: Request,
) -> PricingResult:
    pricing: PricingService = request.app.state.pricing
    return await pricing.price(listing)


@router.get("/{external_id}", response_model=PricingResult)
async def get_pricing(external_id: str, request: Request) -> PricingResult:
    pricing: PricingService = request.app.state.pricing
    return await pricing.get_result(external_id)
