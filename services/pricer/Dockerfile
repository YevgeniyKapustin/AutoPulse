FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY shared /app/shared
COPY services/pricer /app/services/pricer

RUN pip install --no-cache-dir -e /app/shared \
    && pip install --no-cache-dir -e /app/services/pricer

ENV PYTHONPATH=/app
EXPOSE 8002

CMD ["uvicorn", "services.pricer.app.main:app", "--host", "0.0.0.0", "--port", "8002"]
