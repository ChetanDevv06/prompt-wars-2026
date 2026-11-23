"""
Project models: Project, ProjectResourceRequirement, RequirementDependency.
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
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import DependencyType, ProjectPriority, ProjectStatus, UserRole
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.equipment import Equipment
    from app.models.organisation import Department
    from app.models.reservation import Reservation


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A research or coursework project that requires laboratory resources.

    Projects contain one or more resource requirements that the allocation
    engine must satisfy.
    """

    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "length(trim(name)) > 0", name="ck_projects_name_non_empty"
        ),
        CheckConstraint(
            "deadline IS NULL OR deadline > created_at",
            name="ck_projects_deadline_after_creation",
        ),
        Index("ix_projects_department_id", "department_id"),
        Index("ix_projects_submitter_role", "submitter_role"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        String(20),
        nullable=False,
        default=ProjectStatus.DRAFT,
        index=True,
    )
    priority: Mapped[ProjectPriority] = mapped_column(
        String(20),
        nullable=False,
        default=ProjectPriority.MEDIUM,
    )
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Project completion deadline (UTC)"
    )
    preferred_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Preferred scheduling window start (UTC)"
    )
    preferred_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Preferred scheduling window end (UTC)"
    )

    # Submitter identity fields — no auth in M03; role used for workflow routing
    submitter_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Name of the person submitting the project"
    )
    submitter_email: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Contact email for the submitter"
    )
    submitter_role: Mapped[UserRole] = mapped_column(
        String(20),
        nullable=False,
        default=UserRole.STUDENT,
        comment="Role of the submitter (student / faculty / administrator)",
    )

    # FK
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    department: Mapped[Department | None] = relationship(
        "Department", back_populates="projects"
    )
    resource_requirements: Mapped[list[ProjectResourceRequirement]] = relationship(
        "ProjectResourceRequirement",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} name={self.name!r} status={self.status.value}>"


class ProjectResourceRequirement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A single resource requirement within a project.

    Specifies which equipment is needed, for how long, and when.
    May participate in dependency relationships with other requirements.
    """

    __tablename__ = "project_resource_requirements"
    __table_args__ = (
        CheckConstraint(
            "quantity_required >= 1", name="ck_requirements_quantity_positive"
        ),
        CheckConstraint(
            "duration_minutes >= 1", name="ck_requirements_duration_positive"
        ),
        CheckConstraint(
            "earliest_start IS NULL OR latest_end IS NULL OR latest_end > earliest_start",
            name="ck_requirements_valid_window",
        ),
        Index("ix_requirements_project_id", "project_id"),
        Index("ix_requirements_equipment_id", "equipment_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    equipment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("equipment.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_required: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Number of units needed"
    )
    duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Expected usage duration in minutes"
    )
    earliest_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Earliest acceptable start time (UTC)",
    )
    latest_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Latest acceptable end time (UTC)",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_critical: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="Whether this requirement is critical (must be satisfied)",
    )

    # Relationships
    project: Mapped[Project] = relationship("Project", back_populates="resource_requirements")
    equipment: Mapped[Equipment] = relationship(
        "Equipment", back_populates="resource_requirements"
    )
    reservations: Mapped[list[Reservation]] = relationship(
        "Reservation", back_populates="requirement"
    )
    # DAG edges where this requirement is the predecessor
    outgoing_dependencies: Mapped[list[RequirementDependency]] = relationship(
        "RequirementDependency",
        foreign_keys="RequirementDependency.predecessor_id",
        back_populates="predecessor",
        cascade="all, delete-orphan",
    )
    # DAG edges where this requirement is the successor
    incoming_dependencies: Mapped[list[RequirementDependency]] = relationship(
        "RequirementDependency",
        foreign_keys="RequirementDependency.successor_id",
        back_populates="successor",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<ProjectResourceRequirement id={self.id} "
            f"project={self.project_id} equipment={self.equipment_id}>"
        )


class RequirementDependency(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Directed dependency edge between two resource requirements (DAG).

    predecessor → successor means successor cannot start until predecessor finishes.
    """

    __tablename__ = "requirement_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "predecessor_id",
            "successor_id",
            name="uq_requirement_dependencies_pair",
        ),
        CheckConstraint(
            "predecessor_id != successor_id",
            name="ck_requirement_dependencies_no_self_ref",
        ),
        Index("ix_requirement_dependencies_predecessor_id", "predecessor_id"),
        Index("ix_requirement_dependencies_successor_id", "successor_id"),
    )

    predecessor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project_resource_requirements.id", ondelete="CASCADE"),
        nullable=False,
    )
    successor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project_resource_requirements.id", ondelete="CASCADE"),
        nullable=False,
    )
    dependency_type: Mapped[DependencyType] = mapped_column(
        String(20),
        nullable=False,
        default=DependencyType.SEQUENTIAL,
        comment="Nature of the dependency (sequential / parallel / conditional)",
    )

    # Relationships
    predecessor: Mapped[ProjectResourceRequirement] = relationship(
        "ProjectResourceRequirement",
        foreign_keys=[predecessor_id],
        back_populates="outgoing_dependencies",
    )
    successor: Mapped[ProjectResourceRequirement] = relationship(
        "ProjectResourceRequirement",
        foreign_keys=[successor_id],
        back_populates="incoming_dependencies",
    )

    def __repr__(self) -> str:
        return (
            f"<RequirementDependency {self.predecessor_id} → {self.successor_id} "
            f"({self.dependency_type.value})>"
        )
