# Roadmap (2–3 weeks)

Track progress by checking boxes. Agents should pick the next unchecked
item in the current week unless the user redirects.

## Week 1 — Infra & Data Enrichment

- [x] Docker Compose: RabbitMQ, MongoDB, MySQL, service stubs
- [x] Enrichment FastAPI skeleton + request-id middleware
- [x] Shared Pydantic contracts
- [x] aio_pika consumer for `car.raw.created`
- [x] Topic exchange + queue + DLQ declarations
- [x] Motor upsert for listing state
- [x] LLM extract options (real provider or record/replay stub)
- [x] CV pipeline via `asyncio.to_thread` (Pillow ± YOLO)
- [x] Ack-on-aggregation + failure / DLQ path
- [x] Circuit breaker wired on LLM calls

## Week 2 — Market Pricer & databases

- [x] Pricer FastAPI skeleton + margin rule engine baseline
- [x] SQLAlchemy model for `pricing_results`
- [x] aio_pika consumer for `car.enriched.success`
- [x] Async MySQL repository (SQLAlchemy 2)
- [x] Alembic migrations (optional but preferred)
- [x] End-to-end: raw → enriched → priced
- [x] Optional: simple sklearn regressor behind same interface

## Week 3 — Reliability, tests, CI

- [x] GitHub Actions scaffold (lint + unit tests)
- [x] Unit tests for orchestrator / rules / breaker
- [x] Integration tests with testcontainers (RabbitMQ, Mongo, MySQL)
- [x] Harden Dockerfiles (non-root, healthchecks)
- [x] Polish README runbook + Mermaid diagram
- [x] Sample curl / event fixtures under `docs/fixtures/`

## Stretch (after MVP)

- [ ] Optional orchestrator UI / admin API
- [x] Metrics (Prometheus text on scrape ports `:9091` / `:9092`) and structured JSON logs
- [ ] Real watermark / plate heuristics
- [ ] Multi-source crawler adapters
- [x] RabbitMQ production hardening (see `docs/messaging.md`)
