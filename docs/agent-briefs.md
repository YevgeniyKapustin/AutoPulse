# Agent task briefs

Use these as prompts when starting a focused session.

## Brief A — Wire enrichment consumer

~~Implement `RawListingConsumer` with aio_pika…~~ **Done**.

## Brief B — Motor listing repository

~~Replace `ListingRepository` stub…~~ **Done**.

## Brief C — Pricer MySQL path

~~Wire SQLAlchemy async engine…~~ **Done**.

## Brief D — Integration smoke

~~Fixture enrich → price~~ **Done** via `tests/test_brief_d_smoke.py`.

Docker-backed checks:

```bash
make test-int
# or: poetry run pytest -m integration -q
```

Compose manual smoke:

```bash
docker compose up -d --build
curl -s -X POST http://localhost:8003/api/v1/ingest/copart \
  -H "Content-Type: application/json" \
  -d @services/crawler/fixtures/copart_lot.json
# or legacy RawListing shape:
curl -s -X POST http://localhost:8001/api/v1/listings \
  -H "Content-Type: application/json" \
  -d @docs/fixtures/raw_listing_sample.json
# wait for enrichment + pricing consumers, then:
curl -s http://localhost:8001/api/v1/listings/copart-12345678
curl -s http://localhost:8002/api/v1/pricing/copart-12345678
```

## Fixture

`docs/fixtures/raw_listing_sample.json` — sample inbound payload.
