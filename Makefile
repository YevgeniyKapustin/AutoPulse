.PHONY: help up down logs build test lint format install

help:
	@echo "AutoPulse targets:"
	@echo "  make install  - install deps (editable monorepo)"
	@echo "  make up       - docker compose up (infra + services)"
	@echo "  make down     - stop and remove containers"
	@echo "  make build    - rebuild service images"
	@echo "  make logs     - follow compose logs"
	@echo "  make test     - run pytest for both services"
	@echo "  make lint     - ruff + mypy"
	@echo "  make format   - ruff format"

install:
	python -m pip install -e "./shared[dev]"
	python -m pip install -e "./services/enrichment[dev]"
	python -m pip install -e "./services/pricer[dev]"

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

test:
	pytest services/enrichment/tests services/pricer/tests -q

lint:
	ruff check shared services
	mypy shared services/enrichment/app services/pricer/app

format:
	ruff format shared services
