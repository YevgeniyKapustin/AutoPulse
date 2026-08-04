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
| `app/cv/` | Image fetch + Pillow heuristics |
| `app/repositories/listing_repository.py` | Motor upsert/get |
| `app/core/circuit_breaker.py` | External API breaker |

## Reliability notes

- Inbox: `processing` → `completed` (released on failure for TTL retries)
- Outbox drain on enqueue + periodic ticker (`OUTBOX_DRAIN_INTERVAL_SEC`)
- Partial LLM/CV progress is persisted per stage for resume
