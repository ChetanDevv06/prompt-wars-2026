"""
Pydantic schemas for Reservation API endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import ApprovalStatus, ReservationStatus, UserRole

# ---------------------------------------------------------------------------
# Reservation schemas
# ---------------------------------------------------------------------------


class ReservationCreate(BaseModel):
    """Request schema for creating a reservation."""

    equipment_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    requester_name: str = Field(..., min_length=1, max_length=255)
    requester_email: str = Field(..., min_length=1, max_length=255)
    requester_role: UserRole = UserRole.STUDENT
    quantity_reserved: int = Field(default=1, ge=1)
    notes: str | None = None
    project_id: uuid.UUID | None = None
    requirement_id: uuid.UUID | None = None


class ReservationApproval(BaseModel):
    """Request schema for confirming (approving) a reservation."""

    approved_by: str = Field(..., min_length=1, max_length=255)


class ReservationRejection(BaseModel):
    """Request schema for rejecting a reservation."""

    reason: str = Field(..., min_length=1)


class ReservationCancellation(BaseModel):
    """Request schema for cancelling a reservation."""

    actor: str = Field(..., min_length=1, max_length=255)
    reason: str | None = None


class HoldRequest(BaseModel):
    """Request schema for placing a provisional hold."""

    hold_minutes: int = Field(default=60, ge=1, le=10080)  # max 1 week


class ReservationHistoryResponse(BaseModel):
    """Response schema for a single history entry."""

    id: uuid.UUID
    reservation_id: uuid.UUID
    from_status: ReservationStatus | None
    to_status: ReservationStatus
    changed_by: str | None
    changed_at: datetime
    reason: str | None

    model_config = {"from_attributes": True}


class ReservationResponse(BaseModel):
    """Response schema for a reservation."""

    id: uuid.UUID
    equipment_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    status: ReservationStatus
    hold_expires_at: datetime | None
    quantity_reserved: int
    requester_name: str
    requester_email: str
    requester_role: UserRole
    notes: str | None
    rejection_reason: str | None
    approval_status: ApprovalStatus | None
    approved_by: str | None
    approved_at: datetime | None
    project_id: uuid.UUID | None
    requirement_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReservationDetailResponse(ReservationResponse):
    """Extended response schema including full status history."""

    history: list[ReservationHistoryResponse] = []


class ReservationListResponse(BaseModel):
    """Paginated list response for reservations."""

    items: list[ReservationResponse]
    total: int
    limit: int
    offset: int
