"""UI auth gate unit tests."""

from pydantic import SecretStr

from autopulse_shared.ui_auth import credentials_match, passwords_configured


def test_empty_password_disables_gate() -> None:
    assert not passwords_configured(SecretStr(""))
    assert credentials_match(
        expected_username="autopulse",
        expected_password="",
        provided_username=None,
        provided_password=None,
        api_key=None,
    )


def test_basic_credentials_ok() -> None:
    assert credentials_match(
        expected_username="autopulse",
        expected_password="secret",
        provided_username="autopulse",
        provided_password="secret",
        api_key=None,
    )


def test_basic_credentials_reject_bad_password() -> None:
    assert not credentials_match(
        expected_username="autopulse",
        expected_password="secret",
        provided_username="autopulse",
        provided_password="nope",
        api_key=None,
    )


def test_api_key_header_ok() -> None:
    assert credentials_match(
        expected_username="autopulse",
        expected_password="secret",
        provided_username=None,
        provided_password=None,
        api_key="secret",
    )


def test_api_key_rejects_mismatch() -> None:
    assert not credentials_match(
        expected_username="autopulse",
        expected_password="secret",
        provided_username=None,
        provided_password=None,
        api_key="other",
    )
