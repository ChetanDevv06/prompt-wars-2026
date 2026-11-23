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
| PostgreSQL | 16+ (Docker or local instance) |
| Docker + Docker Compose | Recommended for local development |

---

## Environment Setup

```bash
# Clone the repository and enter the backend directory
cd backend

# Copy the example environment file
cp .env.example .env

# Edit .env with your local values
```

The `.env` file is **never committed**. Supported configuration options:

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `APP_ENV` | `development` | Runtime environment (`development`, `test`, `production`) |
| `APP_DEBUG` | `true` | Debug mode (enables Swagger UI at `/docs`) |
| `APP_HOST` | `0.0.0.0` | API bind address |
| `APP_PORT` | `8000` | API bind port |
| `APP_LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `DATABASE_URL` | `postgresql://lablink:lablink_dev_password@localhost:5432/lablink_db` | PostgreSQL connection string |
| `DATABASE_POOL_SIZE` | `5` | Persistent connection pool size |
| `DATABASE_MAX_OVERFLOW` | `10` | Temporary pool overflow limit |
| `DATABASE_POOL_TIMEOUT` | `30` | Seconds to wait before checkout timeout |
| `DATABASE_POOL_RECYCLE` | `1800` | Seconds before recycling connections (prevents stale sockets) |
| `DATABASE_ECHO` | `false` | Echo SQL queries to log (development only) |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | Comma-separated CORS whitelist |

---

## Dependency Installation

```bash
# Create virtual environment with Python 3.12
uv venv .venv --python 3.12

# Install dependencies (runtime + dev)
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"

# Windows PowerShell activation:
.venv\Scripts\Activate.ps1

# Linux / macOS activation:
source .venv/bin/activate
```

---

## PostgreSQL Operations

### 1. Local Development via Docker Compose

```powershell
# Start PostgreSQL container in background
docker compose up -d

# Verify container status and health check
docker compose ps

# View database logs
docker compose logs -f postgres

# Stop PostgreSQL container (data is preserved in postgres_data volume)
docker compose down

# Stop container and wipe data volume (clean reset)
docker compose down -v
```

### 2. Standalone / Native PostgreSQL (Windows PowerShell)

If running a native PostgreSQL service (e.g. PostgreSQL 16/18 on port 5432):

```powershell
# Create dedicated database user (if not using default superuser)
& "E:\PostgreSQL\bin\createuser.exe" -U postgres -P -d lablink

# Create development and test databases
& "E:\PostgreSQL\bin\createdb.exe" -U lablink -E UTF8 lablink_db
& "E:\PostgreSQL\bin\createdb.exe" -U lablink -E UTF8 lablink_test
```

### 3. Ephemeral Test Cluster (Automated or Manual)

An ephemeral PostgreSQL cluster can be initialized for isolated testing:

```powershell
$testDbDir = "$env:TEMP\lablink_pg_test"
& "E:\PostgreSQL\bin\initdb.exe" -D $testDbDir -U lablink -A trust -E UTF8 --locale=C
& "E:\PostgreSQL\bin\pg_ctl.exe" -D $testDbDir -l "$env:TEMP\lablink_pg.log" -o "-p 5433" start

# Run migrations or tests against port 5433
$env:DATABASE_URL = "postgresql+psycopg://lablink@localhost:5433/lablink_test"

# Stop the ephemeral cluster
& "E:\PostgreSQL\bin\pg_ctl.exe" -D $testDbDir stop
```

---

## Database Migrations (Alembic)

Alembic migrations dynamically load database settings from `app.core.config.get_settings()` and model metadata from `app.models.base.Base.metadata`. No database passwords are hardcoded in `alembic.ini`.

```powershell
# Show current database revision
uv run alembic current

# Inspect migration history
uv run alembic history

# Generate a new migration after editing models in app/models/
uv run alembic revision --autogenerate -m "add_table_name"

# Apply all pending migrations to the database
uv run alembic upgrade head

# Rollback the last applied migration
uv run alembic downgrade -1

# Generate SQL script for offline inspection (dry-run without touching database)
uv run alembic upgrade head --sql

# Verify if models and database schema are in sync
uv run alembic check
```

---

## Running the Application

```powershell
# Run the API server with auto-reload
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API Base: `http://localhost:8000`
- Health Endpoint: `http://localhost:8000/api/v1/health`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`

---

## Testing & Verification

```powershell
# Run all tests with coverage report
uv run pytest --cov=app --cov-report=term-missing

# Run only unit tests (pure logic, no live database required)
uv run pytest tests/unit/

# Run integration tests (PostgreSQL connectivity, persistence, migrations)
uv run pytest tests/integration/ -v
```

---

## Code Quality & Static Analysis

```powershell
# Run Ruff lint check
uv run ruff check .

# Fix auto-fixable lint issues
uv run ruff check . --fix

# Verify code formatting
uv run ruff format . --check

# Run static type checking
uv run pyright
```

---

## Database Troubleshooting

| Symptom | Probable Cause | Resolution |
| :--- | :--- | :--- |
| `FATAL: password authentication failed for user "lablink"` | PostgreSQL running on port 5432 with different credentials | Check if Docker container or another service owns port 5432; ensure `DATABASE_URL` in `.env` matches your active PostgreSQL user password. |
| `FATAL: database "lablink_db" does not exist` | Database not yet created | Run `docker compose up -d` (automatically creates `lablink_db`), or execute `createdb -U lablink -E UTF8 lablink_db`. |
| `TypeError: cannot use a string pattern on a bytes-like object` | Database created with `SQL_ASCII` instead of `UTF8` | Ensure databases are created with `-E UTF8`. |
| Connection pool exhausted (`TimeoutError`) | High concurrency or unclosed sessions | Increase `DATABASE_POOL_SIZE` or verify all custom queries use `get_db_context()` or `get_db()` which close sessions in `finally`. |

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                 # Application factory and entry point
│   ├── api/
│   │   └── v1/
│   │       ├── router.py       # Aggregated v1 router
│   │       ├── schemas.py      # Standard response and error envelopes
│   │       └── endpoints/
│   │           └── health.py   # GET /api/v1/health
│   ├── core/
│   │   ├── config.py           # Pydantic Settings (connection pooling, env vars)
│   │   ├── exceptions.py       # Domain exception hierarchy and handlers
│   │   ├── logging.py          # Structured logging (structlog)
│   │   └── middleware.py       # Request context & X-Request-ID middleware
│   ├── infrastructure/
│   │   └── database.py         # SQLAlchemy engine, session factory, context managers
│   └── models/
│       ├── __init__.py         # Re-exports Base and mixins
│       └── base.py             # Declarative Base, naming conventions, UUID/Timestamp mixins
├── tests/
│   ├── conftest.py             # Pytest configuration and client fixtures
│   ├── unit/
│   │   ├── test_config.py      # Settings and environment validation tests
│   │   ├── test_database.py    # Naming conventions, mixins, session lifecycle tests
│   │   └── test_exceptions.py  # Domain error hierarchy tests
│   └── integration/
│       ├── test_health.py      # Health endpoint integration tests
│       └── test_database_persistence.py # Real PostgreSQL persistence & migration tests
├── alembic/
│   ├── env.py                  # Dynamic configuration and autogenerate metadata loader
│   ├── script.py.mako          # Migration template
│   └── versions/               # Tracked migration revisions
├── alembic.ini                 # Alembic project configuration
├── pyproject.toml              # Tool configurations and dependencies
├── .env.example                # Documented configuration template
├── Dockerfile                  # Production container definition
├── docker-compose.yml          # Local development PostgreSQL 16 container
├── .dockerignore
├── AGENTS.md                   # Agent conventions and layer boundaries
└── README.md
```
