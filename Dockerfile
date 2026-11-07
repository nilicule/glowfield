# Glowfield: works with Docker and Podman.
#
#   docker build -t glowfield .
#   docker run -d --name glowfield --restart unless-stopped \
#     -p 127.0.0.1:5010:5010 -e TZ=Europe/Amsterdam glowfield
#
# Defaults match an nginx `location /glowfield/ { proxy_pass http://localhost:5010/; }`.

# ---- build: resolve dependencies and install the app into a venv ----
FROM python:3.13-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Dependencies first, so code changes don't invalidate this layer.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# ---- runtime: just Python and the venv ----
FROM python:3.13-slim-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 --no-create-home glowfield

COPY --from=build /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=5010 \
    # URL prefix the app is served under, e.g. /glowfield (set to "" to serve at site root).
    ROOT_PATH=/glowfield \
    # Uvicorn worker processes.
    WEB_CONCURRENCY=2 \
    # Trust X-Forwarded-* from the reverse proxy (it's the only way in).
    FORWARDED_ALLOW_IPS="*" \
    # The daily puzzle changes at midnight in this timezone.
    TZ=UTC

USER glowfield
EXPOSE 5010

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/healthz', timeout=2)"

CMD ["glowfield"]
