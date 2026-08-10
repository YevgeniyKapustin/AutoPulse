"""Server-rendered dealer pipeline UI (Jinja + HTMX)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from services.enrichment.app.dealer.crawler_client import CrawlerSampleError
from services.enrichment.app.dealer.normalize import (
    DealerSubmitError,
    listing_from_form,
    listing_from_json_text,
)
from services.enrichment.app.dealer.service import DealerService

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "dealer" / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter(tags=["dealer-ui"])


def _require_dealer(request: Request) -> DealerService:
    if not getattr(request.app.state.settings, "dealer_ui_enabled", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dealer UI is disabled",
        )
    dealer: DealerService | None = getattr(request.app.state, "dealer", None)
    if dealer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dealer UI is disabled",
        )
    return dealer


async def _submit_page(
    request: Request,
    *,
    error: str | None = None,
    form: dict[str, Any] | None = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    dealer = _require_dealer(request)
    samples = await dealer.sample_sources()
    return templates.TemplateResponse(
        request,
        "submit.html",
        {
            "error": error,
            "form": form or {},
            "samples": samples,
        },
        status_code=status_code,
    )


@router.get("/", response_class=HTMLResponse)
async def dealer_home(request: Request) -> HTMLResponse:
    return await _submit_page(request)


@router.get("/dealer", response_class=HTMLResponse)
async def dealer_submit_page(request: Request) -> HTMLResponse:
    return await dealer_home(request)


@router.post("/dealer/samples/{source}", response_model=None)
async def dealer_sample(
    source: str,
    request: Request,
) -> RedirectResponse | HTMLResponse:
    dealer = _require_dealer(request)
    request_id: str | None = getattr(request.state, "request_id", None)
    try:
        result = await dealer.submit_sample(source, request_id=request_id)
    except CrawlerSampleError as exc:
        return await _submit_page(
            request,
            error=str(exc),
            status_code=status.HTTP_502_BAD_GATEWAY,
        )
    return RedirectResponse(
        url=f"/dealer/listings/{result.external_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/dealer/submit", response_model=None)
async def dealer_submit(
    request: Request,
    source: str = Form("manual"),
    external_ref: str = Form(""),
    title: str = Form(""),
    description: str = Form(""),
    make: str = Form(""),
    model: str = Form(""),
    year: str = Form(""),
    mileage_km: str = Form(""),
    asking_price: str = Form(""),
    currency: str = Form("USD"),
    url: str = Form(""),
    image_urls: str = Form(""),
    json_payload: str = Form(""),
) -> RedirectResponse | HTMLResponse:
    dealer = _require_dealer(request)
    request_id: str | None = getattr(request.state, "request_id", None)
    form = {
        "source": source,
        "external_ref": external_ref,
        "title": title,
        "description": description,
        "make": make,
        "model": model,
        "year": year,
        "mileage_km": mileage_km,
        "asking_price": asking_price,
        "currency": currency,
        "url": url,
        "image_urls": image_urls,
        "json_payload": json_payload,
    }
    try:
        if json_payload.strip():
            listing = listing_from_json_text(json_payload, source_hint=source)
        else:
            listing = listing_from_form(
                source=source,
                external_ref=external_ref,
                title=title,
                description=description,
                make=make,
                model=model,
                year=year,
                mileage_km=mileage_km,
                asking_price=asking_price,
                currency=currency,
                url=url,
                image_urls_text=image_urls,
            )
        result = await dealer.submit(listing, request_id=request_id)
    except DealerSubmitError as exc:
        return await _submit_page(
            request,
            error=str(exc),
            form=form,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return RedirectResponse(
        url=f"/dealer/listings/{result.external_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/dealer/listings/{external_id}", response_class=HTMLResponse)
async def dealer_listing(
    external_id: str,
    request: Request,
) -> HTMLResponse:
    dealer = _require_dealer(request)
    view = await dealer.pipeline(external_id)
    return templates.TemplateResponse(
        request,
        "result.html",
        {
            "external_id": external_id,
            "view": view,
        },
    )


@router.get(
    "/dealer/listings/{external_id}/status",
    response_class=HTMLResponse,
)
async def dealer_listing_status(
    external_id: str,
    request: Request,
) -> HTMLResponse:
    dealer = _require_dealer(request)
    view = await dealer.pipeline(external_id)
    return templates.TemplateResponse(
        request,
        "partials/status.html",
        {
            "external_id": external_id,
            "view": view,
        },
    )
