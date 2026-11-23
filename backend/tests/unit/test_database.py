"""
Unit tests for database infrastructure, ORM Base, and session lifecycle.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table, create_engine
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import Settings
from app.infrastructure.database import (
    build_engine,
    build_session_factory,
    check_database_connection,
    get_db,
    get_db_context,
    get_sanitized_db_url,
)
from app.models.base import (
    POSTGRES_NAMING_CONVENTION,
    Base,
    IntegerPrimaryKeyMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class TestNamingConventions:
    """Verifies standard PostgreSQL naming conventions."""

    def test_naming_convention_keys(self) -> None:
        """Convention dictionary must include ix, uq, ck, fk, and pk."""
        required_keys = {"ix", "uq", "ck", "fk", "pk"}
        assert required_keys.issubset(POSTGRES_NAMING_CONVENTION.keys())

    def test_declarative_base_metadata_naming_conventions(self) -> None:
        """Declarative Base metadata must use the centralized convention."""
        assert Base.metadata.naming_convention == POSTGRES_NAMING_CONVENTION

    def test_table_constraint_naming_generated(self) -> None:
        """Constraints created on Base models adhere to naming templates."""

        class _SampleParent(Base):
            __tablename__ = "sample_parents"
            id: Mapped[int] = mapped_column(primary_key=True)

        class _SampleChild(Base):
            __tablename__ = "sample_children"
            id: Mapped[int] = mapped_column(primary_key=True)
            parent_id = Column(Integer, ForeignKey("sample_parents.id"))

        table = _SampleChild.__table__
        assert isinstance(table, Table)
        fk_constraint = next(iter(table.foreign_key_constraints))
        assert fk_constraint.name == "fk_sample_children_parent_id_sample_parents"


class TestORMMixins:
    """Verifies reusable ORM mixins."""

    def test_uuid_primary_key_mixin(self) -> None:
        class _TestUUIDEntity(Base, UUIDPrimaryKeyMixin):
            __tablename__ = "test_uuid_entities"
            name: Mapped[str] = mapped_column(String(50))

        entity = _TestUUIDEntity(name="Resource A")
        # Mixin default generates a uuid.UUID
        assert isinstance(entity.id, uuid.UUID) or callable(_TestUUIDEntity.id.default.arg)

    def test_integer_primary_key_mixin(self) -> None:
        class _TestIntEntity(Base, IntegerPrimaryKeyMixin):
            __tablename__ = "test_int_entities"
            name: Mapped[str] = mapped_column(String(50))

        col = _TestIntEntity.__table__.columns["id"]
        assert col.primary_key is True
        assert col.autoincrement is True

    def test_timestamp_mixin_columns(self) -> None:
        class _TestTimestampEntity(Base, TimestampMixin):
            __tablename__ = "test_timestamp_entities"
            id: Mapped[int] = mapped_column(primary_key=True)

        table = _TestTimestampEntity.__table__
        assert "created_at" in table.columns
        assert "updated_at" in table.columns
        assert table.columns["created_at"].nullable is False
        assert table.columns["updated_at"].nullable is False
        assert getattr(table.columns["created_at"].type, "timezone", False) is True
        assert getattr(table.columns["updated_at"].type, "timezone", False) is True

    def test_soft_delete_mixin_columns(self) -> None:
        class _TestSoftDeleteEntity(Base, SoftDeleteMixin):
            __tablename__ = "test_soft_delete_entities"
            id: Mapped[int] = mapped_column(primary_key=True)

        table = _TestSoftDeleteEntity.__table__
        assert "is_deleted" in table.columns
        assert "deleted_at" in table.columns
        assert table.columns["is_deleted"].nullable is False
        assert table.columns["deleted_at"].nullable is True


class TestSanitizedDatabaseURL:
    """Verifies that credentials are never leaked in logs or error messages."""

    def test_masks_password_in_standard_url(self) -> None:
        raw = "postgresql://lablink_user:super_secret_pw@db.cluster.internal:5432/lablink"
        sanitized = get_sanitized_db_url(raw)
        assert "super_secret_pw" not in sanitized
        assert "***" in sanitized
        assert "lablink_user" in sanitized
        assert "db.cluster.internal" in sanitized

    def test_masks_password_in_sqlite_or_no_password(self) -> None:
        raw = "sqlite:///./test.db"
        sanitized = get_sanitized_db_url(raw)
        assert sanitized == "sqlite:///./test.db"

    def test_fallback_on_invalid_url(self) -> None:
        sanitized = get_sanitized_db_url("not-a-valid-url:::")
        assert "postgresql://" in sanitized


class TestSessionFactoryAndTransactions:
    """Verifies transaction boundaries, commit, rollback, and cleanup."""

    @pytest.fixture
    def memory_session_factory(self) -> tuple[object, object]:
        """Provides an isolated in-memory SQLite engine and session factory with StaticPool."""
        from sqlalchemy.orm import DeclarativeBase as FixtureBase
        from sqlalchemy.pool import StaticPool

        class _LocalBase(FixtureBase):
            metadata = MetaData(naming_convention=POSTGRES_NAMING_CONVENTION)

        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        class _TempItem(_LocalBase):
            __tablename__ = "temp_items"
            id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
            name: Mapped[str] = mapped_column(String(50))

        _LocalBase.metadata.create_all(test_engine)
        factory = build_session_factory(test_engine)
        return factory, _TempItem

    def test_build_engine_from_settings(self) -> None:
        custom_settings = Settings(
            app_env="test",
            database_url="sqlite:///:memory:",
            database_pool_size=7,
            database_max_overflow=12,
            database_echo=False,
        )
        eng = build_engine(custom_settings)
        assert eng is not None

    def test_get_db_context_commit_on_success(
        self, memory_session_factory: tuple[object, object]
    ) -> None:
        factory, item_cls = memory_session_factory

        with get_db_context(session_factory=factory) as session:  # type: ignore[arg-type]
            session.add(item_cls(name="Committed Item"))  # type: ignore[call-arg]

        # Verify item was persisted across sessions
        read_session = factory()  # type: ignore[operator]
        try:
            persisted = read_session.query(item_cls).filter_by(name="Committed Item").first()
            assert persisted is not None
            assert persisted.name == "Committed Item"
        finally:
            read_session.close()

    def test_get_db_context_rollback_on_exception(
        self, memory_session_factory: tuple[object, object]
    ) -> None:
        factory, item_cls = memory_session_factory

        with pytest.raises(RuntimeError, match="Simulation Failure"):
            with get_db_context(session_factory=factory) as session:  # type: ignore[arg-type]
                session.add(item_cls(name="Rolled Back Item"))  # type: ignore[call-arg]
                raise RuntimeError("Simulation Failure")

        # Verify item was NOT persisted
        read_session = factory()  # type: ignore[operator]
        try:
            persisted = read_session.query(item_cls).filter_by(name="Rolled Back Item").first()
            assert persisted is None
        finally:
            read_session.close()

    def test_get_db_dependency_rollback_on_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """FastAPI get_db dependency rolls back when caller fails."""
        test_engine = create_engine("sqlite:///:memory:")

        class _SampleRecord(Base):
            __tablename__ = "sample_records"
            id: Mapped[int] = mapped_column(primary_key=True)
            val: Mapped[str] = mapped_column(String(20))

        Base.metadata.create_all(test_engine)
        factory = build_session_factory(test_engine)
        monkeypatch.setattr("app.infrastructure.database.SessionLocal", factory)

        gen = get_db()
        session = next(gen)
        session.add(_SampleRecord(val="temporary"))

        with pytest.raises(ValueError, match="Request error"):
            gen.throw(ValueError("Request error"))

        # Check that session is rolled back
        verify_session = factory()
        try:
            assert verify_session.query(_SampleRecord).count() == 0
        finally:
            verify_session.close()

    def test_check_database_connection_failure(self) -> None:
        """Verifies check_database_connection returns False when database is unreachable."""
        # Pointing to an impossible path immediately fails without network timeouts
        unreachable_engine = create_engine("sqlite:///non_existent_dir_probe_xyz/fail.db")
        connected = check_database_connection(unreachable_engine)
        assert connected is False
