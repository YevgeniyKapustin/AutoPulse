# Poetry layout

## Projects

| Path | Role | Runtime deps |
|------|------|----------------|
| `/pyproject.toml` | Workspace tooling only (`package-mode = false`) | `autopulse-shared` |
| `/shared` | Installable library `autopulse-shared` | pydantic |
| `/services/enrichment` | Enrichment service | motor, pillow, … |
| `/services/pricer` | Pricer service | sqlalchemy, aiomysql, pymysql, … |

Root must **not** list service-specific libraries (no `motor` / `pillow` /
`sqlalchemy` dump). Each Docker image installs from that service’s lockfile
only.

Dev tooling (`ruff`, `mypy`, `pytest`, `testcontainers`) lives **only** in
the root `[tool.poetry.group.dev.dependencies]`. Service `pyproject.toml`
files have no `dev` group — run lint/tests from the repo root.

Path to shared from a service is `../../shared` (service → `services/` →
repo root → `shared/`). That is correct for this layout.

## Local install

```bash
# Python 3.12.x (see python constraint >=3.12,<3.14)
python scripts/poetry_install.py
# or: make install
```

This installs root tools + shared into `.venv`, then `pip install`s each
service’s locked main deps into that same env (Poetry’s
`virtualenvs.create=false` would otherwise target the base interpreter).
Images stay isolated via per-service Docker builds.

## Commands

```bash
poetry run ruff format shared services
poetry run ruff check shared services
poetry run pytest
poetry -C services/pricer run alembic -c alembic.ini upgrade head
```

## Docker

Service Dockerfiles run `poetry install --only main --no-root` from the
service directory (path dep on `../../shared`). Runtime stage copies the
built `.venv` and drops Poetry/build tools.
