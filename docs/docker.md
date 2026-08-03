# Docker & Compose

## Files

| File | Role |
|------|------|
| `compose.yaml` | Base stack: pinned images, networks, healthchecks, no app images |
| `compose.override.yaml` | Local only (auto-merged): host ports, bind mounts, `--reload` |
| `compose.prod.yaml` | Prod overlay: registry images by `TAG`, no DB/app host ports |
| `.dockerignore` | Keeps `.git` / `.env` / caches out of build context |
| `services/*/Dockerfile` | Multi-stage, non-root `appuser`, runtime healthcheck |

## Local

```bash
cp .env.example .env
docker compose up -d --build
docker compose config   # validate merge
```

## Production

Do **not** deploy with the override file. Pull an already-built digest/tag:

```bash
export TAG=$(git rev-parse --short HEAD)
# place secrets on the host, e.g. /run/env/enrichment.env
export ENRICHMENT_ENV_FILE=/run/env/enrichment.env
export PRICER_ENV_FILE=/run/env/pricer.env
docker compose -f compose.yaml -f compose.prod.yaml pull
docker compose -f compose.yaml -f compose.prod.yaml up -d
```

Checklist highlights covered:

- pinned third-party images (no `:latest`)
- multi-stage + `USER appuser`
- Poetry per-service install (no cross-service dep leakage in images)
- healthchecks + `depends_on: service_healthy`
- datastores without published ports in prod
- secrets via env files, not image layers
- logs to stdout (json-file rotation in prod overlay)
