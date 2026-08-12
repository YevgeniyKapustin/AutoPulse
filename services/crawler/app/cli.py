"""CLI: normalize a source JSON file and POST to enrichment."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from services.crawler.app.adapters import AdapterRegistry
from services.crawler.app.core.config import get_settings
from services.crawler.app.core.exceptions import AdapterError, UnknownSourceError
from services.crawler.app.messaging.publisher import EnrichmentHttpPublisher
from services.crawler.app.service import IngestService


async def _run(source: str, path: Path, *, dry_run: bool) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        print("payload must be a JSON object", file=sys.stderr)
        return 2
    registry = AdapterRegistry()
    try:
        adapter = registry.get(source)
        listing = adapter.to_raw_listing(payload)
    except (UnknownSourceError, AdapterError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if dry_run:
        print(listing.model_dump_json(indent=2))
        return 0

    settings = get_settings()
    async with EnrichmentHttpPublisher(
        settings.enrichment_base_url,
        timeout_sec=settings.enrichment_timeout_sec,
    ) as publisher:
        result = await IngestService(
            registry=registry,
            publisher=publisher,
        ).ingest(source, payload)
    print(
        json.dumps(
            {
                "status": "accepted",
                "source": result.source,
                "external_id": result.external_id,
                "event_id": result.event_id,
            },
            indent=2,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="copart | iaai | manual")
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print RawListing JSON without calling enrichment",
    )
    args = parser.parse_args(argv)
    return asyncio.run(_run(args.source, args.file, dry_run=args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
