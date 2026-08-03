# AGENTS.md — AutoPulse

Instructions for AI agents working in this repository.

## Mission

Build a production-shaped auction aggregator: enrich raw car listings
(LLM + CV), then price them (margin / turnover). Prefer working vertical
slices over incomplete sprawl.

## Non-negotiables

1. **Ack-on-aggregation** — never `.ack()` enrichment until both LLM and CV
   finished and Mongo state is durable.
2. **Hybrid storage** — unstructured enrichment → MongoDB; business metrics →
   MySQL. Do not dump pricing history into Mongo as the source of truth.
3. **Do not block the event loop** — Pillow / OpenCV / sync SDK calls go through
   `asyncio.to_thread()` or a `ThreadPoolExecutor`.
4. **SOLID** — thin routers, orchestrators coordinate, repositories own I/O,
   domain rules stay free of FastAPI/RabbitMQ.
5. **Black formatting** — code line length **88**, docstrings/comments
   **≤ 72**. Run `black shared services` (not `ruff format`). English for
   code, commits, and agent docs. Comments only when intent is non-obvious.

## Where to work

| Area | Path |
|------|------|
| Contracts | `shared/autopulse_shared/schemas/` |
| Enrichment | `services/enrichment/app/` |
| Pricer | `services/pricer/app/` |
| Compose / CI | `compose.yaml`, `compose.prod.yaml`, `.github/workflows/` |
| Specs / plans | `docs/` |

## Implementation order

Follow `docs/roadmap.md`. Do not jump to week-3 CI polish before week-1
consumer + Mongo path works end-to-end.

## Patterns required by the vacancy brief

- Topic exchange + routing keys (`car.raw.created`, …)
- DLQ after N failures (`car.enrichment.dlq`)
- Circuit breaker + retries for LLM / Vision (`tenacity` or custom)
- Pydantic v2 everywhere on boundaries
- `X-Request-ID` middleware on both HTTP APIs
- Pytest + `pytest-asyncio`; integration via testcontainers later

## Agent workflow

1. Read `docs/architecture.md` and the relevant service README briefly.
2. Prefer extending stubs marked `TODO(week-N)` over inventing parallel modules.
3. Update shared schemas first when events/payloads change; keep services in sync.
4. Add/adjust unit tests next to the changed behavior.
5. Do not commit unless the user asks. Do not rewrite README for every tweak.

## Out of scope (for now)

- Full crawler product
- Auth / multi-tenant SaaS
- Frontend orchestrator UI (optional later)
- Real YOLO training pipeline (use a light pretrained model when CV lands)

## Definition of done (per slice)

- Type-checked happy path
- Failure path documented (retry / DLQ / circuit open)
- Test covering the pure rule or adapter contract
- No secrets in git (use `.env`)
