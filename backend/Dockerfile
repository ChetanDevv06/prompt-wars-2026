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
RUN uv venv /build/.venv && \
    uv pip install --python /build/.venv/bin/python --no-cache . && \
    sed -i 's|/build/\.venv|/app/.venv|g' /build/.venv/bin/*

# --- Runtime stage ---
FROM python:3.12-slim AS runtime

WORKDIR /app

# Create non-root user
RUN addgroup --system lablink && adduser --system --ingroup lablink lablink

# Copy installed packages from builder
COPY --from=builder /build/.venv /app/.venv

# Maintain backwards compatibility symlink for build path
RUN mkdir -p /build && ln -s /app/.venv /build/.venv

# Copy application source
COPY app/ ./app/

# Set ownership and executable permissions
RUN chmod +x /app/.venv/bin/* && chown -R lablink:lablink /app /build

USER lablink

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
