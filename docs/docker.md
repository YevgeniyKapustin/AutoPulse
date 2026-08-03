# Docker & Compose

## Files

| File | Role |
|------|------|
| `compose.yaml` | Base stack: pinned images, networks, healthchecks, discovery env |
| `compose.override.yaml` | Local only (auto-merged): `127.0.0.1` ports, bind mounts, `--reload` |
| `compose.prod.yaml` | Prod overlay: GHCR images by `TAG`, API + worker, fail-closed secrets |
| `deploy/observability/` | ClickHouse init, Vector, Grafana provisioning |
| `.dockerignore` | Keeps `.git` / `.env` / caches out of build context |
| `services/*/Dockerfile` | Multi-stage, non-root `appuser`, Python healthcheck |

## Env precedence (important)

Compose `environment:` **wins over** `env_file:`. The base `x-app-env`
anchor therefore only sets service discovery (`RABBITMQ_HOST`,
`MYSQL_HOST`, ports). Credentials and app knobs come from:

| Mode | Source |
|------|--------|
| Local | `compose.override.yaml` → `env_file: .env` |
| Prod | `compose.prod.yaml` → required `ENRICHMENT_ENV_FILE` / `PRICER_ENV_FILE` |

Datastore bootstrap on the host:

| Mode | Behavior |
|------|----------|
| Local | `${RABBITMQ_USER:-autopulse}` (and friends) — weak defaults OK |
| Prod | `${RABBITMQ_USER:?…}` — missing/empty fails compose parse |

## Process model (`RUN_MODE`)

| Value | Process | Use |
|-------|---------|-----|
| `all` | HTTP + consumer in one process | Local DX (default) |
| `api` | HTTP (+ publisher for enrichment) | Prod API containers |
| `worker` | Consumer only (`python -m …worker`) | Prod worker containers |

## Local

```bash
cp .env.example .env
docker compose up -d --build
docker compose config   # validate merge
```

`--reload` restarts the process on code change; lifespan shutdown stops
consumers and closes aio_pika channels.

Logging stack (ClickHouse + Vector + Grafana) is opt-in:

```bash
make up-observability
# see docs/logging.md
```

## Production

Do **not** deploy with the override file (it publishes DB ports on
localhost for DBeaver/Compass). Always pass `TAG` and secrets explicitly:

```bash
export TAG=$(git rev-parse --short HEAD)
export ENRICHMENT_ENV_FILE=/run/env/enrichment.env
export PRICER_ENV_FILE=/run/env/pricer.env
export RABBITMQ_USER=… RABBITMQ_PASSWORD=…
export MYSQL_ROOT_PASSWORD=… MYSQL_USER=… MYSQL_PASSWORD=… MYSQL_DATABASE=…
docker compose -f compose.yaml -f compose.prod.yaml pull
docker compose -f compose.yaml -f compose.prod.yaml up -d
# or: make up-prod TAG=$TAG ENRICHMENT_ENV_FILE=… …
```

`${TAG:?…}` and datastore `${VAR:?…}` fail fast if unset/empty. CI sets
dummy secrets for `config -q` and pushes images as
`ghcr.io/yevgeniykapustin/autopulse-{enrichment,pricer}:ci-<sha>` on push
to `main`/`master`.

## Admin processes (Factor XII)

Prefer one-offs from the **same image** as the running release:

```bash
make migrate-docker
# or:
docker compose run --rm --entrypoint "" pricer \
  alembic -c /app/services/pricer/alembic.ini upgrade head
```

`make migrate` (host Poetry) is fine for local DX only.

## 12-Factor snapshot

| # | Factor | Status |
|---|--------|--------|
| I | Codebase | One repo, two deployables (`enrichment` / `pricer`) |
| II | Dependencies | Per-service Poetry lockfiles; images install from those |
| III | Config | Env / required `env_file`; prod fail-closed on secrets |
| IV | Backing services | Rabbit/Mongo/MySQL via env URLs/hosts |
| V | Build, release, run | Multi-stage build; CI pushes `TAG` digests to GHCR |
| VI | Processes | Stateless apps; API vs worker split in prod |
| VII | Port binding | Uvicorn binds `0.0.0.0:8001/8002` |
| VIII | Concurrency | Scale API and worker replicas independently |
| IX | Disposability | Fast health; graceful stop < `stop_grace_period` |
| X | Dev/prod parity | Same Dockerfiles; override only for local ports/reload |
| XI | Logs | JSON stdout → Vector → ClickHouse (profile `observability`) |
| XII | Admin processes | `make migrate-docker` against the pricer image |
