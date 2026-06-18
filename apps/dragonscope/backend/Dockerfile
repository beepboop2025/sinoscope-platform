FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# --- API server ---
FROM base AS api
EXPOSE 3456
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3456"]

# --- Celery worker ---
FROM base AS worker
CMD ["celery", "-A", "collector.celery_app", "worker", "--loglevel=info", "--concurrency=4"]

# --- Celery beat ---
FROM base AS beat
CMD ["celery", "-A", "collector.celery_app", "beat", "--loglevel=info"]
