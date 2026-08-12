"""Secrets policy for non-local environments."""

import pytest
from pydantic import ValidationError
from services.enrichment.app.core.config import Settings as EnrichmentSettings
from services.pricer.app.core.config import Settings as PricerSettings

from autopulse_shared.secrets_policy import (
    is_local_environment,
    require_strong_secret,
)


def test_local_allows_default_broker_password() -> None:
    settings = EnrichmentSettings(
        environment="local",
        rabbitmq_password="autopulse",
    )
    assert settings.rabbitmq_password == "autopulse"


def test_production_rejects_default_broker_password() -> None:
    with pytest.raises(ValidationError, match="RABBITMQ_PASSWORD"):
        EnrichmentSettings(
            environment="production",
            rabbitmq_password="autopulse",
            admin_ui_enabled=False,
            dealer_ui_enabled=False,
        )


def test_production_requires_ui_password_when_ui_enabled() -> None:
    with pytest.raises(ValidationError, match="UI_AUTH_PASSWORD"):
        EnrichmentSettings(
            environment="production",
            rabbitmq_password="not-a-default-broker-secret",
            admin_ui_enabled=True,
            dealer_ui_enabled=False,
            ui_auth_password="",
        )


def test_pricer_production_rejects_default_mysql_password() -> None:
    with pytest.raises(ValidationError, match="MYSQL_PASSWORD"):
        PricerSettings(
            environment="production",
            rabbitmq_password="not-a-default-broker-secret",
            mysql_password="autopulse",
        )


def test_require_strong_secret_helper() -> None:
    assert is_local_environment("local")
    require_strong_secret("X", "unique-value-ok")
    with pytest.raises(ValueError):
        require_strong_secret("X", "change-me")
