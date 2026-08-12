"""Fail closed on weak credential defaults outside local DX."""

from __future__ import annotations

# Obvious placeholders / compose local defaults — not for shared hosts.
WEAK_SECRET_VALUES = frozenset(
    {
        "autopulse",
        "admin",
        "change-me",
        "password",
        "secret",
        "root",
        "toor",
        "123456",
    }
)


def is_local_environment(environment: str) -> bool:
    return environment.strip().lower() in {"local", "dev", "development", "test"}


def require_strong_secret(
    name: str,
    value: str,
    *,
    allow_empty: bool = False,
) -> None:
    """Raise ValueError when value is missing or a known
    weak default.
    """
    if allow_empty and value == "":
        return
    if value == "" or value.lower() in WEAK_SECRET_VALUES:
        raise ValueError(
            f"{name} must be set to a non-default secret "
            f"(not allowed outside local DX)"
        )
