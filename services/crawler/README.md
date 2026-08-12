# Multi-source crawler adapters

Thin ingest edge in front of enrichment. Adapters normalize **vendor-shaped
JSON** (fixtures / feed dumps) into `RawListing`, then POST to enrichment
`POST /api/v1/listings` (Mongo upsert + `car.raw.created`).

This is **not** a live auction scraper (see AGENTS.md — full crawler product
is out of scope).

## Sources

| Source | Adapter | `external_id` |
|--------|---------|---------------|
| `copart` | `CopartAdapter` | `copart-{lotNumber}` |
| `iaai` | `IaaiAdapter` | `iaai-{stockNumber}` |
| `manual` | `ManualAdapter` | as provided (RawListing JSON) |

## Run (local)

```bash
# dry-run normalize
python -m services.crawler.app.cli --source copart \
  --file services/crawler/fixtures/copart_lot.json --dry-run

# ingest into enrichment (must be up)
export ENRICHMENT_BASE_URL=http://127.0.0.1:8001
python -m services.crawler.app.cli --source copart \
  --file services/crawler/fixtures/copart_lot.json

# HTTP API
uvicorn services.crawler.app.main:app --reload --port 8003
curl -s -X POST http://127.0.0.1:8003/api/v1/ingest/iaai \
  -H "Content-Type: application/json" \
  -d @services/crawler/fixtures/iaai_stock.json

# built-in fixtures (same files as above)
curl -s -X POST http://127.0.0.1:8003/api/v1/ingest/samples/copart
```

## Layout

| Path | Role |
|------|------|
| `app/adapters/` | SourceStrategy normalizers |
| `app/messaging/publisher.py` | Enrichment HTTP client |
| `app/service.py` | Ingest orchestration |
| `app/cli.py` | File ingest CLI |
| `fixtures/` | Sample vendor payloads |
