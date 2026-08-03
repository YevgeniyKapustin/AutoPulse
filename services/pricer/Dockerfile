# syntax=docker/dockerfile:1.7

ARG PYTHON_IMAGE=python:3.12.8-slim-bookworm
ARG POETRY_VERSION=2.1.1

FROM ${PYTHON_IMAGE} AS builder

ARG POETRY_VERSION
WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir "poetry==${POETRY_VERSION}"

ENV POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_OPTIONS_NO_PIP=false

COPY shared /build/shared
COPY services/pricer/pyproject.toml services/pricer/poetry.lock \
    /build/services/pricer/

WORKDIR /build/services/pricer
RUN poetry install --only main --no-root --no-ansi


FROM ${PYTHON_IMAGE} AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 appuser \
    && useradd --system --uid 10001 --gid appuser --home /app \
        --shell /usr/sbin/nologin appuser

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY --from=builder /build/services/pricer/.venv /opt/venv
COPY --chown=appuser:appuser shared /app/shared
COPY --chown=appuser:appuser services/pricer /app/services/pricer

USER appuser

EXPOSE 8002

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:8002/health" || exit 1

CMD ["uvicorn", "services.pricer.app.main:app", "--host", "0.0.0.0", "--port", "8002"]
