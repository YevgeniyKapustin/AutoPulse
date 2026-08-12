"""Unit tests for heuristic CV without network."""

from io import BytesIO

import httpx
import pytest
from PIL import Image
from pydantic import HttpUrl
from services.enrichment.app.cv import CvService, ImageAnalyzer
from services.enrichment.app.cv.defects import license_plate_detected
from services.enrichment.app.cv.service import _MAX_DOWNLOAD_BYTES


def _jpeg_bytes(color: tuple[int, int, int], size: tuple[int, int] = (32, 32)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="JPEG")
    return buf.getvalue()


def test_analyze_dark_image_flags_defect() -> None:
    analyzer = ImageAnalyzer()
    defects = analyzer.inspect(
        _jpeg_bytes((5, 5, 5), (64, 64)),
        HttpUrl("https://example.com/dark.jpg"),
    )
    assert any(d.label == "very_dark_image" for d in defects)


def test_decompression_bomb_is_rejected() -> None:
    analyzer = ImageAnalyzer()
    original = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = 100
    try:
        # 20x20 = 400 pixels > cap → DecompressionBombError on load.
        defects = analyzer.inspect(
            _jpeg_bytes((1, 1, 1), (20, 20)),
            HttpUrl("https://example.com/bomb.jpg"),
        )
        assert any(d.label == "image_too_large" for d in defects)
    finally:
        Image.MAX_IMAGE_PIXELS = original


@pytest.mark.asyncio
async def test_oversized_download_is_rejected() -> None:
    url = "https://cdn.example.com/huge.bin"

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == url
        return httpx.Response(200, content=b"x" * (_MAX_DOWNLOAD_BYTES + 1))

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)

    class _Listing:
        image_urls = [HttpUrl(url)]

    try:
        async with CvService(http_client=client) as cv:
            defects = await cv.detect_defects(_Listing())  # type: ignore[arg-type]
    finally:
        await client.aclose()

    assert any(d.label == "image_too_large" for d in defects)


@pytest.mark.asyncio
async def test_images_fetched_concurrently() -> None:
    urls = [
        "https://cdn.example.com/a.jpg",
        "https://cdn.example.com/b.jpg",
    ]
    seen: list[str] = []
    body = _jpeg_bytes((128, 128, 128))

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, content=body)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)

    class _Listing:
        image_urls = [HttpUrl(u) for u in urls]

    # Brightness-only: ignore watermark heuristics in this test.
    analyzer = ImageAnalyzer(checks=(ImageAnalyzer._check_brightness,))
    try:
        async with CvService(http_client=client, analyzer=analyzer) as cv:
            defects = await cv.detect_defects(_Listing())  # type: ignore[arg-type]
    finally:
        await client.aclose()

    assert defects == []
    assert set(seen) == set(urls)


@pytest.mark.asyncio
async def test_fake_plate_check_emits_bbox() -> None:
    url = "https://cdn.example.com/car.jpg"
    body = _jpeg_bytes((128, 128, 128), (64, 64))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    def fake_plate(image: Image.Image, image_url: HttpUrl):
        return [
            license_plate_detected(
                image_url,
                0.9,
                [0.1, 0.2, 0.4, 0.35],
            )
        ]

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    class _Listing:
        image_urls = [HttpUrl(url)]

    analyzer = ImageAnalyzer(checks=(fake_plate,))
    try:
        async with CvService(http_client=client, analyzer=analyzer) as cv:
            defects = await cv.detect_defects(_Listing())  # type: ignore[arg-type]
    finally:
        await client.aclose()

    assert len(defects) == 1
    assert defects[0].label == "license_plate_detected"
    assert defects[0].bbox == [0.1, 0.2, 0.4, 0.35]


@pytest.mark.asyncio
async def test_context_manager_closes_owned_client() -> None:
    async with CvService() as cv:
        assert cv._owns_http is True
        assert not cv._http.is_closed
    assert cv._http.is_closed


@pytest.mark.asyncio
async def test_injected_client_is_not_closed() -> None:
    client = httpx.AsyncClient()
    try:
        async with CvService(http_client=client) as cv:
            assert cv._owns_http is False
        assert not client.is_closed
    finally:
        await client.aclose()
