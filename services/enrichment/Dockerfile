# syntax=docker/dockerfile:1.7

ARG PYTHON_IMAGE=python:3.12.8-slim-bookworm

FROM ${PYTHON_IMAGE} AS builder

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

COPY shared /build/shared
COPY services/enrichment /build/services/enrichment

RUN pip install --upgrade pip \
    && pip install /build/shared /build/services/enrichment


FROM ${PYTHON_IMAGE} AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 appuser \
    && useradd --system --uid 10001 --gid appuser --home /app --shell /usr/sbin/nologin appuser

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser shared /app/shared
COPY --chown=appuser:appuser services/enrichment /app/services/enrichment

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:8001/health" || exit 1

CMD ["uvicorn", "services.enrichment.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
