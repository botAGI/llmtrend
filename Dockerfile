# ============================================================================
# Multistage Dockerfile for AI Trend Monitor: API server + Celery worker/beat
# ============================================================================
# Targets:
#   api       - FastAPI application (uvicorn)
#   worker    - Celery worker process
#   scheduler - Celery beat scheduler
#
# Build examples:
#   docker build --target api -t ai-trend-monitor:api .
#   docker build --target worker -t ai-trend-monitor:worker .
#   docker build --target scheduler -t ai-trend-monitor:scheduler .
# ============================================================================

# ---------------------------------------------------------------------------
# Stage: base - shared runtime with Python deps
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies required at runtime and for healthchecks
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy and install Python requirements (cached layer)
COPY requirements/base.txt requirements/base.txt
COPY requirements/api.txt requirements/api.txt
RUN pip install --no-cache-dir -r requirements/api.txt

# Copy application source
COPY app/ app/
COPY scripts/ scripts/
COPY alembic/ alembic/
COPY alembic.ini alembic.ini

# Create reports directory and set ownership
RUN mkdir -p /app/reports \
    && chown -R appuser:appuser /app

USER appuser

# ---------------------------------------------------------------------------
# Target: api - FastAPI served by uvicorn
# ---------------------------------------------------------------------------
FROM base AS api

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# ---------------------------------------------------------------------------
# Target: worker - Celery worker
# ---------------------------------------------------------------------------
FROM base AS worker

CMD ["celery", "-A", "app.tasks", "worker", "--loglevel=info", "--concurrency=2"]

# ---------------------------------------------------------------------------
# Target: scheduler - Celery beat
# ---------------------------------------------------------------------------
FROM base AS scheduler

CMD ["celery", "-A", "app.tasks", "beat", "--loglevel=info"]
