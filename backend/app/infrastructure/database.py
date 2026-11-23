"""
Database connection, session management, and transaction boundaries.

Provides:
- Centralized SQLAlchemy 2.x engine configuration with connection pooling.
- Safe connection URL sanitization (prevents credential leaks in logs).
- Reusable session factory (`sessionmaker`).
- Request-scoped database session dependency for FastAPI (`get_db`).
- Standalone transaction context manager for tasks/services (`get_db_context`).
- Resilient database connectivity health checks.
- Re-export of declarative `Base` from `app.models.base`.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

import structlog
from sqlalchemy import Engine, create_engine, event, make_url, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.models.base import Base

logger = structlog.get_logger(__name__)

# Re-export declarative Base for backwards-compatibility
__all__ = [
    "Base",
    "SessionLocal",
    "build_engine",
    "build_session_factory",
    "check_database_connection",
    "engine",
    "get_db",
    "get_db_context",
    "get_sanitized_db_url",
]


def get_sanitized_db_url(url: str | None = None) -> str:
    """
    Return a safe representation of the database URL with the password masked.

    Prevents secret leakage in log statements, health endpoints, or error reports.
    """
    raw_url = url or get_settings().database_url
    try:
        parsed = make_url(raw_url)
        return parsed.render_as_string(hide_password=True)
    except Exception:
        return "postgresql://***:***@***"


def build_engine(settings: Settings | None = None) -> Engine:
    """
    Create and configure the primary SQLAlchemy 2.x Engine.

    Configures connection pooling, pre-ping validation, and timeouts
    from environment settings.
    """
    cfg = settings or get_settings()

    engine_kwargs: dict[str, object] = {
        "pool_pre_ping": True,                     # Test connection aliveness
        "pool_size": cfg.database_pool_size,       # Persistent pool size
        "max_overflow": cfg.database_max_overflow, # Max temporary overflow connections
        "pool_timeout": cfg.database_pool_timeout, # Wait timeout for pool checkout
        "pool_recycle": cfg.database_pool_recycle, # Periodically recycle connections
        "echo": cfg.database_echo or cfg.app_debug,
    }

    # SQLite (used in lightweight unit tests) does not support pool_size/max_overflow
    if cfg.database_url.startswith("sqlite"):
        engine_kwargs.pop("pool_size", None)
        engine_kwargs.pop("max_overflow", None)
        engine_kwargs.pop("pool_timeout", None)

    created_engine = create_engine(cfg.database_url, **engine_kwargs)

    @event.listens_for(created_engine, "connect")
    def on_connect(dbapi_connection: object, connection_record: object) -> None:
        logger.debug(
            "db_connection_acquired",
            database=get_sanitized_db_url(cfg.database_url),
        )

    return created_engine


def build_session_factory(eng: Engine) -> sessionmaker[Session]:
    """Create a configured sessionmaker bound to the given engine."""
    return sessionmaker(
        bind=eng,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


# ---------------------------------------------------------------------------
# Module-level singletons (lazily configured per process)
# ---------------------------------------------------------------------------
engine: Engine = build_engine()
SessionLocal: sessionmaker[Session] = build_session_factory(engine)


# ---------------------------------------------------------------------------
# Transaction & Session Lifecycle Management
# ---------------------------------------------------------------------------


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a request-scoped database session.

    Transaction boundaries:
    - Automatically rolls back if an uncaught exception is raised during request handling.
    - Always guarantees connection release back to the pool in the finally block.
    """
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_db_context(
    session_factory: sessionmaker[Session] | None = None,
) -> Generator[Session, None, None]:
    """
    Context manager providing an explicit transactional session boundary.

    Usage (in background tasks, CLI scripts, or services):
        with get_db_context() as session:
            session.add(record)
            # automatically committed on clean exit; rolled back on exception
    """
    factory = session_factory or SessionLocal
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database_connection(eng: Engine | None = None) -> bool:
    """
    Verify database connectivity via a lightweight ping query.

    Returns True if reachable, False otherwise.
    Never exposes raw connection credentials in error logs.
    """
    target_engine = eng or engine
    target_url = str(target_engine.url) if target_engine is not None else None
    sanitized_url = get_sanitized_db_url(target_url)
    try:
        with target_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning(
            "db_connection_check_failed",
            target=sanitized_url,
            error_type=type(exc).__name__,
        )
        return False
