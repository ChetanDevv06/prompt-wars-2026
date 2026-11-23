"""
API endpoints: LIAE (LabLink Intelligent Allocation Engine) orchestration.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.schemas.allocation import (
    AllocationExplanationResponse,
    AllocationListResponse,
    AllocationRunResponse,
    ApplyAllocationRequest,
    ApplyAllocationResponse,
    BatchAllocationRequest,
    ImmediateAllocationRequest,
)
from app.api.v1.schemas_common import SuccessResponse
from app.infrastructure.database import get_db
from app.services.allocation import AllocationService

router = APIRouter()


@router.post(
    "/allocations/optimise",
    response_model=SuccessResponse[AllocationRunResponse],
    status_code=status.HTTP_200_OK,
    summary="Run immediate single-project optimization",
    description=(
        "Allocates laboratory equipment for a single project's resource "
        "requirements using OR-Tools CP-SAT."
    ),
)
def run_immediate_allocation(
    body: ImmediateAllocationRequest,
    session: Session = Depends(get_db),
) -> SuccessResponse[AllocationRunResponse]:
    """Execute immediate allocation run."""
    svc = AllocationService(session)
    run = svc.run_immediate_allocation(
        project_id=body.project_id,
        horizon_start=body.horizon_start,
        horizon_end=body.horizon_end,
        solver_time_limit=body.solver_time_limit,
    )
    session.commit()
    return SuccessResponse(data=AllocationRunResponse.model_validate(run))


@router.post(
    "/allocations/batch",
    response_model=SuccessResponse[AllocationRunResponse],
    status_code=status.HTTP_200_OK,
    summary="Run multi-project batch optimization",
    description=(
        "Allocates resources across multiple competing projects "
        "considering priority, fairness, and deadlines."
    ),
)
def run_batch_allocation(
    body: BatchAllocationRequest,
    session: Session = Depends(get_db),
) -> SuccessResponse[AllocationRunResponse]:
    """Execute batch allocation run."""
    svc = AllocationService(session)
    run = svc.run_batch_allocation(
        project_ids=body.project_ids,
        horizon_start=body.horizon_start,
        horizon_end=body.horizon_end,
        solver_time_limit=body.solver_time_limit,
    )
    session.commit()
    return SuccessResponse(data=AllocationRunResponse.model_validate(run))


@router.get(
    "/allocations",
    response_model=SuccessResponse[AllocationListResponse],
    summary="List past allocation runs",
    description="Return historical allocation runs with pagination.",
)
def list_allocation_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
) -> SuccessResponse[AllocationListResponse]:
    """List historical allocation runs."""
    svc = AllocationService(session)
    items, total = svc.list_allocation_runs(limit=limit, offset=offset)
    return SuccessResponse(
        data=AllocationListResponse(
            items=[AllocationRunResponse.model_validate(r) for r in items],
            total=total,
            limit=limit,
            offset=offset,
        )
    )


@router.get(
    "/allocations/{run_id}",
    response_model=SuccessResponse[AllocationRunResponse],
    summary="Get allocation run details",
    description="Retrieve full details and assignments for a specific allocation run.",
)
def get_allocation_run(
    run_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> SuccessResponse[AllocationRunResponse]:
    """Get single allocation run."""
    svc = AllocationService(session)
    run = svc.get_allocation_run(run_id)
    return SuccessResponse(data=AllocationRunResponse.model_validate(run))


@router.get(
    "/allocations/{run_id}/explanation",
    response_model=SuccessResponse[AllocationExplanationResponse],
    summary="Get explainability report for allocation run",
    description=(
        "Provides human-readable diagnostic explanations for scheduling "
        "decisions and fairness scores."
    ),
)
def get_allocation_explanation(
    run_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> SuccessResponse[AllocationExplanationResponse]:
    """Get explainability report."""
    svc = AllocationService(session)
    run = svc.get_allocation_run(run_id)

    obj_vals: dict[str, Any] = {}
    if run.objective_values:
        try:
            obj_vals = json.loads(run.objective_values)
        except Exception:
            obj_vals = {}

    fairness_metrics: dict[str, Any] = {}
    if run.fairness_metrics:
        try:
            fairness_metrics = json.loads(run.fairness_metrics)
        except Exception:
            fairness_metrics = {}

    assignments_exps = [
        {
            "assignment_id": str(a.id),
            "requirement_id": str(a.requirement_id),
            "project_id": str(a.project_id),
            "equipment_id": str(a.equipment_id) if a.equipment_id else None,
            "is_satisfied": a.is_satisfied,
            "is_primary_match": a.is_primary_match,
            "assigned_start": a.assigned_start.isoformat() if a.assigned_start else None,
            "assigned_end": a.assigned_end.isoformat() if a.assigned_end else None,
            "explanation": a.explanation,
        }
        for a in run.assignments
    ]

    status_str = run.status.value if hasattr(run.status, "value") else str(run.status)
    summary = (
        f"LIAE run {run.id} concluded with status '{status_str}' "
        f"({run.satisfied_requirements}/{run.total_requirements} requirements satisfied "
        f"across {run.allocated_projects}/{run.total_projects} projects in "
        f"{run.solve_time_seconds:.2f}s)."
    )

    return SuccessResponse(
        data=AllocationExplanationResponse(
            run_id=run.id,
            solver_status=run.status,
            solver_status_raw=run.solver_status_raw,
            solve_time_seconds=run.solve_time_seconds,
            summary=summary,
            diagnostics=run.diagnostics,
            objective_values=obj_vals,
            fairness_metrics=fairness_metrics,
            assignments_explanations=assignments_exps,
        )
    )


@router.post(
    "/allocations/{run_id}/apply",
    response_model=SuccessResponse[ApplyAllocationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Apply allocation plan to create reservations",
    description=(
        "Converts satisfied assignments into provisional holds or confirmed "
        "reservations with double-booking collision checks."
    ),
)
def apply_allocation(
    run_id: uuid.UUID,
    body: ApplyAllocationRequest,
    session: Session = Depends(get_db),
) -> SuccessResponse[ApplyAllocationResponse]:
    """Apply allocation plan to create reservations."""
    svc = AllocationService(session)
    reservations = svc.apply_allocation(
        run_id=run_id,
        as_status=body.as_status,
        hold_minutes=body.hold_minutes,
        approved_by=body.approved_by,
    )
    session.commit()

    return SuccessResponse(
        data=ApplyAllocationResponse(
            run_id=run_id,
            reservations_created=len(reservations),
            reservation_ids=[r.id for r in reservations],
            status=body.as_status,
        )
    )
