.PHONY: help up down logs build test lint format install config-prod up-prod migrate

POETRY ?= poetry

help:
	@echo "AutoPulse targets:"
	@echo "  make install     - Poetry monorepo install (shared root venv)"
	@echo "  make up          - local compose (compose.yaml + override)"
	@echo "  make down        - stop and remove containers"
	@echo "  make build       - rebuild local service images"
	@echo "  make logs        - follow compose logs"
	@echo "  make migrate     - alembic upgrade head (pricer MySQL)"
	@echo "  make config-prod - validate compose.yaml + compose.prod.yaml"
	@echo "  make up-prod     - prod overlay (requires TAG=...)"
	@echo "  make test        - pytest (shared + services)"
	@echo "  make lint        - ruff check + mypy"
	@echo "  make format      - ruff format (line length 88)"

install:
	python scripts/poetry_install.py

up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

migrate:
	$(POETRY) -C services/pricer run alembic -c alembic.ini upgrade head

config-prod:
	docker compose -f compose.yaml -f compose.prod.yaml config -q

up-prod:
	@test -n "$(TAG)" || (echo "TAG is required, e.g. make up-prod TAG=abc1234" && exit 1)
	docker compose -f compose.yaml -f compose.prod.yaml up -d

test:
	$(POETRY) run pytest shared/tests services/enrichment/tests services/pricer/tests -q

lint:
	$(POETRY) run ruff check shared services
	$(POETRY) run mypy

format:
	$(POETRY) run ruff format shared services
