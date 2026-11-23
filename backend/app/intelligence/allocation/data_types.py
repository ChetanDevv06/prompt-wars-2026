"""
LIAE: LabLink Intelligent Allocation Engine — Data Types and Specifications.

Pure Python dataclasses for solver inputs, intermediate structures, and results.
Completely decoupled from database persistence and HTTP transport.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.enums import DependencyType, ProjectPriority, SolverStatus, UserRole


@dataclass
class EquipmentSpec:
    """Equipment capacity, availability, and laboratory association."""

    id: uuid.UUID
    name: str
    laboratory_id: uuid.UUID
    quantity: int = 1
    is_bookable: bool = True
    status: str = "available"


@dataclass
class SubstituteSpec:
    """Permitted substitute mapping: primary equipment can be substituted by compatible units."""

    primary_id: uuid.UUID
    compatible_id: uuid.UUID
    notes: str | None = None


@dataclass
class ExistingCommitmentSpec:
    """
    Fixed, immutable time commitment on equipment (confirmed reservation or maintenance).

    Hard constraint: LIAE will NEVER displace or overlap an existing commitment.
    """

    id: uuid.UUID
    equipment_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    quantity: int = 1
    commitment_type: str = "confirmed_reservation"  # "confirmed_reservation" | "maintenance"


@dataclass
class RequirementSpec:
    """Resource requirement defined by a project."""

    id: uuid.UUID
    project_id: uuid.UUID
    equipment_id: uuid.UUID  # Requested primary equipment
    duration_minutes: int
    quantity_required: int = 1
    earliest_start: datetime | None = None
    latest_end: datetime | None = None
    deadline: datetime | None = None
    is_critical: bool = False
    notes: str | None = None


@dataclass
class DependencySpec:
    """DAG dependency between two requirements of the same project."""

    predecessor_id: uuid.UUID
    successor_id: uuid.UUID
    dependency_type: DependencyType = DependencyType.SEQUENTIAL


@dataclass
class ProjectSpec:
    """Project requesting laboratory resource allocation."""

    id: uuid.UUID
    name: str
    priority: ProjectPriority = ProjectPriority.MEDIUM
    deadline: datetime | None = None
    preferred_start: datetime | None = None
    preferred_end: datetime | None = None
    department_id: uuid.UUID | None = None
    submitter_name: str = ""
    submitter_email: str = ""
    submitter_role: UserRole = UserRole.STUDENT
    requirements: list[RequirementSpec] = field(default_factory=list)
    dependencies: list[DependencySpec] = field(default_factory=list)


@dataclass
class HistoricalUsageSpec:
    """Historical resource usage records for need-aware fairness calculation."""

    department_id: uuid.UUID | None = None
    submitter_email: str | None = None
    confirmed_reservations_count: int = 0
    total_hours_used: float = 0.0


@dataclass
class AllocationInput:
    """Complete specification package passed to LIAE solver."""

    horizon_start: datetime
    horizon_end: datetime
    projects: list[ProjectSpec] = field(default_factory=list)
    equipment: list[EquipmentSpec] = field(default_factory=list)
    substitutes: list[SubstituteSpec] = field(default_factory=list)
    commitments: list[ExistingCommitmentSpec] = field(default_factory=list)
    historical_usage: list[HistoricalUsageSpec] = field(default_factory=list)
    solver_time_limit_seconds: float = 10.0
    enable_lexicographic: bool = True


@dataclass
class ScheduledAssignment:
    """The allocation decision for an individual resource requirement."""

    requirement_id: uuid.UUID
    project_id: uuid.UUID
    equipment_id: uuid.UUID | None
    assigned_start: datetime | None
    assigned_end: datetime | None
    is_satisfied: bool
    is_primary_match: bool
    explanation: str
    decision_factors: list[str] = field(default_factory=list)


@dataclass
class ObjectiveScores:
    """Detailed scores for each level in the lexicographic objective hierarchy."""

    l1_critical_unmet: int = 0
    l1_deadline_lateness_minutes: int = 0
    l2_need_weighted_points: int = 0
    l3_fairness_balance_score: int = 0
    l4_utilization_minutes: int = 0
    l5_preference_deviation_minutes: int = 0


@dataclass
class FairnessMetrics:
    """Quantified fairness metrics for the allocation run."""

    jains_fairness_index: float = 1.0
    gini_coefficient: float = 0.0
    department_fulfillment_rates: dict[str, float] = field(default_factory=dict)
    historical_data_available: bool = False
    notes: str = ""


@dataclass
class AllocationResult:
    """Full result produced by LIAE."""

    status: SolverStatus
    solver_status_raw: str
    solve_time_seconds: float
    assignments: list[ScheduledAssignment]
    total_projects: int
    allocated_projects: int
    total_requirements: int
    satisfied_requirements: int
    objective_scores: ObjectiveScores
    fairness_metrics: FairnessMetrics
    diagnostic_message: str = ""
