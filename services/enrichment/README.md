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
| `app/messaging/` | Topology + event publisher |
| `app/enrichment/` | Aggregation orchestrator |
| `app/llm/` | Heuristic + OpenAI option extraction |
| `app/cv/` | Image fetch + Pillow heuristics |
| `app/repositories/listing_repository.py` | Motor upsert/get |
| `app/core/circuit_breaker.py` | External API breaker |

## Next TODOs

Week 1 pipeline is implemented. Optional hardening: integration tests with
testcontainers, real YOLO model swap-in for `CvService`.
