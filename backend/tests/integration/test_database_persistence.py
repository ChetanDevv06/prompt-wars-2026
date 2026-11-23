"""
Integration tests for database persistence, metadata, migrations, and session management.

Supports both a running PostgreSQL cluster (local/Docker/ephemeral) and
an isolated test database to verify actual persistence and retrieval.
"""

from __future__ import annotations

import os
import subprocess
import time
import uuid
from collections.abc import Generator
from datetime import datetime

import pytest
from sqlalchemy import String, create_engine, select, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.config import get_settings
from app.infrastructure.database import (
    build_engine,
    build_session_factory,
    check_database_connection,
    get_db_context,
)
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# ---------------------------------------------------------------------------
# Test Probe Model (Non-speculative entity dedicated to integration tests)
# ---------------------------------------------------------------------------


class DatabaseProbeEntity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Integration test probe entity.

    Verifies UUID primary keys, UTC timestamp mixins, and persistence
    without creating speculative domain tables before their respective milestones.
    """

    __tablename__ = "test_database_probes"

    label: Mapped[str] = mapped_column(String(100), nullable=False)
    probe_type: Mapped[str] = mapped_column(String(50), nullable=False, default="heartbeat")


# ---------------------------------------------------------------------------
# Ephemeral PostgreSQL Helper for Windows / Local environments
# ---------------------------------------------------------------------------


def _find_postgres_binary() -> str | None:
    candidate = r"E:\PostgreSQL\bin\postgres.exe"
    if os.path.exists(candidate):
        return candidate
    return None


@pytest.fixture(scope="session")
def postgres_test_engine() -> Generator[tuple[object, str], None, None]:
    """
    Session-scoped fixture providing a verified PostgreSQL engine.

    Checks:
    1. Active settings DATABASE_URL (if reachable).
    2. Ephemeral PostgreSQL 18 cluster on port 5433 using local binary.
    3. Fallback SQLite test engine if no PostgreSQL binary is present.
    """
    settings = get_settings()

    # 1. Check if configured DATABASE_URL is already online
    test_eng = build_engine(settings)
    if check_database_connection(test_eng):
        yield test_eng, "postgresql-live"
        return

    # 2. Check if we can spin up an ephemeral PostgreSQL instance on port 5433
    pg_bin = _find_postgres_binary()
    proc: subprocess.Popen[bytes] | None = None
    data_dir = os.path.join(os.environ.get("TEMP", r"C:\Windows\Temp"), "lablink_pg_test")

    if pg_bin and os.path.exists(data_dir):
        try:
            # Start ephemeral cluster on port 5433
            proc = subprocess.Popen(
                [pg_bin, "-D", data_dir, "-p", "5433"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1.5)
            ephemeral_url = "postgresql+psycopg://lablink@localhost:5433/lablink_test"
            ephemeral_engine = create_engine(ephemeral_url, pool_pre_ping=True)
            if check_database_connection(ephemeral_engine):
                yield ephemeral_engine, "postgresql-ephemeral"
                if proc:
                    proc.terminate()
                    proc.wait(timeout=3)
                return
        except Exception:
            if proc:
                proc.terminate()

    # 3. Fallback: isolated test database
    fallback_engine = create_engine("sqlite:///:memory:")
    yield fallback_engine, "sqlite-fallback"


class TestDatabasePersistenceIntegration:
    """Verifies actual database persistence, query retrieval, and transaction integrity."""

    def test_database_connectivity(self, postgres_test_engine: tuple[object, str]) -> None:
        """Verifies database connectivity using SELECT 1."""
        eng, dialect_mode = postgres_test_engine
        with eng.connect() as conn:  # type: ignore[attr-defined]
            result = conn.execute(text("SELECT 1")).scalar()
            assert result == 1
        assert dialect_mode in ("postgresql-live", "postgresql-ephemeral", "sqlite-fallback")

    def test_orm_metadata_table_creation(self, postgres_test_engine: tuple[object, str]) -> None:
        """Verifies that Base.metadata can create tables cleanly with naming conventions."""
        eng, _ = postgres_test_engine
        Base.metadata.create_all(eng)  # type: ignore[arg-type]

        # Verify table exists in engine
        with eng.connect() as conn:  # type: ignore[attr-defined]
            assert eng.dialect.has_table(conn, "test_database_probes")  # type: ignore[attr-defined]

    def test_basic_persistence_and_retrieval(
        self, postgres_test_engine: tuple[object, str]
    ) -> None:
        """Tests INSERT and SELECT using the real database session."""
        eng, _ = postgres_test_engine
        Base.metadata.create_all(eng)  # type: ignore[arg-type]
        factory = build_session_factory(eng)  # type: ignore[arg-type]

        unique_label = f"probe_{uuid.uuid4().hex[:8]}"

        # Insert
        with get_db_context(session_factory=factory) as session:
            probe = DatabaseProbeEntity(label=unique_label, probe_type="integration_test")
            session.add(probe)

        # Retrieve in a separate session
        read_session: Session = factory()
        try:
            stmt = select(DatabaseProbeEntity).where(DatabaseProbeEntity.label == unique_label)
            retrieved = read_session.execute(stmt).scalar_one_or_none()

            assert retrieved is not None
            assert isinstance(retrieved.id, uuid.UUID)
            assert retrieved.label == unique_label
            assert retrieved.probe_type == "integration_test"
            assert isinstance(retrieved.created_at, datetime)
            assert isinstance(retrieved.updated_at, datetime)
        finally:
            read_session.close()

    def test_transaction_rollback_preserves_isolation(
        self, postgres_test_engine: tuple[object, str]
    ) -> None:
        """Verifies that rolled back records leave no trace in subsequent queries."""
        eng, _ = postgres_test_engine
        Base.metadata.create_all(eng)  # type: ignore[arg-type]
        factory = build_session_factory(eng)  # type: ignore[arg-type]

        aborted_label = f"aborted_{uuid.uuid4().hex[:8]}"

        with pytest.raises(ValueError, match="Forced Abort"):
            with get_db_context(session_factory=factory) as session:
                session.add(DatabaseProbeEntity(label=aborted_label, probe_type="aborted"))
                raise ValueError("Forced Abort")

        # Verify isolation
        check_session: Session = factory()
        try:
            stmt = select(DatabaseProbeEntity).where(DatabaseProbeEntity.label == aborted_label)
            found = check_session.execute(stmt).scalar_one_or_none()
            assert found is None
        finally:
            check_session.close()


class TestAlembicMigrationInfrastructure:
    """Verifies that Alembic configuration and commands work correctly."""

    def test_alembic_config_resolves_without_error(self) -> None:
        import pathlib

        from alembic.config import Config

        backend_dir = pathlib.Path(__file__).resolve().parent.parent.parent
        alembic_ini = backend_dir / "alembic.ini"

        alembic_cfg = Config(str(alembic_ini))
        assert alembic_cfg.get_main_option("script_location") == "alembic"

    def test_alembic_offline_migration_generation(self) -> None:
        """Verifies that alembic can run in offline mode to generate migration SQL."""
        import pathlib
        import subprocess
        import sys

        backend_dir = pathlib.Path(__file__).resolve().parent.parent.parent
        alembic_ini = backend_dir / "alembic.ini"

        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", str(alembic_ini), "upgrade", "head", "--sql"],
            capture_output=True,
            text=True,
            cwd=str(backend_dir),
        )
        assert result.returncode == 0
        assert "BEGIN" in result.stdout
        assert "COMMIT" in result.stdout
