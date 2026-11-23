"""
Reservation models: Reservation, ReservationHistory.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import ApprovalStatus, ReservationStatus, UserRole
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.equipment import Equipment
    from app.models.project import Project, ProjectResourceRequirement


class Reservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A concrete time-slot reservation of a piece of equipment.

    Implements the full lifecycle from PENDING → CONFIRMED or terminal states.
    Uses an EXCLUDE constraint (via check at application layer + PostgreSQL-side
    index) to prevent overlapping CONFIRMED reservations for the same equipment.
    """

    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint(
            "ends_at > starts_at", name="ck_reservations_valid_range"
        ),
        CheckConstraint(
            "quantity_reserved >= 1", name="ck_reservations_quantity_positive"
        ),
        # Partial index to enforce uniqueness of confirmed time-windows
        # Full EXCLUDE USING gist requires btree_gist extension; we enforce
        # overlap at the application layer and add a standard index for queries.
        Index("ix_reservations_equipment_id_starts_at", "equipment_id", "starts_at"),
        Index("ix_reservations_project_id", "project_id"),
        Index("ix_reservations_hold_expires_at", "hold_expires_at"),
    )

    # Time window
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="Reservation start time (UTC)"
    )
    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="Reservation end time (UTC)"
    )

    # Lifecycle
    status: Mapped[ReservationStatus] = mapped_column(
        String(30),
        nullable=False,
        default=ReservationStatus.PENDING,
        index=True,
        comment="Current lifecycle state",
    )
    hold_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Provisional hold expiry timestamp (UTC)",
    )

    quantity_reserved: Mapped[int] = mapped_column(
        default=1, nullable=False, comment="Number of units reserved"
    )

    # Submitter info (no auth in M03)
    requester_name: Mapped[str] = mapped_column(String(255), nullable=False)
    requester_email: Mapped[str] = mapped_column(String(255), nullable=False)
    requester_role: Mapped[UserRole] = mapped_column(
        String(20), nullable=False, default=UserRole.STUDENT
    )

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Approval
    approval_status: Mapped[ApprovalStatus | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Approval decision (if applicable)",
    )
    approved_by: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Name of approver"
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # FK
    equipment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("equipment.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_resource_requirements.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    equipment: Mapped[Equipment] = relationship("Equipment", back_populates="reservations")
    project: Mapped[Project | None] = relationship("Project")
    requirement: Mapped[ProjectResourceRequirement | None] = relationship(
        "ProjectResourceRequirement", back_populates="reservations"
    )
    history: Mapped[list[ReservationHistory]] = relationship(
        "ReservationHistory", back_populates="reservation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Reservation id={self.id} equipment={self.equipment_id} "
            f"status={self.status} {self.starts_at} - {self.ends_at}>"
        )


class ReservationHistory(UUIDPrimaryKeyMixin, Base):
    """
    Immutable audit log of every status change on a reservation.

    Records who made the change, when, and what changed.
    """

    __tablename__ = "reservation_history"
    __table_args__ = (
        Index("ix_reservation_history_reservation_id", "reservation_id"),
        Index("ix_reservation_history_changed_at", "changed_at"),
    )

    reservation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[ReservationStatus | None] = mapped_column(
        String(30), nullable=True, comment="Previous status (null for initial creation)"
    )
    to_status: Mapped[ReservationStatus] = mapped_column(
        String(30), nullable=False, comment="New status after transition"
    )
    changed_by: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Actor who triggered the transition"
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Timestamp of the state change (UTC)",
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    reservation: Mapped[Reservation] = relationship("Reservation", back_populates="history")

    def __repr__(self) -> str:
        return (
            f"<ReservationHistory reservation={self.reservation_id} "
            f"{self.from_status} → {self.to_status}>"
        )
