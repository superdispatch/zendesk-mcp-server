FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/uv-cache

WORKDIR /app

# Install deps first (cached unless pyproject.toml/uv.lock change)
COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev --no-install-project

# Then copy source and install the project itself
COPY src /app/src
COPY README.md /app/
RUN uv sync --frozen --no-dev

# Unprivileged user
RUN groupadd --system appuser \
    && useradd --system --gid appuser --shell /usr/sbin/nologin appuser
USER appuser

EXPOSE 8080
CMD ["uv", "run", "zendesk-http"]
