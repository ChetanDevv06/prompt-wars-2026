"""
Allocation models: AllocationRun and AllocationAssignment.

Records the execution and results of LIAE (LabLink Intelligent Allocation Engine).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import AllocationRunType, SolverStatus
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.equipment import Equipment
    from app.models.project import Project, ProjectResourceRequirement
    from app.models.reservation import Reservation


class AllocationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Metadata and summary metrics for an optimization run by LIAE.

    Distinguishes solver outcome statuses: OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN, MODEL_INVALID.
    """

    __tablename__ = "allocation_runs"
    __table_args__ = (
        Index("ix_allocation_runs_status", "status"),
        Index("ix_allocation_runs_run_type", "run_type"),
        Index("ix_allocation_runs_created_at", "created_at"),
    )

    run_type: Mapped[AllocationRunType] = mapped_column(
        String(20),
        nullable=False,
        default=AllocationRunType.IMMEDIATE,
        comment="Immediate (single project) or batch (multi-project) run",
    )
    status: Mapped[SolverStatus] = mapped_column(
        String(30),
        nullable=False,
        comment="Solver outcome status (optimal, feasible, infeasible, unknown, model_invalid)",
    )
    solver_status_raw: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Exact string reported by the underlying CP-SAT solver",
    )
    solve_time_seconds: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Execution duration of the solver in seconds",
    )

    # Time horizon
    horizon_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Start of scheduling window evaluated (UTC)",
    )
    horizon_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="End of scheduling window evaluated (UTC)",
    )

    # Summary metrics
    total_projects: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Total projects considered in run"
    )
    allocated_projects: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Projects with at least one requirement allocated",
    )
    total_requirements: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Total requirements evaluated"
    )
    satisfied_requirements: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Requirements successfully scheduled"
    )

    # Lexicographic objective scores recorded as JSON string
    objective_values: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Serialized objective values for L1..L5",
    )
    fairness_metrics: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Serialized fairness and balance metrics",
    )
    diagnostics: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="General solver diagnostic or failure message",
    )

    # Relationships
    assignments: Mapped[list[AllocationAssignment]] = relationship(
        "AllocationAssignment",
        back_populates="allocation_run",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<AllocationRun id={self.id} type={self.run_type.value} "
            f"status={self.status.value} "
            f"satisfied={self.satisfied_requirements}/{self.total_requirements}>"
        )


class AllocationAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Detailed resource assignment (or unmet record) for a project requirement.
    """

    __tablename__ = "allocation_assignments"
    __table_args__ = (
        Index("ix_allocation_assignments_run_id", "allocation_run_id"),
        Index("ix_allocation_assignments_project_id", "project_id"),
        Index("ix_allocation_assignments_requirement_id", "requirement_id"),
        Index("ix_allocation_assignments_equipment_id", "equipment_id"),
    )

    allocation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("allocation_runs.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project_resource_requirements.id", ondelete="CASCADE"),
        nullable=False,
    )
    equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("equipment.id", ondelete="SET NULL"),
        nullable=True,
        comment="Allocated equipment (None if requirement was unmet)",
    )

    # Assigned time window
    assigned_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Assigned start time (UTC)",
    )
    assigned_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Assigned end time (UTC)",
    )

    is_satisfied: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if resource was successfully allocated, False if unmet",
    )
    is_primary_match: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="True if requested equipment, False if compatible substitute",
    )

    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Explainable reasoning for assignment or why unmet",
    )

    # Link to reservation if applied
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reservations.id", ondelete="SET NULL"),
        nullable=True,
        comment="Linked reservation once converted to provisional hold or confirmed",
    )

    # Relationships
    allocation_run: Mapped[AllocationRun] = relationship(
        "AllocationRun", back_populates="assignments"
    )
    project: Mapped[Project] = relationship("Project")
    requirement: Mapped[ProjectResourceRequirement] = relationship("ProjectResourceRequirement")
    equipment: Mapped[Equipment | None] = relationship("Equipment")
    reservation: Mapped[Reservation | None] = relationship("Reservation")

    def __repr__(self) -> str:
        return (
            f"<AllocationAssignment run={self.allocation_run_id} "
            f"req={self.requirement_id} satisfied={self.is_satisfied}>"
        )
