FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
# true = also install torch/sentence-transformers (~3 GB) for EMBEDDING_PROVIDER=local.
# Default false keeps hosted builds (Render) slim; docker compose passes INSTALL_EMBEDDINGS explicitly.
ARG INSTALL_EMBEDDINGS=false
RUN if [ "$INSTALL_EMBEDDINGS" = "true" ]; then \
      uv sync --frozen --no-dev --no-install-project --extra embeddings; \
    else \
      uv sync --frozen --no-dev --no-install-project; \
    fi

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
