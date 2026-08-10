"""Built-in vendor fixtures for local/demo ingest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.crawler.app.core.exceptions import UnknownSourceError

_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"

# source → fixture filename under services/crawler/fixtures/
SAMPLE_FILES: dict[str, str] = {
    "copart": "copart_lot.json",
    "iaai": "iaai_stock.json",
}


def list_sample_sources() -> list[str]:
    return sorted(SAMPLE_FILES)


def load_sample_payload(source: str) -> dict[str, Any]:
    key = source.strip().lower()
    filename = SAMPLE_FILES.get(key)
    if filename is None:
        raise UnknownSourceError(f"No sample fixture for source={source!r}")
    path = _FIXTURES_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"Missing sample fixture: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Sample fixture must be a JSON object: {path}")
    return raw
