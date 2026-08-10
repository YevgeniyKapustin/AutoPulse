"""JSON admin/ops API for pricer."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from services.pricer.app.admin.service import (
    PricerAdminOverview,
    PricerAdminService,
    PricingAdminPage,
)
from services.pricer.app.core.ui_auth import require_ui_auth

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_ui_auth)],
)

LimitQuery = Annotated[int, Query(ge=1, le=100)]
CursorQuery = Annotated[datetime | None, Query()]


def _require_admin(request: Request) -> PricerAdminService:
    admin: PricerAdminService | None = getattr(request.app.state, "admin", None)
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin API is disabled",
        )
    return admin


@router.get("/overview", response_model=PricerAdminOverview)
async def admin_overview(request: Request) -> PricerAdminOverview:
    return await _require_admin(request).overview()


@router.get("/pricing", response_model=PricingAdminPage)
async def admin_pricing(
    request: Request,
    limit: LimitQuery = 20,
    cursor: CursorQuery = None,
) -> PricingAdminPage:
    return await _require_admin(request).list_pricing(
        limit=limit,
        before_priced_at=cursor,
    )
