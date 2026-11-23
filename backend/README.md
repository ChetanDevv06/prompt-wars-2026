# LabLink Backend

**Intelligent Laboratory Resource Management Platform — Backend API**

Python · FastAPI · PostgreSQL · SQLAlchemy · Alembic · Pydantic

---

## Overview

LabLink is a campus-wide laboratory resource-sharing and intelligent allocation platform. This repository contains the backend REST API.

The backend exposes a versioned JSON API (`/api/v1/`) and is designed as a **modular monolith** with clear separation between domain logic, application services, API routes, and infrastructure.

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.12+ |
| uv | 0.13+ |
| PostgreSQL | 16+ (for local development) |
| Docker + Docker Compose | For the local database |

---

## Environment Setup

```bash
# Clone the repository and enter the backend directory
cd backend

# Copy the example environment file
cp .env.example .env

# Edit .env with your local values
# The only required change for local development is DATABASE_URL
```

The `.env` file is **never committed**. See `.env.example` for all supported variables.

---

## Dependency Installation

```bash
# Create a virtual environment and install all dependencies (including dev)
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"

# Windows: activate the venv
.venv\Scripts\activate

# macOS/Linux: activate the venv
source .venv/bin/activate
```

---

## Local Development

### 1. Start the database

```bash
# From the backend/ directory
docker compose up -d

# Verify PostgreSQL is healthy
docker compose ps
```

### 2. Run the API server

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now available at `http://localhost:8000`.

Interactive docs (development only): `http://localhost:8000/docs`

---

## Database Migrations

```bash
# Initialise Alembic (first time only)
alembic init alembic

# Generate a migration (after model changes)
alembic revision --autogenerate -m "describe_your_change"

# Apply migrations
alembic upgrade head

# Downgrade one step
alembic downgrade -1
```

---

## Running Tests

```bash
# Run all tests with coverage report
uv run pytest --cov=app --cov-report=term-missing

# Run only unit tests
uv run pytest tests/unit/

# Run only integration tests
uv run pytest tests/integration/
```

> **Note:** Unit tests do not require a running database — they mock all database calls.
> Integration tests that perform real queries require the Docker Compose database.

---

## Linting and Formatting

```bash
# Check linting
uv run ruff check .

# Fix auto-fixable issues
uv run ruff check . --fix

# Format code
uv run ruff format .

# Check formatting without modifying
uv run ruff format . --check
```

---

## Type Checking

```bash
uv run pyright
```

---

## API Health Endpoint

```
GET /api/v1/health
```

Returns:

```json
{
  "status": "ok",
  "timestamp": "2026-11-23T08:00:00Z",
  "version": "0.1.0",
  "environment": "development",
  "python_version": "3.12.15",
  "database": {
    "connected": true,
    "status": "ok"
  }
}
```

Status is `"ok"` when all subsystems are healthy, `"degraded"` otherwise.

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                 # Application entry point and factory
│   ├── api/
│   │   └── v1/
│   │       ├── router.py       # Aggregated v1 router
│   │       ├── schemas.py      # Shared response schemas
│   │       └── endpoints/
│   │           └── health.py   # GET /api/v1/health
│   ├── core/
│   │   ├── config.py           # Pydantic settings (env-driven)
│   │   ├── exceptions.py       # Domain exceptions + handlers
│   │   ├── logging.py          # Structured logging (structlog)
│   │   └── middleware.py       # Request context + logging middleware
│   └── infrastructure/
│       └── database.py         # SQLAlchemy engine + session factory
├── tests/
│   ├── conftest.py             # Shared pytest fixtures
│   ├── unit/
│   │   ├── test_config.py      # Settings validation tests
│   │   └── test_exceptions.py  # Domain exception tests
│   └── integration/
│       └── test_health.py      # Health endpoint integration tests
├── alembic/                    # Database migration environment
├── pyproject.toml              # Project metadata + tool config
├── .env.example                # Environment variable template
├── Dockerfile                  # Production container image
├── docker-compose.yml          # Local PostgreSQL service
├── .dockerignore
└── AGENTS.md                   # Engineering conventions for AI agents
```

---

## Architecture Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Architecture | Modular monolith | Appropriate for project scope; avoids premature complexity |
| Dependency management | uv | Fast, reproducible, modern Python packaging |
| Settings | Pydantic Settings | Type-safe, env-var driven, validated at startup |
| Logging | structlog | Structured JSON in production, readable in dev |
| Linting | Ruff | Fast, opinionated, replaces flake8 + isort |
| Type checking | Pyright | Strict, well-integrated with VSCode and FastAPI |
| Database | PostgreSQL | Required by platform design; relational with strong constraints |
| ORM | SQLAlchemy 2.x | Industry standard; supports typed mapped columns |
| Migrations | Alembic | Official SQLAlchemy migration tool |

---

## Planned (Future Milestones)

- Authentication and authorisation (JWT, role-based access)
- Equipment management domain
- Booking and scheduling workflows
- OR-Tools CP-SAT allocation engine
- Gemini AI integration
- Next.js frontend
