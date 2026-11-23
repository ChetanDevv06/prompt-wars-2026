# ============================================================
# LabLink Backend — Dockerfile
# Multi-stage build for production image
# ============================================================

# --- Builder stage ---
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tools
RUN pip install --no-cache-dir uv==0.13.0

# Copy dependency manifest
COPY pyproject.toml .
RUN touch README.md

# Install dependencies into /build/.venv
RUN uv venv .venv && \
    uv pip install --python .venv/bin/python --no-cache .

# --- Runtime stage ---
FROM python:3.12-slim AS runtime

WORKDIR /app

# Create non-root user
RUN addgroup --system lablink && adduser --system --ingroup lablink lablink

# Copy installed packages from builder
COPY --from=builder /build/.venv /app/.venv

# Copy application source
COPY app/ ./app/

# Set ownership
RUN chown -R lablink:lablink /app

USER lablink

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
