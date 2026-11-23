"""
API endpoints: Department and Laboratory management.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.schemas.organisation import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
    LaboratoryCreate,
    LaboratoryResponse,
    LaboratoryUpdate,
)
from app.api.v1.schemas_common import SuccessResponse
from app.infrastructure.database import get_db
from app.services.organisation import DepartmentService, LaboratoryService

router = APIRouter()


# ---------------------------------------------------------------------------
# Department endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/departments",
    response_model=SuccessResponse[DepartmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create department",
    description="Register a new academic or research department.",
)
def create_department(
    body: DepartmentCreate,
    session: Session = Depends(get_db),
) -> SuccessResponse[DepartmentResponse]:
    """Create a new department."""
    svc = DepartmentService(session)
    dept = svc.create_department(
        name=body.name,
        code=body.code,
        description=body.description,
        contact_email=body.contact_email,
    )
    session.commit()
    return SuccessResponse(data=DepartmentResponse.model_validate(dept))


@router.get(
    "/departments",
    response_model=SuccessResponse[list[DepartmentResponse]],
    summary="List departments",
    description="Return all departments.",
)
def list_departments(
    active_only: bool = Query(default=True, description="Filter to active departments"),
    session: Session = Depends(get_db),
) -> SuccessResponse[list[DepartmentResponse]]:
    """List all departments."""
    svc = DepartmentService(session)
    depts = svc.list_departments(active_only=active_only)
    return SuccessResponse(data=[DepartmentResponse.model_validate(d) for d in depts])


@router.get(
    "/departments/{department_id}",
    response_model=SuccessResponse[DepartmentResponse],
    summary="Get department",
    description="Retrieve a department by ID.",
)
def get_department(
    department_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> SuccessResponse[DepartmentResponse]:
    """Retrieve a single department."""
    svc = DepartmentService(session)
    dept = svc.get_department(department_id)
    return SuccessResponse(data=DepartmentResponse.model_validate(dept))


@router.patch(
    "/departments/{department_id}",
    response_model=SuccessResponse[DepartmentResponse],
    summary="Update department",
    description="Partially update a department's details.",
)
def update_department(
    department_id: uuid.UUID,
    body: DepartmentUpdate,
    session: Session = Depends(get_db),
) -> SuccessResponse[DepartmentResponse]:
    """Update a department."""
    svc = DepartmentService(session)
    dept = svc.update_department(
        department_id,
        name=body.name,
        description=body.description,
        contact_email=body.contact_email,
        is_active=body.is_active,
    )
    session.commit()
    return SuccessResponse(data=DepartmentResponse.model_validate(dept))


# ---------------------------------------------------------------------------
# Laboratory endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/laboratories",
    response_model=SuccessResponse[LaboratoryResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create laboratory",
    description="Register a new laboratory within a department.",
)
def create_laboratory(
    body: LaboratoryCreate,
    session: Session = Depends(get_db),
) -> SuccessResponse[LaboratoryResponse]:
    """Create a new laboratory."""
    svc = LaboratoryService(session)
    lab = svc.create_laboratory(
        name=body.name,
        code=body.code,
        department_id=body.department_id,
        location=body.location,
        description=body.description,
        capacity=body.capacity,
    )
    session.commit()
    return SuccessResponse(data=LaboratoryResponse.model_validate(lab))


@router.get(
    "/laboratories",
    response_model=SuccessResponse[list[LaboratoryResponse]],
    summary="List laboratories",
    description="Return all laboratories, optionally filtered by department.",
)
def list_laboratories(
    department_id: uuid.UUID | None = Query(default=None),
    active_only: bool = Query(default=True),
    session: Session = Depends(get_db),
) -> SuccessResponse[list[LaboratoryResponse]]:
    """List laboratories."""
    svc = LaboratoryService(session)
    labs = svc.list_laboratories(department_id=department_id, active_only=active_only)
    return SuccessResponse(data=[LaboratoryResponse.model_validate(lab) for lab in labs])


@router.get(
    "/laboratories/{laboratory_id}",
    response_model=SuccessResponse[LaboratoryResponse],
    summary="Get laboratory",
    description="Retrieve a laboratory by ID.",
)
def get_laboratory(
    laboratory_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> SuccessResponse[LaboratoryResponse]:
    """Retrieve a single laboratory."""
    svc = LaboratoryService(session)
    lab = svc.get_laboratory(laboratory_id)
    return SuccessResponse(data=LaboratoryResponse.model_validate(lab))


@router.patch(
    "/laboratories/{laboratory_id}",
    response_model=SuccessResponse[LaboratoryResponse],
    summary="Update laboratory",
    description="Partially update a laboratory's details.",
)
def update_laboratory(
    laboratory_id: uuid.UUID,
    body: LaboratoryUpdate,
    session: Session = Depends(get_db),
) -> SuccessResponse[LaboratoryResponse]:
    """Update a laboratory."""
    svc = LaboratoryService(session)
    lab = svc.update_laboratory(
        laboratory_id,
        name=body.name,
        location=body.location,
        description=body.description,
        capacity=body.capacity,
        is_active=body.is_active,
    )
    session.commit()
    return SuccessResponse(data=LaboratoryResponse.model_validate(lab))
