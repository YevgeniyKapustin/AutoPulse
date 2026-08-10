# Data Enrichment Service

FastAPI worker that consumes raw listings, runs LLM + CV enrichment, stores
per-car state in MongoDB, and publishes `car.enriched.success`.

## Run

```bash
uvicorn services.enrichment.app.main:app --reload --port 8001
```

## Key modules

| Module | Role |
|--------|------|
| `app/consumers/raw_listing_consumer.py` | aio_pika + DLQ retries |
| `app/messaging/` | Topology (work + TTL retry + DLQ) + publisher |
| `app/enrichment/` | Aggregation orchestrator |
| `app/llm/` | Heuristic + OpenAI option extraction |
| `app/cv/` | Image fetch + brightness + plate/scene-text ONNX |
| `app/repositories/listing_repository.py` | Motor upsert/get |
| `app/core/circuit_breaker.py` | External API breaker |

## Reliability notes

- Inbox: `processing` → `completed` (released on failure for TTL retries)
- Outbox drain on enqueue + periodic ticker (`OUTBOX_DRAIN_INTERVAL_SEC`)
- Partial LLM/CV progress is persisted per stage for resume

## Ops dashboard

Local-only admin UI (no auth):

- UI: `http://127.0.0.1:8001/admin`
- JSON: `/api/v1/admin/overview`, `/api/v1/admin/listings`, …
- Re-enrich: `POST /api/v1/admin/listings/{external_id}/re-enrich`

Disable with `ADMIN_UI_ENABLED=false`. Queue depths come from RabbitMQ
Management (`RABBITMQ_MANAGEMENT_URL`). Do not expose `/admin` publicly.

## Dealer pipeline

Dealer-facing UI (no auth, local DX):

- Submit: `http://127.0.0.1:8001/` or `/dealer`
- Sample lots: crawler fixtures via `POST /dealer/samples/{copart|iaai}`
- Result poll: `/dealer/listings/{external_id}`

Needs crawler up (`CRAWLER_BASE_URL`, Compose: `http://crawler:8003`).
Disable with `DEALER_UI_ENABLED=false`.

## CV models

Plate + watermark detection use pretrained YOLO ONNX models under
`services/enrichment/models/`:

- plate: `joker5914/yolov8n-license-plate` → `license_plate_detected`
- watermark: `RyanBours/yolo11n-text` (scene text) + overlay scoring →
  `watermark_suspected`

Docker builds download both. With `compose.override` bind-mounts, run on
the host once:

```bash
python services/enrichment/scripts/download_cv_models.py
```

Disable with `CV_PLATE_ENABLED=false` / `CV_WATERMARK_ENABLED=false`.
Missing weights skip that check (log warning). Blur/OCR is out of scope.
