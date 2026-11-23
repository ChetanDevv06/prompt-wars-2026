"""
Database session management.

Provides SQLAlchemy engine and session factory.
Database initialisation is deferred — no connection is
required at import time.
"""

from __future__ import annotations

from collections.abc import Generator

import structlog
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all LabLink models."""


def _build_engine() -> Engine:
    settings = get_settings()
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,         # Verify connections before use
        pool_size=5,
        max_overflow=10,
        echo=settings.app_debug,    # SQL echo in debug mode only
    )

    @event.listens_for(engine, "connect")
    def on_connect(dbapi_connection: object, connection_record: object) -> None:
        logger.debug("db_connection_acquired")

    return engine


# Engine and session factory are module-level singletons.
# They are created lazily on first import of this module.
engine: Engine = _build_engine()
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.

    Usage:
        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    """
    Verify the database is reachable.

    Returns True if connected, False otherwise.
    Does not raise — safe to call from health checks.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("db_connection_check_failed")
        return False
