"""
LabLink domain enumerations.

Centralised enum definitions for equipment status, reservation lifecycle,
approval states, and project priority. Used by ORM models, Pydantic schemas,
and business-logic services alike.
"""

from __future__ import annotations

import enum


class EquipmentStatus(enum.StrEnum):
    """Operational status of a piece of equipment."""

    AVAILABLE = "available"
    IN_USE = "in_use"
    UNDER_MAINTENANCE = "under_maintenance"
    DECOMMISSIONED = "decommissioned"
    UNAVAILABLE = "unavailable"


class EquipmentCategory(enum.StrEnum):
    """High-level category grouping for equipment."""

    COMPUTING = "computing"
    IMAGING = "imaging"
    MEASUREMENT = "measurement"
    FABRICATION = "fabrication"
    CHEMICAL = "chemical"
    BIOLOGICAL = "biological"
    ELECTRONICS = "electronics"
    OPTICS = "optics"
    MECHANICAL = "mechanical"
    OTHER = "other"


class ReservationStatus(enum.StrEnum):
    """
    Full reservation lifecycle as defined in SRS §9.

    Transitions:
        PENDING → ALLOCATED | REJECTED
        ALLOCATED → PROVISIONALLY_HELD | REJECTED
        PROVISIONALLY_HELD → CONFIRMED | REJECTED | EXPIRED
        CONFIRMED → CANCELLED | RELEASED
        REJECTED → (terminal)
        EXPIRED → (terminal)
        RELEASED → (terminal)
        CANCELLED → (terminal)
    """

    PENDING = "pending"
    ALLOCATED = "allocated"
    PROVISIONALLY_HELD = "provisionally_held"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    RELEASED = "released"
    CANCELLED = "cancelled"


# Valid state transitions
VALID_RESERVATION_TRANSITIONS: dict[ReservationStatus, set[ReservationStatus]] = {
    ReservationStatus.PENDING: {
        ReservationStatus.ALLOCATED,
        ReservationStatus.REJECTED,
        ReservationStatus.CANCELLED,
    },
    ReservationStatus.ALLOCATED: {
        ReservationStatus.PROVISIONALLY_HELD,
        ReservationStatus.REJECTED,
        ReservationStatus.CANCELLED,
    },
    ReservationStatus.PROVISIONALLY_HELD: {
        ReservationStatus.CONFIRMED,
        ReservationStatus.REJECTED,
        ReservationStatus.EXPIRED,
        ReservationStatus.CANCELLED,
    },
    ReservationStatus.CONFIRMED: {
        ReservationStatus.CANCELLED,
        ReservationStatus.RELEASED,
    },
    ReservationStatus.REJECTED: set(),
    ReservationStatus.EXPIRED: set(),
    ReservationStatus.RELEASED: set(),
    ReservationStatus.CANCELLED: set(),
}


class ApprovalStatus(enum.StrEnum):
    """Status of an approval decision."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class ProjectStatus(enum.StrEnum):
    """Lifecycle state of a project."""

    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"


class ProjectPriority(enum.StrEnum):
    """Scheduling priority level for a project."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DependencyType(enum.StrEnum):
    """
    Type of dependency between project resource requirements.

    SEQUENTIAL: requirement B cannot start until requirement A finishes.
    PARALLEL: requirements may run simultaneously.
    CONDITIONAL: requirement B runs only if A succeeds.
    """

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


class UserRole(enum.StrEnum):
    """User role for workflow routing (no authentication enforced in M03)."""

    STUDENT = "student"
    FACULTY = "faculty"
    ADMINISTRATOR = "administrator"
