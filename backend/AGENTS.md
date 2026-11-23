# LabLink — Engineering Instructions
# Project-Level Agent Configuration

## Project: LabLink Backend

**Stack:** Python 3.12+, FastAPI, PostgreSQL, SQLAlchemy 2.x, Alembic, Pydantic v2, uv

**Architecture:** Modular monolith. No microservices.

---

## Code Conventions

### Python

- Use Python 3.12+ type hints throughout. No `Any` without justification.
- All public functions and classes must have docstrings.
- Use `from __future__ import annotations` for forward references.
- Never use `typing.Optional[X]` — use `X | None`.
- Prefer `list[T]`, `dict[K, V]` over `List[T]`, `Dict[K, V]`.
- Use `Literal` for restricted string values.
- Use dataclasses or Pydantic models for structured data — no raw dicts crossing layer boundaries.

### FastAPI

- All endpoints must have `response_model`, `summary`, and `description`.
- Use `Depends()` for all shared logic (database sessions, settings).
- Never call `get_settings()` directly in endpoint functions — inject via `Depends`.
- API versioning: all routes under `/api/v1/`.
- Always return `SuccessResponse[T]` or raise a `LabLinkError` subclass.

### SQLAlchemy

- Use SQLAlchemy 2.x style (`Mapped`, `mapped_column`, type annotations).
- All models inherit from `app.models.base.Base`.
- Use `UUIDPrimaryKeyMixin` and `TimestampMixin` from `app.models.base`.
- Never use `Session.execute(raw_string)` — use parameterised queries or SQLAlchemy select().
- Database sessions: use `Depends(get_db)` in endpoints or `with get_db_context():` in services/tasks.
- Repository pattern: data access lives in `app/repositories/`, not in endpoints.

### Alembic

- Never modify the database schema manually.
- Every schema change requires an Alembic migration.
- Migration messages must be descriptive: `alembic revision --autogenerate -m "add_equipment_table"`.

---

## Layer Boundaries

```
API endpoint → Service → Repository → Database
                ↓
           Domain logic (app/domain/)
```

- Endpoints call services only.
- Services call repositories and domain logic only.
- Repositories call SQLAlchemy only.
- Domain logic is pure Python — no FastAPI, SQLAlchemy or HTTP concerns.
- Infrastructure (database, external clients) lives in `app/infrastructure/`.

---

## Testing Rules

- Tests live in `backend/tests/`.
- Unit tests: `tests/unit/` — pure logic, no database, no HTTP.
- Integration tests: `tests/integration/` — TestClient, mocked or real database.
- Always mock database in unit tests.
- Test file naming: `test_<module>.py`.
- Use `pytest` fixtures for shared state.
- Coverage target: 80% minimum.

Run tests:
```bash
uv run pytest
```

---

## Linting and Type Checking

```bash
uv run ruff check .
uv run ruff format .
uv run pyright
```

All linting and type checks must pass before committing.

---

## Security Rules

- Never commit `.env` files.
- Never hardcode secrets, passwords or API keys.
- Never log sensitive data (passwords, tokens, full database URLs).
- Use `get_settings()` for all configuration access.
- Never expose internal paths or stack traces in API responses.

---

## Git Rules

- Single branch: `main`.
- Commit messages: imperative mood, present tense. E.g. `Add health endpoint`.
- Never rewrite published Git history.
- Do not push without user approval.

---

## What Is Implemented (M01-M03)

- Backend foundation, structured logging, middleware, centralized error handling.
- PostgreSQL persistence layer, connection pooling, and Alembic migrations.
- Domain models: Department, Laboratory, Equipment, EquipmentCompatibility, MaintenanceWindow, Project, ProjectResourceRequirement, RequirementDependency, Reservation, ReservationHistory.
- Deterministic resource matching service (`ResourceMatchingService`).
- Reservation lifecycle state machine with conflict prevention and audit logging.
- REST API endpoints under `/api/v1` for Organisation, Equipment, Projects, Reservations, and Matching.

---

## What Is Not Implemented Yet (Future Milestones)

- M04: LIAE Global Optimization Engine (OR-Tools CP-SAT) and need-aware fairness algorithms.
- M05: GenAI & Gemini API integration for natural language discovery and explanations.
- Frontend: Next.js/React interface.
- Authentication & Authorization: Strictly restricted until competition instructions explicitly require it.
