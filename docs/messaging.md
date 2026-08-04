# Messaging reliability checklist

| Item | Status |
|------|--------|
| `connect_robust` + reconnect coverage | Done |
| Heartbeat / connection name / timeouts | Done |
| Durable + quorum queues | Done (`RABBITMQ_QUORUM_QUEUES`) |
| Persistent messages | Done |
| Publisher confirms + `mandatory` | Done |
| Prefetch limits | Done |
| ACK after side effect | Done |
| Idempotent inbox (`event_id`, processing→completed) | Done (enrichment + pricer) |
| Transactional outbox | Done (Mongo enrichment w/ claim, MySQL pricer w/ SKIP LOCKED) |
| Retry backoff + DLQ | Done |
| Graceful shutdown < grace period | Done (`SHUTDOWN_TIMEOUT_SEC` / 25s) |
| Payload validation + `schema_version` | Done |
| Trace headers + scrape `/metrics` + JSON logs | Done (`:9091` / `:9092`) |
| Integration tests (topology + reconnect) | Done |

**Note:** switching an existing classic queue to quorum requires deleting the
old queue or wiping Compose volumes (`docker compose down -v`).
