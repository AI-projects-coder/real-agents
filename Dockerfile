FROM python:3.12-slim

# Bring in the uv binary from its official image
COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Layer 1: dependencies only. Cached until pyproject.toml/uv.lock change -> fast rebuilds.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Layer 2: our code (changes often, cheap to rebuild)
COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Never run as root inside containers
RUN useradd --create-home appuser
USER appuser

# `exec` makes uvicorn PID 1, so it receives SIGTERM directly -> graceful shutdown
CMD ["sh", "-c", "exec uvicorn shoppilot.api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
