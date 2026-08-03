# Agent task briefs

Use these as prompts when starting a focused session.

## Brief A — Wire enrichment consumer

Implement `RawListingConsumer` with aio_pika: declare topic exchange, durable
queue, DLQ, consume `car.raw.created`, call orchestrator, ack on aggregation.
Update `docs/roadmap.md` checkboxes when done.

## Brief B — Motor listing repository

Replace `ListingRepository` stub with Motor upsert/get by `external_id`.
Idempotent. Add a unit test with mongomock or testcontainers.

## Brief C — Pricer MySQL path

Wire SQLAlchemy async engine, create tables / Alembic, implement
`PricingRepository.save/get`, consume enriched events.

## Brief D — Integration smoke

`docker compose up`, publish one fixture from `docs/fixtures/`, assert Mongo
doc + MySQL row exist.

## Fixture

`docs/fixtures/raw_listing_sample.json` — sample inbound payload.
