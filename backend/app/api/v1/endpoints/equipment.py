"""
API endpoints: Equipment management (equipment, maintenance, compatibility).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.schemas.equipment import (
    CompatibilityCreate,
    CompatibilityResponse,
    EquipmentCreate,
    EquipmentListResponse,
    EquipmentResponse,
    EquipmentUpdate,
    MaintenanceWindowCreate,
    MaintenanceWindowResponse,
)
from app.api.v1.schemas_common import SuccessResponse
from app.domain.enums import EquipmentCategory, EquipmentStatus
from app.infrastructure.database import get_db
from app.services.equipment import EquipmentService

router = APIRouter()


# ---------------------------------------------------------------------------
# Equipment CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/equipment",
    response_model=SuccessResponse[EquipmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register equipment",
    description="Register a new piece of equipment in a laboratory.",
)
def create_equipment(
    body: EquipmentCreate,
    session: Session = Depends(get_db),
) -> SuccessResponse[EquipmentResponse]:
    """Register new equipment."""
    svc = EquipmentService(session)
    equip = svc.create_equipment(
        name=body.name,
        laboratory_id=body.laboratory_id,
        category=body.category,
        model=body.model,
        manufacturer=body.manufacturer,
        serial_number=body.serial_number,
        description=body.description,
        specifications=body.specifications,
        quantity=body.quantity,
        is_bookable=body.is_bookable,
    )
    session.commit()
    return SuccessResponse(data=EquipmentResponse.model_validate(equip))


@router.get(
    "/equipment",
    response_model=SuccessResponse[EquipmentListResponse],
    summary="List equipment",
    description="Return equipment with optional filters and pagination.",
)
def list_equipment(
    laboratory_id: uuid.UUID | None = Query(default=None),
    category: EquipmentCategory | None = Query(default=None),
    status: EquipmentStatus | None = Query(default=None),
    bookable_only: bool = Query(default=False),
    search: str | None = Query(default=None, description="Search in name, model, manufacturer"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
) -> SuccessResponse[EquipmentListResponse]:
    """List equipment with filtering and pagination."""
    svc = EquipmentService(session)
    items, total = svc.list_equipment(
        laboratory_id=laboratory_id,
        category=category,
        status=status,
        bookable_only=bookable_only,
        search=search,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse(
        data=EquipmentListResponse(
            items=[EquipmentResponse.model_validate(e) for e in items],
            total=total,
            limit=limit,
            offset=offset,
        )
    )


@router.get(
    "/equipment/{equipment_id}",
    response_model=SuccessResponse[EquipmentResponse],
    summary="Get equipment",
    description="Retrieve a single piece of equipment by ID.",
)
def get_equipment(
    equipment_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> SuccessResponse[EquipmentResponse]:
    """Retrieve equipment by ID."""
    svc = EquipmentService(session)
    equip = svc.get_equipment(equipment_id)
    return SuccessResponse(data=EquipmentResponse.model_validate(equip))


@router.patch(
    "/equipment/{equipment_id}",
    response_model=SuccessResponse[EquipmentResponse],
    summary="Update equipment",
    description="Partially update equipment details or status.",
)
def update_equipment(
    equipment_id: uuid.UUID,
    body: EquipmentUpdate,
    session: Session = Depends(get_db),
) -> SuccessResponse[EquipmentResponse]:
    """Update equipment."""
    svc = EquipmentService(session)
    equip = svc.update_equipment(
        equipment_id,
        name=body.name,
        category=body.category,
        status=body.status,
        model=body.model,
        manufacturer=body.manufacturer,
        description=body.description,
        specifications=body.specifications,
        quantity=body.quantity,
        is_bookable=body.is_bookable,
    )
    session.commit()
    return SuccessResponse(data=EquipmentResponse.model_validate(equip))


# ---------------------------------------------------------------------------
# Maintenance windows
# ---------------------------------------------------------------------------


@router.post(
    "/equipment/{equipment_id}/maintenance",
    response_model=SuccessResponse[MaintenanceWindowResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add maintenance window",
    description="Schedule a maintenance / unavailability period for equipment.",
)
def add_maintenance_window(
    equipment_id: uuid.UUID,
    body: MaintenanceWindowCreate,
    session: Session = Depends(get_db),
) -> SuccessResponse[MaintenanceWindowResponse]:
    """Add a maintenance window."""
    svc = EquipmentService(session)
    window = svc.add_maintenance_window(
        equipment_id=equipment_id,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        reason=body.reason,
        is_confirmed=body.is_confirmed,
    )
    session.commit()
    return SuccessResponse(data=MaintenanceWindowResponse.model_validate(window))


@router.delete(
    "/equipment/{equipment_id}/maintenance/{window_id}",
    response_model=SuccessResponse[dict],
    summary="Delete maintenance window",
    description="Remove a scheduled maintenance window.",
)
def delete_maintenance_window(
    equipment_id: uuid.UUID,
    window_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> SuccessResponse[dict]:
    """Delete a maintenance window."""
    svc = EquipmentService(session)
    svc.delete_maintenance_window(window_id)
    session.commit()
    return SuccessResponse(data={"deleted": str(window_id)})


# ---------------------------------------------------------------------------
# Compatibility
# ---------------------------------------------------------------------------


@router.post(
    "/equipment/{equipment_id}/compatibility",
    response_model=SuccessResponse[CompatibilityResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add compatibility",
    description="Declare that another piece of equipment is a compatible substitute.",
)
def add_compatibility(
    equipment_id: uuid.UUID,
    body: CompatibilityCreate,
    session: Session = Depends(get_db),
) -> SuccessResponse[CompatibilityResponse]:
    """Add equipment compatibility."""
    svc = EquipmentService(session)
    compat = svc.add_compatibility(
        equipment_id=equipment_id,
        compatible_equipment_id=body.compatible_equipment_id,
        notes=body.notes,
    )
    session.commit()
    return SuccessResponse(data=CompatibilityResponse.model_validate(compat))
