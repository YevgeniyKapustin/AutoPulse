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

Requires **Poetry 2.x** lockfiles (`metadata.lock-version` 2.*) and
Python 3.12.x (`>=3.12,<3.14`). Docker / CI use the same Poetry 2 line.

```bash
python scripts/poetry_install.py
# or: make install
```

`scripts/poetry_install.py` runs root `poetry install` (dev tools + path
`shared` only — no service libraries in root `pyproject.toml`), then a
**single** `pip install -e shared …pins` so pip resolves shared’s PyPI deps
against the merged service pins. It will:

- refuse Poetry 1.x / empty-main locks;
- skip packages whose environment markers do not match this host;
- abort if enrichment and pricer pin different versions of the same package
  (no silent overwrite).

Images stay isolated via per-service Docker builds (not this script).

## Commands

```bash
poetry run ruff format shared services
poetry run ruff check shared services
poetry run pytest
poetry -C services/pricer run alembic -c alembic.ini upgrade head
```

## Docker

Service Dockerfiles use **Poetry 2.1.x** and run
`poetry install --only main --no-root` from the service directory (path dep
on `../../shared`). Runtime stage copies the built venv and drops
Poetry/build tools. Keep service `poetry.lock` files on Poetry 2
(`lock-version` 2.*) so local `poetry_install.py` and images stay aligned.
