# Market Pricer Service

Consumes `car.enriched.success`, applies margin/turnover rules, persists
results to MySQL.

## Run

```bash
uvicorn services.pricer.app.main:app --reload --port 8002
```

## Key modules

| Module | Role |
|--------|------|
| `app/api/pricing.py` | Manual estimate endpoint |
| `app/consumers/enriched_listing_consumer.py` | aio_pika (stub) |
| `app/services/margin_rules.py` | Deterministic rule engine |
| `app/services/pricing_service.py` | Orchestrates price + persist |
| `app/models/pricing.py` | SQLAlchemy ORM |
| `app/repositories/pricing_repository.py` | MySQL adapter (stub) |

## Next TODOs

See week-2 items in `docs/roadmap.md`.
