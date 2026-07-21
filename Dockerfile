# Command-center service image (task #27). Ships the FastAPI backend that
# reuses emctl's data layer; when the SPA (task #28) is built, its static bundle
# is dropped at command_center/static and FastAPI serves it alongside the API
# (one image, one deploy -- PRD command-center §3). Infra task #29 owns the
# Cloud Run wiring, ingress lock, and Secret Manager injection of GITHUB_TOKEN
# and the OIDC/session secrets; this Dockerfile is the runnable unit it deploys.
#
# Build context is the repo root:  docker build -t command-center .

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first so the layer caches until the manifest changes.
# The package + its `web` extra pull FastAPI, uvicorn, httpx, pydantic(-settings),
# and itsdangerous; emctl's own deps (psycopg, alembic, sqlalchemy) come with it.
COPY pyproject.toml ./
COPY emctl/__init__.py ./emctl/__init__.py
RUN pip install ".[web]"

# Application source: the CLI/data layer it reuses, the migrations, and the API.
COPY emctl ./emctl
COPY command_center ./command_center
COPY alembic.ini ./
# Reinstall so the console script + package metadata pick up the full source.
RUN pip install --no-deps ".[web]"

EXPOSE 8080
# Cloud Run provides $PORT; default to 8080 for local runs.
CMD ["sh", "-c", "uvicorn command_center.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
