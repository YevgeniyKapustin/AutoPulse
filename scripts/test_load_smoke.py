"""Unit tests for load_smoke payload uniquification."""

from copy import deepcopy

from scripts.load_smoke import _unique_payload


def test_unique_copart_lot_number() -> None:
    base = {
        "lotNumber": "12345678",
        "title": "2019 BMW",
        "lotUrl": "https://example.com/lots/12345678",
    }
    a = _unique_payload("copart", base, 1)
    b = _unique_payload("copart", deepcopy(base), 2)
    assert a["lotNumber"] != b["lotNumber"]
    assert a["lotNumber"].startswith("12345678-")
    assert "1" in a["title"]


def test_unique_iaai_stock_number() -> None:
    base = {"stockNumber": "98765432", "title": "Camry"}
    payload = _unique_payload("iaai", base, 3)
    assert payload["stockNumber"].startswith("98765432-")
    assert payload["title"].endswith("#3")
