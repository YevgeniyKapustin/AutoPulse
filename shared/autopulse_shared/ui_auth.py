"""Shared credential matching for lightweight UI / admin gates."""

from __future__ import annotations

import hashlib
import hmac

from pydantic import SecretStr


def passwords_configured(password: SecretStr | str) -> bool:
    if isinstance(password, SecretStr):
        return bool(password.get_secret_value())
    return bool(password)


def credentials_match(
    *,
    expected_username: str,
    expected_password: str,
    provided_username: str | None,
    provided_password: str | None,
    api_key: str | None,
) -> bool:
    """Return True when X-API-Key or Basic credentials match."""
    if not expected_password:
        return True
    if api_key is not None and digest_eq(api_key, expected_password):
        return True
    if provided_username is None or provided_password is None:
        return False
    return digest_eq(provided_username, expected_username) and digest_eq(
        provided_password,
        expected_password,
    )


def digest_eq(left: str, right: str) -> bool:
    left_digest = hashlib.sha256(left.encode("utf-8")).digest()
    right_digest = hashlib.sha256(right.encode("utf-8")).digest()
    return hmac.compare_digest(left_digest, right_digest)
