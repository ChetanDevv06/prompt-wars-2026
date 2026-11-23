"""
API endpoints: Project and resource requirement management.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.schemas.project import (
    DependencyCreate,
    DependencyResponse,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
    RequirementCreate,
    RequirementResponse,
)
from app.api.v1.schemas_common import SuccessResponse
from app.domain.enums import ProjectStatus
from app.infrastructure.database import get_db
from app.services.project import ProjectService

router = APIRouter()


# ---------------------------------------------------------------------------
# Project endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/projects",
    response_model=SuccessResponse[ProjectResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create project",
    description="Create a new project with resource requirements.",
)
def create_project(
    body: ProjectCreate,
    session: Session = Depends(get_db),
) -> SuccessResponse[ProjectResponse]:
    """Create a new project."""
    svc = ProjectService(session)
    project = svc.create_project(
        name=body.name,
        submitter_name=body.submitter_name,
        submitter_email=body.submitter_email,
        submitter_role=body.submitter_role,
        department_id=body.department_id,
        description=body.description,
        priority=body.priority,
        deadline=body.deadline,
        preferred_start=body.preferred_start,
        preferred_end=body.preferred_end,
    )
    session.commit()
    return SuccessResponse(data=ProjectResponse.model_validate(project))


@router.get(
    "/projects",
    response_model=SuccessResponse[ProjectListResponse],
    summary="List projects",
    description="Return projects with optional filters and pagination.",
)
def list_projects(
    department_id: uuid.UUID | None = Query(default=None),
    project_status: ProjectStatus | None = Query(default=None, alias="status"),
    submitter_email: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
) -> SuccessResponse[ProjectListResponse]:
    """List projects."""
    svc = ProjectService(session)
    items, total = svc.list_projects(
        department_id=department_id,
        status=project_status,
        submitter_email=submitter_email,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse(
        data=ProjectListResponse(
            items=[ProjectResponse.model_validate(p) for p in items],
            total=total,
            limit=limit,
            offset=offset,
        )
    )


@router.get(
    "/projects/{project_id}",
    response_model=SuccessResponse[ProjectResponse],
    summary="Get project",
    description="Retrieve a project by ID.",
)
def get_project(
    project_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> SuccessResponse[ProjectResponse]:
    """Retrieve a project."""
    svc = ProjectService(session)
    project = svc.get_project(project_id)
    return SuccessResponse(data=ProjectResponse.model_validate(project))


@router.patch(
    "/projects/{project_id}",
    response_model=SuccessResponse[ProjectResponse],
    summary="Update project",
    description="Partially update a project.",
)
def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    session: Session = Depends(get_db),
) -> SuccessResponse[ProjectResponse]:
    """Update a project."""
    svc = ProjectService(session)
    project = svc.update_project(
        project_id,
        name=body.name,
        description=body.description,
        priority=body.priority,
        status=body.status,
        deadline=body.deadline,
        preferred_start=body.preferred_start,
        preferred_end=body.preferred_end,
    )
    session.commit()
    return SuccessResponse(data=ProjectResponse.model_validate(project))


# ---------------------------------------------------------------------------
# Resource requirement endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/requirements",
    response_model=SuccessResponse[RequirementResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add resource requirement",
    description="Add a resource requirement to a project.",
)
def add_requirement(
    project_id: uuid.UUID,
    body: RequirementCreate,
    session: Session = Depends(get_db),
) -> SuccessResponse[RequirementResponse]:
    """Add a resource requirement."""
    svc = ProjectService(session)
    req = svc.add_requirement(
        project_id=project_id,
        equipment_id=body.equipment_id,
        quantity_required=body.quantity_required,
        duration_minutes=body.duration_minutes,
        earliest_start=body.earliest_start,
        latest_end=body.latest_end,
        notes=body.notes,
        is_critical=body.is_critical,
    )
    session.commit()
    return SuccessResponse(data=RequirementResponse.model_validate(req))


@router.get(
    "/projects/{project_id}/requirements",
    response_model=SuccessResponse[list[RequirementResponse]],
    summary="List requirements",
    description="Return all resource requirements for a project.",
)
def list_requirements(
    project_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> SuccessResponse[list[RequirementResponse]]:
    """List resource requirements for a project."""
    svc = ProjectService(session)
    reqs = svc.list_requirements(project_id)
    return SuccessResponse(
        data=[RequirementResponse.model_validate(r) for r in reqs]
    )


@router.delete(
    "/projects/{project_id}/requirements/{requirement_id}",
    response_model=SuccessResponse[dict],
    summary="Delete requirement",
    description="Remove a resource requirement from a project.",
)
def delete_requirement(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> SuccessResponse[dict]:
    """Delete a resource requirement."""
    svc = ProjectService(session)
    svc.delete_requirement(requirement_id)
    session.commit()
    return SuccessResponse(data={"deleted": str(requirement_id)})


# ---------------------------------------------------------------------------
# Dependency endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/dependencies",
    response_model=SuccessResponse[DependencyResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add dependency",
    description="Add a DAG dependency edge between two resource requirements.",
)
def add_dependency(
    project_id: uuid.UUID,
    body: DependencyCreate,
    session: Session = Depends(get_db),
) -> SuccessResponse[DependencyResponse]:
    """Add a requirement dependency."""
    svc = ProjectService(session)
    dep = svc.add_dependency(
        project_id=project_id,
        predecessor_id=body.predecessor_id,
        successor_id=body.successor_id,
        dependency_type=body.dependency_type,
    )
    session.commit()
    return SuccessResponse(data=DependencyResponse.model_validate(dep))
