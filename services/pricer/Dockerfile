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

# Fixed venv path so console-script shebangs survive COPY to runtime.
ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

# Stub shared so Poetry can resolve the path dep without invalidating the
# heavy install layer on every shared source change.
COPY shared/pyproject.toml shared/README.md /build/shared/
RUN mkdir -p /build/shared/autopulse_shared \
    && printf '%s\n' '"""Docker layer-cache stub; replaced below."""' \
        > /build/shared/autopulse_shared/__init__.py

COPY services/pricer/pyproject.toml services/pricer/poetry.lock \
    /build/services/pricer/

WORKDIR /build/services/pricer
RUN poetry install --only main --no-root --no-ansi

# Real shared package into site-packages (only this layer rebuilds on shared edits).
COPY shared /build/shared
RUN pip install --no-cache-dir --force-reinstall --no-deps /build/shared


FROM ${PYTHON_IMAGE} AS runtime

RUN groupadd --system --gid 10001 appuser \
    && useradd --system --uid 10001 --gid appuser --home /app \
        --shell /usr/sbin/nologin appuser

# PYTHONPATH=/app for `services.*`. Shared lives in /opt/venv site-packages.
# /app/shared is still present so compose.override bind-mounts can hot-reload
# shared when PYTHONPATH prefers it (local DX only).
ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app:/app/shared \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser shared /app/shared
COPY --chown=appuser:appuser services/pricer /app/services/pricer

USER appuser

EXPOSE 8002

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/health')"

CMD ["python", "-m", "uvicorn", "services.pricer.app.main:app", "--host", "0.0.0.0", "--port", "8002"]
