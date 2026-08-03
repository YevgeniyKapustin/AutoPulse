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
| `app/api/` | Health + listing ingress |
| `app/consumers/raw_listing_consumer.py` | aio_pika (stub) |
| `app/services/enrichment_orchestrator.py` | Aggregation coordinator |
| `app/services/llm_service.py` | Option extraction |
| `app/services/cv_service.py` | Image / defect detection |
| `app/repositories/listing_repository.py` | Mongo upsert/get |
| `app/core/circuit_breaker.py` | External API breaker |

## Next TODOs

See week-1 items in `docs/roadmap.md`.
