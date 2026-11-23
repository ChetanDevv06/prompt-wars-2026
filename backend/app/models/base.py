"""
Declarative Base and reusable ORM mixins for SQLAlchemy 2.x.

Establishes:
- Centralized naming conventions for tables, primary keys, foreign keys,
  unique constraints, check constraints, and indexes.
- Consistent primary key conventions (UUID v4 and Integer).
- UTC-aware timestamp tracking mixin.
- Soft-delete auditing mixin.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ---------------------------------------------------------------------------
# Centralized PostgreSQL Constraint & Index Naming Conventions
# ---------------------------------------------------------------------------
# Prevents auto-generated unnamed constraints that cause migration diff issues.
POSTGRES_NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """
    Declarative Base for all LabLink domain models.

    All models inherit from this base class to ensure consistent metadata
    registration, naming conventions, and Alembic auto-generation support.
    """

    metadata = MetaData(naming_convention=POSTGRES_NAMING_CONVENTION)


# ---------------------------------------------------------------------------
# Reusable Primary Key Mixins
# ---------------------------------------------------------------------------


class UUIDPrimaryKeyMixin:
    """
    Mixin providing an RFC 4122 UUID v4 primary key.

    Recommended for student, project, booking, and equipment models
    where unguessable, distributed identifiers are required.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        sort_order=-100,
        comment="RFC 4122 UUID primary key",
    )


class IntegerPrimaryKeyMixin:
    """
    Mixin providing an autoincrementing integer primary key.

    Suitable for reference lookups, internal sequences, or audit logs.
    """

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        sort_order=-100,
        comment="Autoincrementing integer primary key",
    )


# ---------------------------------------------------------------------------
# Timestamp & Audit Mixins
# ---------------------------------------------------------------------------


class TimestampMixin:
    """
    Mixin providing UTC-aware creation and update timestamp columns.

    Uses PostgreSQL server_default `CURRENT_TIMESTAMP` / `now()` so timestamps
    are reliably recorded by the database engine, with Python-side onupdate.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Record creation timestamp (UTC)",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Record last update timestamp (UTC)",
    )


class SoftDeleteMixin:
    """
    Mixin providing soft-delete lifecycle tracking.

    Enables audit trails without physical record destruction.
    """

    is_deleted: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        index=True,
        comment="Soft-delete flag",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
        nullable=True,
        comment="Timestamp when record was marked deleted (UTC)",
    )
