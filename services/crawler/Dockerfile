# syntax=docker/dockerfile:1.7

ARG PYTHON_IMAGE=python:3.12.8-slim-bookworm
ARG POETRY_VERSION=2.1.1

FROM ${PYTHON_IMAGE} AS builder

ARG POETRY_VERSION
WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir "poetry==${POETRY_VERSION}"

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache \
    PIP_NO_CACHE_DIR=1

COPY shared/pyproject.toml shared/README.md /build/shared/
RUN mkdir -p /build/shared/autopulse_shared \
    && printf '%s\n' '"""Docker layer-cache stub; replaced below."""' \
        > /build/shared/autopulse_shared/__init__.py

COPY services/crawler/pyproject.toml services/crawler/poetry.lock \
    /build/services/crawler/

WORKDIR /build/services/crawler
RUN poetry install --only main --no-root --no-ansi \
    && rm -rf "${POETRY_CACHE_DIR}"

COPY shared /build/shared
RUN pip install --force-reinstall --no-deps /build/shared


FROM ${PYTHON_IMAGE} AS runtime

RUN groupadd --system --gid 10001 appuser \
    && useradd --system --uid 10001 --gid appuser --home /app \
        --shell /usr/sbin/nologin appuser

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app:/app/shared \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser shared /app/shared
COPY --chown=appuser:appuser services/crawler /app/services/crawler

USER appuser

EXPOSE 8003

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8003/health/live')"

CMD ["python", "-m", "uvicorn", "services.crawler.app.main:app", "--host", "0.0.0.0", "--port", "8003"]
