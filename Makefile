.PHONY: help up down logs build test lint format install config-prod up-prod migrate

help:
	@echo "AutoPulse targets:"
	@echo "  make install     - install deps (editable monorepo)"
	@echo "  make up          - local compose (compose.yaml + override)"
	@echo "  make down        - stop and remove containers"
	@echo "  make build       - rebuild local service images"
	@echo "  make logs        - follow compose logs"
	@echo "  make migrate     - alembic upgrade head (pricer MySQL)"
	@echo "  make config-prod - validate compose.yaml + compose.prod.yaml"
	@echo "  make up-prod     - prod overlay (requires TAG=...)"
	@echo "  make test        - run pytest for both services"
	@echo "  make lint        - ruff + mypy"
	@echo "  make format      - ruff format"

install:
	python -m pip install -e "./shared[dev]"
	python -m pip install -e "./services/enrichment[dev]"
	python -m pip install -e "./services/pricer[dev]"

up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

migrate:
	alembic -c services/pricer/alembic.ini upgrade head

config-prod:
	docker compose -f compose.yaml -f compose.prod.yaml config -q

up-prod:
	@test -n "$(TAG)" || (echo "TAG is required, e.g. make up-prod TAG=abc1234" && exit 1)
	docker compose -f compose.yaml -f compose.prod.yaml up -d

test:
	pytest services/enrichment/tests services/pricer/tests -q

lint:
	ruff check shared services
	mypy shared services/enrichment/app services/pricer/app

format:
	ruff format shared services
