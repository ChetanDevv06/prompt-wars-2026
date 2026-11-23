# LabLink

**Intelligent Laboratory Resource Management Platform**

> Google Prompt Wars 2026

---

## Project Overview

LabLink is a campus-wide laboratory resource-sharing and intelligent allocation platform that connects students, faculty, departments, laboratories, and institutional equipment through a unified system.

The platform enables intelligent equipment discovery, project-aware booking, and AI-powered fair allocation across university departments.

---

## Repository Structure

```
.
├── backend/          # Python / FastAPI backend API (this milestone)
├── LABLINK_SRS_v1.0.md  # Software Requirements Specification
└── README.md
```

## Backend Quick Start

See [`backend/README.md`](backend/README.md) for full setup instructions.

```bash
cd backend
cp .env.example .env
docker compose up -d           # Start PostgreSQL
uv run uvicorn app.main:app --reload
```

Health check: `GET http://localhost:8000/api/v1/health`

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python 3.12, FastAPI |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.x |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Frontend | Next.js / TypeScript *(planned)* |
| Optimisation | OR-Tools CP-SAT *(planned)* |
| AI | Google Gemini *(planned)* |
