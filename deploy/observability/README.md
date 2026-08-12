# Observability profile

Compose profile `observability` runs ClickHouse + Vector + Grafana for
structured log search. Grafana provisioning today only wires the
ClickHouse datasource — there are **no** provisioned alert rules yet.

Queue / DLQ depth alerting for local ops lives on the enrichment
dashboard (`/admin`) via RabbitMQ Management depths:

- `ADMIN_DLQ_WARN_DEPTH` (default `0`) — DLQ card is bad above this
- `ADMIN_QUEUE_WARN_DEPTH` (default `100`) — work/retry warn above half,
  bad above the threshold

Prometheus queue-depth gauges + Grafana alerts can layer on later once a
scraper ships; until then treat `/admin` cards as the on-call signal.
