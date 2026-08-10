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

Ack rule: broker ack only when aggregation is durable, the outbox row is
enqueued, and the inbox claim is marked ``completed``. Inbox rows use
``processing`` → ``completed`` (released on failure so TTL retries can reclaim).

### Market Pricer Service

- **Ingress:** `car.enriched.success` (+ HTTP estimate / durable price)
- **Logic:** `PricingEngine` protocol — `MarginRuleEngine` (default) or
  `SklearnPricingEngine` via `PRICING_ENGINE=sklearn`
- **State:** MySQL `pricing_results` + inbox/outbox tables
- **Outputs:** `bid_price`, `recommended_dealer_bid`, `estimated_turnover_days`

Ack rule: broker ack only after durable pricing+outbox write and inbox
``completed``. Inbox uses ``processing`` → ``completed`` (released on
failure so TTL retries can reclaim).

### Messaging

- Exchange type: **topic** (`autopulse.cars`)
- Queues: durable, with dead-letter exchange for enrichment and pricer
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

Malformed / permanent failures skip TTL retry and go straight to DLQ.

## Directory map

```
services/enrichment/app/
  api/           HTTP routes (+ admin/dealer UI)
  admin/         ops dashboard service, templates, static
  dealer/        dealer submit + pipeline result UI
  bootstrap/     composition root + process lifecycle
  consumers/     aio_pika workers
  enrichment/    orchestrator + ports (protocols)
  llm/           heuristic + OpenAI option extraction
  cv/            image fetch + Pillow/OpenCV + plate ONNX
  messaging/     topology, publisher, outbox sink, retry
  repositories/  Mongo adapters (listings, inbox, outbox)
  core/          config, middleware, circuit breaker, metrics

services/pricer/app/
  api/           (+ /api/v1/admin overview)
  admin/         admin service DTOs
  bootstrap/     composition root + process lifecycle
  consumers/
  services/      pricing engine + ports + margin/sklearn
  messaging/     topology, outbox publisher, TTL retry
  repositories/  MySQL adapters
  models/        SQLAlchemy ORM

services/crawler/app/
  adapters/      Copart / IAAI / manual → RawListing
  api/           /api/v1/ingest/{source}
  messaging/     enrichment HTTP publisher
```

## Evolution notes

- Keep contracts in `shared/` versioned by fields, not by breaking renames.
- Prefer additive event fields; consumers must ignore unknowns.
- When adding a third service, reuse the same exchange and new routing keys.

## Crawler adapters

`services/crawler` normalizes vendor-shaped JSON (Copart / IAAI / manual)
into `RawListing` and POSTs enrichment `POST /api/v1/listings`. It is an
ingest edge, not a live auction scraper.
