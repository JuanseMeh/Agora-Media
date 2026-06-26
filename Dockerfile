FROM --platform=$TARGETPLATFORM python:3.11-slim-bookworm AS builder

RUN pip install uv --no-cache-dir
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1

# Cache layer: dependencies only rebuild when pyproject.toml or lock changes
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

# Source layer — changes bust only this layer, deps stay cached
COPY main.py .
COPY api ./api
COPY config ./config
COPY db ./db
COPY schemas ./schemas
COPY services ./services

FROM --platform=$TARGETPLATFORM python:3.11-slim-bookworm AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=builder /app/.venv .venv
COPY --from=builder /app/main.py .
COPY --from=builder /app/api ./api
COPY --from=builder /app/config ./config
COPY --from=builder /app/db ./db
COPY --from=builder /app/schemas ./schemas
COPY --from=builder /app/services ./services

EXPOSE 8003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
