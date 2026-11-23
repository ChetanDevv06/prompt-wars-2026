"""
Pydantic schemas for LIAE Allocation API endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import AllocationRunType, ReservationStatus, SolverStatus

# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------


class ImmediateAllocationRequest(BaseModel):
    """Request schema for optimizing allocation for a single project."""

    project_id: uuid.UUID
    horizon_start: datetime
    horizon_end: datetime
    solver_time_limit: float = Field(
        default=10.0,
        ge=0.5,
        le=120.0,
        description="Max solver execution time in seconds",
    )


class BatchAllocationRequest(BaseModel):
    """Request schema for multi-project batch optimization."""

    project_ids: list[uuid.UUID] | None = Field(
        default=None,
        description=(
            "Optional list of specific project IDs to allocate. "
            "If omitted, allocates for all active/draft projects."
        ),
    )
    horizon_start: datetime
    horizon_end: datetime
    solver_time_limit: float = Field(
        default=15.0,
        ge=0.5,
        le=300.0,
        description="Max solver execution time in seconds",
    )


class ApplyAllocationRequest(BaseModel):
    """Request schema for committing satisfied assignments to reservations."""

    as_status: ReservationStatus = Field(
        default=ReservationStatus.PROVISIONALLY_HELD,
        description="Target status for created reservations (PROVISIONALLY_HELD or CONFIRMED)",
    )
    hold_minutes: int = Field(
        default=60,
        ge=1,
        le=10080,
        description="Duration of provisional hold in minutes (if PROVISIONALLY_HELD)",
    )
    approved_by: str | None = Field(
        default=None,
        max_length=255,
        description="Approver name/email if confirmed directly",
    )


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------


class ScheduledAssignmentResponse(BaseModel):
    """Response schema for a single requirement assignment."""

    id: uuid.UUID
    allocation_run_id: uuid.UUID
    project_id: uuid.UUID
    requirement_id: uuid.UUID
    equipment_id: uuid.UUID | None = None
    assigned_start: datetime | None = None
    assigned_end: datetime | None = None
    is_satisfied: bool
    is_primary_match: bool
    explanation: str
    reservation_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AllocationRunResponse(BaseModel):
    """Response schema for an allocation run with full assignments."""

    id: uuid.UUID
    run_type: AllocationRunType
    status: SolverStatus
    solver_status_raw: str
    solve_time_seconds: float
    horizon_start: datetime
    horizon_end: datetime
    total_projects: int
    allocated_projects: int
    total_requirements: int
    satisfied_requirements: int
    objective_values: str | None = None
    fairness_metrics: str | None = None
    diagnostics: str | None = None
    assignments: list[ScheduledAssignmentResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class AllocationExplanationResponse(BaseModel):
    """Detailed explainability response for an allocation run."""

    run_id: uuid.UUID
    solver_status: SolverStatus
    solver_status_raw: str
    solve_time_seconds: float
    summary: str
    diagnostics: str | None = None
    objective_values: dict[str, Any] = {}
    fairness_metrics: dict[str, Any] = {}
    assignments_explanations: list[dict[str, Any]] = []


class AllocationListResponse(BaseModel):
    """Paginated list of past allocation runs."""

    items: list[AllocationRunResponse]
    total: int
    limit: int
    offset: int


class ApplyAllocationResponse(BaseModel):
    """Response after applying assignments as reservations."""

    run_id: uuid.UUID
    reservations_created: int
    reservation_ids: list[uuid.UUID]
    status: ReservationStatus
