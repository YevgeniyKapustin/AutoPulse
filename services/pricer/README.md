# Market Pricer Service

Consumes `car.enriched.success`, applies margin/turnover rules, persists
results to MySQL.

## Run

```bash
uvicorn services.pricer.app.main:app --reload --port 8002
```

Local compose sets `AUTO_CREATE_TABLES=true`. Prefer Alembic for shared envs:

```bash
make migrate
```

## Key modules

| Module | Role |
|--------|------|
| `app/api/pricing.py` | Estimate + get endpoints |
| `app/consumers/enriched_listing_consumer.py` | aio_pika consumer |
| `app/messaging/topology.py` | Topic exchange + DLQ |
| `app/services/margin_rules.py` | Deterministic rule engine |
| `app/services/pricing_service.py` | Price + persist |
| `app/repositories/pricing_repository.py` | Async MySQL upsert/get |
| `app/db/session.py` | SQLAlchemy async engine |
| `alembic/` | Schema migrations |

## Next TODOs

Optional sklearn regressor behind the same `PricingService` interface.
Docker smoke (Brief D) still open.
