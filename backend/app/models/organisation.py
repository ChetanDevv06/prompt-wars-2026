"""
Organisation models: Department and Laboratory.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.equipment import Equipment
    from app.models.project import Project


class Department(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Academic or research department.

    Departments own laboratories and sponsor projects.
    """

    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("code", name="uq_departments_code"),
        CheckConstraint("length(trim(name)) > 0", name="ck_departments_name_non_empty"),
        CheckConstraint("length(trim(code)) > 0", name="ck_departments_code_non_empty"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Full department name")
    code: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True, comment="Short department code (e.g. CS, BIO)"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        default=True, nullable=False, comment="Whether the department is active"
    )

    # Relationships
    laboratories: Mapped[list[Laboratory]] = relationship(
        "Laboratory", back_populates="department", cascade="all, delete-orphan"
    )
    projects: Mapped[list[Project]] = relationship("Project", back_populates="department")

    def __repr__(self) -> str:
        return f"<Department id={self.id} code={self.code!r}>"


class Laboratory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Physical laboratory space within a department.

    A laboratory may house multiple pieces of equipment.
    """

    __tablename__ = "laboratories"
    __table_args__ = (
        UniqueConstraint("code", name="uq_laboratories_code"),
        CheckConstraint("length(trim(name)) > 0", name="ck_laboratories_name_non_empty"),
        Index("ix_laboratories_department_id", "department_id"),
    )

    name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Laboratory display name"
    )
    code: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True, comment="Unique laboratory code"
    )
    location: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Physical location / building / room"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    capacity: Mapped[int | None] = mapped_column(nullable=True, comment="Maximum concurrent users")
    is_active: Mapped[bool] = mapped_column(
        default=True, nullable=False, comment="Whether the laboratory accepts bookings"
    )

    # FK
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )

    # Relationships
    department: Mapped[Department] = relationship("Department", back_populates="laboratories")
    equipment: Mapped[list[Equipment]] = relationship("Equipment", back_populates="laboratory")

    def __repr__(self) -> str:
        return f"<Laboratory id={self.id} code={self.code!r}>"
