# Market Pricer Service

Consumes `car.enriched.success`, applies margin/turnover rules, persists
results to MySQL, and publishes `car.priced.success` via an outbox.

## Run

```bash
uvicorn services.pricer.app.main:app --reload --port 8002
```

Local compose sets `AUTO_CREATE_TABLES=true`. Prefer Alembic for shared envs:

```bash
make migrate         # host Poetry (dev)
make migrate-docker  # same container image as the app
```

## Key modules

| Module | Role |
|--------|------|
| `app/api/pricing.py` | Dry-run estimate + durable price + get |
| `app/bootstrap/` | Composition root + process lifecycle |
| `app/consumers/enriched_listing_consumer.py` | aio_pika + TTL retry + DLQ |
| `app/messaging/` | Topology (work + TTL retry + DLQ), outbox, retry |
| `app/services/` | Engine protocol, rules/sklearn, pricing service |
| `app/repositories/pricing_repository.py` | MySQL pricing + inbox + outbox |
| `alembic/` | Schema migrations |

## Reliability notes

- Inbox: `processing` → `completed` (released on failure for TTL retries)
- Pricing + outbox insert share one MySQL commit
- Outbox drain on success + periodic ticker (`OUTBOX_DRAIN_INTERVAL_SEC`)
- `POST /api/v1/pricing/estimate` is dry-run; `POST /api/v1/pricing` persists

## Admin API

`GET /api/v1/admin/overview` and `GET /api/v1/admin/pricing` honor the same
`UI_AUTH_USERNAME` / `UI_AUTH_PASSWORD` gate as enrichment UIs (HTTP Basic
or `X-API-Key`). Empty password keeps local DX open. Public pricing routes
under `/api/v1/pricing` stay ungated.
