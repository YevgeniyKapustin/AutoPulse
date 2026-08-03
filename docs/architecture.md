# Architecture

## Context

AutoPulse aggregates auction/listing cars for dealers. Enrichment is async and
document-shaped; pricing is relational and queryable.

## Components

### Data Enrichment Service

- **Ingress:** HTTP `POST /api/v1/listings` and/or RabbitMQ `car.raw.created`
- **Workers:** LLM text extraction + CV image pipeline
- **State:** MongoDB document per `external_id` with flags `llm_done` / `cv_done`
- **Egress:** `car.enriched.success` or DLQ / failed event

Ack rule: broker ack only when `is_fully_enriched` is true and upsert succeeded.

### Market Pricer Service

- **Ingress:** `car.enriched.success` (+ HTTP estimate for debugging)
- **Logic:** `MarginRuleEngine` (rules first; sklearn optional later)
- **State:** MySQL `pricing_results`
- **Outputs:** `bid_price`, `recommended_dealer_bid`, `estimated_turnover_days`

### Messaging

- Exchange type: **topic** (`autopulse.cars`)
- Queues: durable, with dead-letter exchange for enrichment
- Headers: propagate `request_id` / `event_id` when present

## Data ownership

| Data | Store | Owner |
|------|-------|-------|
| Raw + enriched listing blob | MongoDB | Enrichment |
| Pricing metrics / history | MySQL | Pricer |
| Transient jobs | RabbitMQ | both |

## Resilience

```
LLM/CV call
  → retry (tenacity, bounded)
  → circuit breaker open → fail fast / retry later
  → message retry_count++
  → if retry_count >= N → DLQ
```

## Directory map

```
services/enrichment/app/
  api/           HTTP routes
  consumers/     aio_pika workers
  services/      LLM, CV, orchestrator
  repositories/  Mongo adapters
  core/          config, middleware, circuit breaker

services/pricer/app/
  api/
  consumers/
  services/      pricing + margin rules
  repositories/  MySQL adapters
  models/        SQLAlchemy ORM
```

## Evolution notes

- Keep contracts in `shared/` versioned by fields, not by breaking renames.
- Prefer additive event fields; consumers must ignore unknowns.
- When adding a third service, reuse the same exchange and new routing keys.
