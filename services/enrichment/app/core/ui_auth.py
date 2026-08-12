"""HTTP Basic / API-key gate for dealer and admin UIs."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPBasic, HTTPBasicCredentials

from autopulse_shared.ui_auth import credentials_match, passwords_configured

_basic = HTTPBasic(auto_error=False)
_api_key = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_ui_auth(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)],
    api_key: Annotated[str | None, Depends(_api_key)],
) -> None:
    settings = request.app.state.settings
    expected_password = settings.ui_auth_password.get_secret_value()
    if not passwords_configured(settings.ui_auth_password):
        return
    username = credentials.username if credentials else None
    password = credentials.password if credentials else None
    if credentials_match(
        expected_username=settings.ui_auth_username,
        expected_password=expected_password,
        provided_username=username,
        provided_password=password,
        api_key=api_key,
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized",
        headers={"WWW-Authenticate": 'Basic realm="AutoPulse"'},
    )
