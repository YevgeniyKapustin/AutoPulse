import pytest

from autopulse_shared.schemas.listing import RawListing
from services.enrichment.app.core.circuit_breaker import CircuitBreaker, CircuitOpenError
from services.enrichment.app.core.config import Settings
from services.enrichment.app.services.llm_service import LlmService


@pytest.mark.asyncio
async def test_heuristic_extracts_m_sport_and_panorama() -> None:
    settings = Settings(llm_api_key="")
    llm = LlmService(settings, breaker=CircuitBreaker(failure_threshold=10))
    listing = RawListing(
        external_id="x1",
        title="BMW 320i",
        description="M-Sport package, panorama roof, one owner",
    )
    options = await llm.extract_options(listing)
    assert "M-Sport" in options.packages
    assert "panorama" in options.features
    assert options.owner_count == 1


@pytest.mark.asyncio
async def test_circuit_opens_and_blocks_llm() -> None:
    settings = Settings(llm_api_key="")
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_sec=60)
    llm = LlmService(settings, breaker=breaker)
    breaker.record_failure()
    with pytest.raises(CircuitOpenError):
        await llm.extract_options(RawListing(external_id="x2", description="x"))
