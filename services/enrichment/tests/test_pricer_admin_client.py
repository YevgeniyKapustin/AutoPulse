"""Pricer admin client auth wiring."""

import httpx
import pytest
from services.enrichment.app.admin.pricer_client import HttpPricerAdminClient


@pytest.mark.asyncio
async def test_owned_client_sets_basic_auth() -> None:
    admin = HttpPricerAdminClient(
        "http://pricer.test",
        username="autopulse",
        password="secret",
    )
    try:
        assert admin._http.auth is not None
    finally:
        await admin.aclose()


@pytest.mark.asyncio
async def test_owned_client_skips_auth_without_password() -> None:
    admin = HttpPricerAdminClient("http://pricer.test", password=None)
    try:
        assert admin._http.auth is None
    finally:
        await admin.aclose()


@pytest.mark.asyncio
async def test_overview_sends_basic_authorization_header() -> None:
    seen: dict[str, str | None] = {"authorization": None}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization")
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    admin = HttpPricerAdminClient(
        "http://pricer.test",
        http_client=httpx.AsyncClient(
            base_url="http://pricer.test",
            transport=transport,
            auth=("autopulse", "secret"),
        ),
    )
    try:
        assert await admin.overview() == {"ok": True}
        assert seen["authorization"]
        assert seen["authorization"].lower().startswith("basic ")
    finally:
        await admin.aclose()
