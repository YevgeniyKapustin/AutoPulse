# Docker & Compose

## Files

| File | Role |
|------|------|
| `compose.yaml` | Base stack: pinned images, networks, healthchecks, discovery env |
| `compose.override.yaml` | Local only (auto-merged): `127.0.0.1` ports, bind mounts, `--reload` |
| `compose.prod.yaml` | Prod overlay: registry images by `TAG`, no DB/app host ports |
| `.dockerignore` | Keeps `.git` / `.env` / caches out of build context |
| `services/*/Dockerfile` | Multi-stage, non-root `appuser`, Python healthcheck |

## Env precedence (important)

Compose `environment:` **wins over** `env_file:`. The base `x-app-env`
anchor therefore only sets service discovery (`RABBITMQ_HOST`,
`MYSQL_HOST`, ports). Credentials and app knobs come from:

| Mode | Source |
|------|--------|
| Local | `compose.override.yaml` → `env_file: .env` |
| Prod | `compose.prod.yaml` → `ENRICHMENT_ENV_FILE` / `PRICER_ENV_FILE` |

Datastore containers (RabbitMQ / MySQL) still interpolate bootstrap users
from the **host** shell or project `.env` at compose-parse time
(`${RABBITMQ_USER:-autopulse}`, etc.).

## Local

```bash
cp .env.example .env
docker compose up -d --build
docker compose config   # validate merge
```

`--reload` restarts the process on code change; lifespan shutdown calls
`await consumer.stop()` which closes the aio_pika channel + connection.

## Production

Do **not** deploy with the override file (it publishes DB ports on
localhost for DBeaver/Compass). Always pass `TAG` explicitly:

```bash
export TAG=$(git rev-parse --short HEAD)
# place secrets on the host, e.g. /run/env/enrichment.env
export ENRICHMENT_ENV_FILE=/run/env/enrichment.env
export PRICER_ENV_FILE=/run/env/pricer.env
docker compose -f compose.yaml -f compose.prod.yaml pull
docker compose -f compose.yaml -f compose.prod.yaml up -d
# or: make up-prod TAG=$TAG
```

`${TAG:?…}` fails fast if `TAG` is missing. CI sets `TAG: ci-${{ github.sha }}`
for compose validation and image builds.

Checklist highlights:

- pinned third-party images (no `:latest`)
- multi-stage + `USER appuser` (no `curl` in runtime; health via Python)
- Poetry per-service install (no cross-service dep leakage in images)
- healthchecks + `depends_on: service_healthy`
- datastores without published ports in prod
- secrets via env files, not image layers / not YAML defaults
- enrichment memory limit `1G` (Pillow/CV headroom); pricer `512M`
- logs to stdout (json-file rotation in prod overlay)
