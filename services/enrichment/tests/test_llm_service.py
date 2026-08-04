import httpx
import pytest
from services.enrichment.app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)
from services.enrichment.app.core.config import Settings
from services.enrichment.app.core.exceptions import EnrichmentError
from services.enrichment.app.llm import LlmService

from autopulse_shared.schemas.listing import RawListing


@pytest.mark.asyncio
async def test_heuristic_extracts_m_sport_and_panorama() -> None:
    settings = Settings(llm_api_key="")
    async with LlmService(
        settings,
        breaker=CircuitBreaker(failure_threshold=10),
    ) as llm:
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
async def test_heuristic_bypasses_open_circuit() -> None:
    settings = Settings(llm_api_key="")
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_sec=60)
    await breaker.record_failure()
    async with LlmService(settings, breaker=breaker) as llm:
        options = await llm.extract_options(
            RawListing(external_id="x2", description="leather seats"),
        )
        assert "leather" in options.features
        assert "heuristic" in options.tags


@pytest.mark.asyncio
async def test_circuit_opens_and_blocks_api_path() -> None:
    settings = Settings(llm_api_key="sk-test")
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_sec=60)
    await breaker.record_failure()
    async with LlmService(settings, breaker=breaker) as llm:
        with pytest.raises(CircuitOpenError):
            await llm.extract_options(RawListing(external_id="x3", description="x"))


@pytest.mark.asyncio
async def test_parse_error_does_not_trip_circuit() -> None:
    settings = Settings(llm_api_key="sk-test")
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_sec=60)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {}}]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        async with LlmService(
            settings,
            breaker=breaker,
            http_client=client,
        ) as llm:
            with pytest.raises(EnrichmentError, match="parsing error"):
                await llm.extract_options(
                    RawListing(external_id="x4", description="x"),
                )
            assert breaker.state == CircuitState.CLOSED
            assert breaker.failures == 0
