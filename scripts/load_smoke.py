#!/usr/bin/env python3
"""Load smoke: push N unique fixture lots via crawler ingest.

Expects local stack up (crawler :8003, enrichment :8001, pricer :8002).
Does not require Poetry service packages — only stdlib.

Example:

  python scripts/load_smoke.py --count 20
  python scripts/load_smoke.py --count 5 --source iaai --wait-sec 45
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = {
    "copart": ROOT / "services" / "crawler" / "fixtures" / "copart_lot.json",
    "iaai": ROOT / "services" / "crawler" / "fixtures" / "iaai_stock.json",
}


def _http_json(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> tuple[int, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            payload: Any = json.loads(raw) if raw else None
            return response.status, payload
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {"detail": raw}
        except json.JSONDecodeError:
            payload = {"detail": raw}
        return exc.code, payload


def _unique_payload(source: str, base: dict[str, Any], index: int) -> dict[str, Any]:
    payload = deepcopy(base)
    suffix = f"{index:04d}-{uuid4().hex[:6]}"
    if source == "copart":
        lot = f"{payload.get('lotNumber', 'lot')}-{suffix}"
        payload["lotNumber"] = lot
        if "lotUrl" in payload:
            payload["lotUrl"] = f"https://example.com/lots/{lot}"
        if "title" in payload:
            payload["title"] = f"{payload['title']} #{index}"
    elif source == "iaai":
        stock = f"{payload.get('stockNumber', 'stock')}-{suffix}"
        payload["stockNumber"] = stock
        if "vehicleUrl" in payload:
            payload["vehicleUrl"] = f"https://example.com/iaai/{stock}"
        if "title" in payload:
            payload["title"] = f"{payload['title']} #{index}"
    else:
        raise ValueError(f"unsupported source: {source}")
    return payload


def _poll_enriched(
    enrichment_base: str,
    external_id: str,
    *,
    wait_sec: float,
    interval_sec: float,
) -> bool:
    deadline = time.monotonic() + wait_sec
    url = f"{enrichment_base.rstrip('/')}/api/v1/listings/{external_id}"
    while time.monotonic() < deadline:
        status, payload = _http_json("GET", url, timeout=5.0)
        if (
            status == 200
            and isinstance(payload, dict)
            and payload.get("llm_done")
            and payload.get("cv_done")
        ):
            return True
        time.sleep(interval_sec)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10, help="Listings to ingest")
    parser.add_argument(
        "--source",
        choices=sorted(FIXTURES),
        default="copart",
        help="Fixture adapter source",
    )
    parser.add_argument(
        "--crawler-base",
        default="http://127.0.0.1:8003",
        help="Crawler base URL",
    )
    parser.add_argument(
        "--enrichment-base",
        default="http://127.0.0.1:8001",
        help="Enrichment base URL (for optional wait)",
    )
    parser.add_argument(
        "--wait-sec",
        type=float,
        default=0.0,
        help="If >0, poll first listing until fully enriched",
    )
    parser.add_argument(
        "--interval-sec",
        type=float,
        default=1.0,
        help="Delay between ingest posts",
    )
    args = parser.parse_args(argv)
    if args.count < 1:
        print("--count must be >= 1", file=sys.stderr)
        return 2

    fixture_path = FIXTURES[args.source]
    base = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(base, dict):
        print("fixture must be a JSON object", file=sys.stderr)
        return 2

    ingest_url = f"{args.crawler_base.rstrip('/')}/api/v1/ingest/{args.source}"
    accepted: list[str] = []
    failures = 0
    started = time.perf_counter()
    for index in range(1, args.count + 1):
        payload = _unique_payload(args.source, base, index)
        status, body = _http_json("POST", ingest_url, body=payload)
        if status not in {200, 202} or not isinstance(body, dict):
            failures += 1
            print(f"[{index}] FAIL status={status} body={body}", file=sys.stderr)
            continue
        external_id = str(body.get("external_id", ""))
        accepted.append(external_id)
        print(f"[{index}] accepted {external_id} event={body.get('event_id')}")
        if index < args.count and args.interval_sec > 0:
            time.sleep(args.interval_sec)

    elapsed = time.perf_counter() - started
    print(
        json.dumps(
            {
                "ingested": len(accepted),
                "failed": failures,
                "elapsed_sec": round(elapsed, 3),
                "rate_per_sec": round(len(accepted) / elapsed, 3) if elapsed else None,
                "external_ids": accepted,
            },
            indent=2,
        )
    )

    if args.wait_sec > 0 and accepted:
        first = accepted[0]
        ok = _poll_enriched(
            args.enrichment_base,
            first,
            wait_sec=args.wait_sec,
            interval_sec=min(2.0, args.wait_sec),
        )
        print(
            json.dumps(
                {
                    "wait_external_id": first,
                    "fully_enriched": ok,
                    "wait_sec": args.wait_sec,
                },
                indent=2,
            )
        )
        if not ok:
            return 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
