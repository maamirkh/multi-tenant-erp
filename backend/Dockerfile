# =============================================================================
# DevSphere ERP — Backend Dockerfile
#
# Stages:
#   builder  — installs Poetry and project dependencies (no source code)
#   development — hot-reload dev server (default CMD)
#   production  — non-root appuser, no dev deps
# =============================================================================

# ---------------------------------------------------------------------------
# Stage: builder — dependency installation only
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

# Install Poetry
RUN pip install --upgrade pip && \
    pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

# Copy dependency manifests first for layer-cache efficiency
COPY pyproject.toml poetry.lock ./

# Install all dependencies (including dev) for the development stage
RUN poetry install --no-root

# ---------------------------------------------------------------------------
# Stage: development — hot-reload, source mounted as volume
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS development

# Install curl for Docker healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Copy the pre-built virtual environment from builder
COPY --from=builder /app/.venv ./.venv

# Copy source code (overridden by volume mount in docker-compose.yml)
COPY . .

EXPOSE 8000

# Hot-reload enabled for development
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------------------------------------------------------------------------
# Stage: production — non-root user, no dev dependencies, no --reload
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PATH="/app/.venv/bin:$PATH"

# Install curl for Docker healthcheck and create non-root user
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* && \
    groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Install Poetry (needed to install --no-dev)
RUN pip install --upgrade pip && \
    pip install "poetry==${POETRY_VERSION}"

# Copy dependency manifests
COPY pyproject.toml poetry.lock ./

# Install production dependencies only
RUN poetry install --no-root --without dev

# Copy application source
COPY . .

# Transfer ownership to non-root user
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

# No --reload in production
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
