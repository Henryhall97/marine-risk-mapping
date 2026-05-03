# syntax=docker/dockerfile:1.7
# ─────────────────────────────────────────────────────────────
# Marine Risk Mapping — Backend (FastAPI + ML inference)
# Multi-stage build. Final image: python:3.12-slim + runtime deps
# only. Excludes Dagster, dbt, MLflow, geopandas, rasterio, etc.
# ─────────────────────────────────────────────────────────────

# ── Stage 1: builder ─────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# System packages required to build psycopg2 and audio libs from wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libsndfile1 \
        libpq-dev \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Use uv to resolve and install (much faster than pip).
RUN pip install uv

WORKDIR /app
COPY backend/requirements-runtime.txt /tmp/requirements-runtime.txt

# Install torch from CPU wheel index to keep image lean (~700MB vs 2GB CUDA).
# --index-strategy unsafe-best-match lets uv fall back to PyPI for packages
# whose latest version isn't on the PyTorch index (e.g. requests, numpy).
RUN uv pip install --system \
        --index-strategy unsafe-best-match \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        -r /tmp/requirements-runtime.txt

# ── Stage 2: runtime ─────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    PYTHONPATH=/app

# Runtime libs only (no -dev / no build tools).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libsndfile1 \
        libpq5 \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder.
COPY --from=builder /usr/local/lib/python3.12/site-packages \
                    /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /app

# Application code. Pipeline modules are needed because backend
# imports pipeline.config, pipeline.photo, pipeline.audio.
COPY backend/ ./backend/
COPY pipeline/ ./pipeline/
COPY transform/dbt_project.yml ./transform/dbt_project.yml

# ML model artifacts (photo_classifier ~68 MB, audio_classifier ~44 MB) are
# NOT baked into the image — they are large, gitignored, and rsync'd to the
# host then bind-mounted at /app/data/processed/ml via docker-compose.prod.yml.
# See scripts/upload_assets.sh and docs/DEPLOYMENT.md.

# Run as non-root.
RUN groupadd -r app && useradd -r -g app -d /app app && \
    mkdir -p /app/data/uploads && \
    chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:${PORT}/health || exit 1

# uvicorn workers tuned for 1 vCPU. Bump --workers on larger VMs.
CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT} --workers 2"]
