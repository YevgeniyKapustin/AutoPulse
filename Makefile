.DEFAULT_GOAL := help

.PHONY: help up up-observability down logs build test test-int lint format install config-prod up-prod migrate migrate-docker

POETRY ?= poetry

help:
	@echo "AutoPulse targets:"
	@echo "  make install           - Poetry monorepo install (shared root venv)"
	@echo "  make up                - local compose (compose.yaml + override)"
	@echo "  make up-observability  - local stack + ClickHouse/Vector/Grafana"
	@echo "  make down              - stop and remove containers"
	@echo "  make build             - rebuild local service images"
	@echo "  make logs              - follow compose logs"
	@echo "  make migrate           - alembic via host Poetry (dev)"
	@echo "  make migrate-docker    - alembic one-off in pricer container"
	@echo "  make config-prod       - validate compose.yaml + compose.prod.yaml"
	@echo "  make up-prod           - prod overlay (TAG + secrets required)"
	@echo "  make test              - unit tests (skip integration)"
	@echo "  make test-int          - integration tests (Docker required)"
	@echo "  make lint              - ruff check + mypy"
	@echo "  make format            - ruff format (line length 88)"

install:
	python scripts/poetry_install.py

up:
	docker compose up -d --build

up-observability:
	docker compose --profile observability up -d --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

migrate:
	$(POETRY) -C services/pricer run alembic -c alembic.ini upgrade head

migrate-docker:
	docker compose run --rm --entrypoint "" pricer \
		alembic -c /app/services/pricer/alembic.ini upgrade head

config-prod:
	TAG=local \
	ENRICHMENT_ENV_FILE=.env.prod.example \
	PRICER_ENV_FILE=.env.prod.example \
	RABBITMQ_USER=ci RABBITMQ_PASSWORD=ci \
	MYSQL_ROOT_PASSWORD=ci MYSQL_USER=ci MYSQL_PASSWORD=ci \
	MYSQL_DATABASE=autopulse_pricing \
	CLICKHOUSE_USER=ci CLICKHOUSE_PASSWORD=ci \
	GRAFANA_ADMIN_USER=ci GRAFANA_ADMIN_PASSWORD=ci \
	docker compose -f compose.yaml -f compose.prod.yaml config -q

up-prod:
	@test -n "$(TAG)" || (echo "TAG is required, e.g. make up-prod TAG=abc1234" && exit 1)
	@test -n "$(ENRICHMENT_ENV_FILE)" || (echo "ENRICHMENT_ENV_FILE is required" && exit 1)
	@test -n "$(PRICER_ENV_FILE)" || (echo "PRICER_ENV_FILE is required" && exit 1)
	@test -n "$(RABBITMQ_USER)" || (echo "RABBITMQ_USER is required" && exit 1)
	@test -n "$(RABBITMQ_PASSWORD)" || (echo "RABBITMQ_PASSWORD is required" && exit 1)
	@test -n "$(MYSQL_ROOT_PASSWORD)" || (echo "MYSQL_ROOT_PASSWORD is required" && exit 1)
	@test -n "$(MYSQL_USER)" || (echo "MYSQL_USER is required" && exit 1)
	@test -n "$(MYSQL_PASSWORD)" || (echo "MYSQL_PASSWORD is required" && exit 1)
	@test -n "$(MYSQL_DATABASE)" || (echo "MYSQL_DATABASE is required" && exit 1)
	@test -n "$(CLICKHOUSE_USER)" || (echo "CLICKHOUSE_USER is required" && exit 1)
	@test -n "$(CLICKHOUSE_PASSWORD)" || (echo "CLICKHOUSE_PASSWORD is required" && exit 1)
	@test -n "$(GRAFANA_ADMIN_USER)" || (echo "GRAFANA_ADMIN_USER is required" && exit 1)
	@test -n "$(GRAFANA_ADMIN_PASSWORD)" || (echo "GRAFANA_ADMIN_PASSWORD is required" && exit 1)
	docker compose -f compose.yaml -f compose.prod.yaml up -d

test:
	$(POETRY) run pytest -m "not integration" -q

test-int:
	$(POETRY) run pytest -m integration -q

lint:
	$(POETRY) run ruff check shared services
	$(POETRY) run mypy

format:
	$(POETRY) run ruff format shared services
