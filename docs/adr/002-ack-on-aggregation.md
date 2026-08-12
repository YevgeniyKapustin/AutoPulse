# ADR 002: Ack-on-aggregation for enrichment

## Status

Accepted

## Context

Enrichment has two independent stages (LLM text, CV images). Partial progress
must not lose work, but the broker must not drop a message until the
downstream event is safe to publish.

## Decision

1. Upsert Mongo state as each stage completes (`llm_done`, `cv_done`).
2. Ack RabbitMQ message only when both flags are true and
   `car.enriched.success` publish succeeded (or intentional fail event path).
3. On crash mid-way, redelivery resumes from persisted state (idempotent upsert).

## Consequences

- Consumer must be idempotent on `external_id` / `event_id`.
- At-least-once delivery → pricer must upsert pricing by `external_id`.
- Longer ack time → tune prefetch; avoid unbounded concurrency.
