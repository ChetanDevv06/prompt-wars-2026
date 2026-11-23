"""
API endpoints: Reservation lifecycle management.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.schemas.reservation import (
    HoldRequest,
    ReservationApproval,
    ReservationCancellation,
    ReservationCreate,
    ReservationDetailResponse,
    ReservationListResponse,
    ReservationRejection,
    ReservationResponse,
)
from app.api.v1.schemas_common import SuccessResponse
from app.domain.enums import ReservationStatus
from app.infrastructure.database import get_db
from app.services.reservation import ReservationService

router = APIRouter()


@router.post(
    "/reservations",
    response_model=SuccessResponse[ReservationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create reservation",
    description="Create a new PENDING resource reservation.",
)
def create_reservation(
    body: ReservationCreate,
    session: Session = Depends(get_db),
) -> SuccessResponse[ReservationResponse]:
    """Create a reservation."""
    svc = ReservationService(session)
    res = svc.create_reservation(
        equipment_id=body.equipment_id,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        requester_name=body.requester_name,
        requester_email=body.requester_email,
        requester_role=body.requester_role,
        quantity_reserved=body.quantity_reserved,
        notes=body.notes,
        project_id=body.project_id,
        requirement_id=body.requirement_id,
    )
    session.commit()
    return SuccessResponse(data=ReservationResponse.model_validate(res))


@router.get(
    "/reservations",
    response_model=SuccessResponse[ReservationListResponse],
    summary="List reservations",
    description="Return reservations with optional filters and pagination.",
)
def list_reservations(
    equipment_id: uuid.UUID | None = Query(default=None),
    project_id: uuid.UUID | None = Query(default=None),
    res_status: ReservationStatus | None = Query(default=None, alias="status"),
    requester_email: str | None = Query(default=None),
    from_dt: datetime | None = Query(default=None),
    to_dt: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
) -> SuccessResponse[ReservationListResponse]:
    """List reservations."""
    svc = ReservationService(session)
    items, total = svc.list_reservations(
        equipment_id=equipment_id,
        project_id=project_id,
        status=res_status,
        requester_email=requester_email,
        from_dt=from_dt,
        to_dt=to_dt,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse(
        data=ReservationListResponse(
            items=[ReservationResponse.model_validate(r) for r in items],
            total=total,
            limit=limit,
            offset=offset,
        )
    )


@router.get(
    "/reservations/{reservation_id}",
    response_model=SuccessResponse[ReservationDetailResponse],
    summary="Get reservation",
    description="Retrieve a reservation by ID including its full status history.",
)
def get_reservation(
    reservation_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> SuccessResponse[ReservationDetailResponse]:
    """Retrieve a reservation with history."""
    svc = ReservationService(session)
    res = svc.get_reservation_with_history(reservation_id)
    return SuccessResponse(data=ReservationDetailResponse.model_validate(res))


@router.post(
    "/reservations/{reservation_id}/hold",
    response_model=SuccessResponse[ReservationResponse],
    summary="Place provisional hold",
    description=(
        "Transition an ALLOCATED reservation to PROVISIONALLY_HELD. "
        "Checks for conflicts before placing the hold."
    ),
)
def place_hold(
    reservation_id: uuid.UUID,
    body: HoldRequest,
    session: Session = Depends(get_db),
) -> SuccessResponse[ReservationResponse]:
    """Place a provisional hold."""
    svc = ReservationService(session)
    res = svc.place_hold(reservation_id, hold_minutes=body.hold_minutes, actor="system")
    session.commit()
    return SuccessResponse(data=ReservationResponse.model_validate(res))


@router.post(
    "/reservations/{reservation_id}/confirm",
    response_model=SuccessResponse[ReservationResponse],
    summary="Confirm reservation",
    description=(
        "Approve and confirm a PROVISIONALLY_HELD reservation. "
        "Re-validates availability before confirming."
    ),
)
def confirm_reservation(
    reservation_id: uuid.UUID,
    body: ReservationApproval,
    session: Session = Depends(get_db),
) -> SuccessResponse[ReservationResponse]:
    """Confirm a reservation."""
    svc = ReservationService(session)
    res = svc.confirm(
        reservation_id,
        approved_by=body.approved_by,
        actor=body.approved_by,
    )
    session.commit()
    return SuccessResponse(data=ReservationResponse.model_validate(res))


@router.post(
    "/reservations/{reservation_id}/reject",
    response_model=SuccessResponse[ReservationResponse],
    summary="Reject reservation",
    description="Reject a pending, allocated, or provisionally held reservation.",
)
def reject_reservation(
    reservation_id: uuid.UUID,
    body: ReservationRejection,
    session: Session = Depends(get_db),
) -> SuccessResponse[ReservationResponse]:
    """Reject a reservation."""
    svc = ReservationService(session)
    res = svc.reject(reservation_id, reason=body.reason, actor="faculty")
    session.commit()
    return SuccessResponse(data=ReservationResponse.model_validate(res))


@router.post(
    "/reservations/{reservation_id}/cancel",
    response_model=SuccessResponse[ReservationResponse],
    summary="Cancel reservation",
    description="Cancel a reservation that is in a cancellable state.",
)
def cancel_reservation(
    reservation_id: uuid.UUID,
    body: ReservationCancellation,
    session: Session = Depends(get_db),
) -> SuccessResponse[ReservationResponse]:
    """Cancel a reservation."""
    svc = ReservationService(session)
    res = svc.cancel(reservation_id, actor=body.actor, reason=body.reason)
    session.commit()
    return SuccessResponse(data=ReservationResponse.model_validate(res))


@router.post(
    "/reservations/{reservation_id}/release",
    response_model=SuccessResponse[ReservationResponse],
    summary="Release reservation",
    description="Mark a confirmed reservation as released (resource returned).",
)
def release_reservation(
    reservation_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> SuccessResponse[ReservationResponse]:
    """Release a confirmed reservation."""
    svc = ReservationService(session)
    res = svc.release(reservation_id, actor="system")
    session.commit()
    return SuccessResponse(data=ReservationResponse.model_validate(res))


@router.post(
    "/reservations/expire-holds",
    response_model=SuccessResponse[dict],
    summary="Expire stale holds",
    description="Expire all PROVISIONALLY_HELD reservations whose hold has passed.",
)
def expire_holds(
    session: Session = Depends(get_db),
) -> SuccessResponse[dict]:
    """Expire stale provisional holds."""
    svc = ReservationService(session)
    expired = svc.expire_holds()
    session.commit()
    return SuccessResponse(data={"expired_count": len(expired)})
