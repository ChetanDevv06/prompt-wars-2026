"""
Pydantic schemas for Equipment API endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import EquipmentCategory, EquipmentStatus

# ---------------------------------------------------------------------------
# Equipment schemas
# ---------------------------------------------------------------------------


class EquipmentCreate(BaseModel):
    """Request schema for registering new equipment."""

    name: str = Field(..., min_length=1, max_length=255)
    laboratory_id: uuid.UUID
    category: EquipmentCategory = EquipmentCategory.OTHER
    model: str | None = None
    manufacturer: str | None = None
    serial_number: str | None = None
    description: str | None = None
    specifications: str | None = None
    quantity: int = Field(default=1, ge=1)
    is_bookable: bool = True


class EquipmentUpdate(BaseModel):
    """Request schema for updating equipment (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    category: EquipmentCategory | None = None
    status: EquipmentStatus | None = None
    model: str | None = None
    manufacturer: str | None = None
    description: str | None = None
    specifications: str | None = None
    quantity: int | None = Field(None, ge=1)
    is_bookable: bool | None = None


class EquipmentResponse(BaseModel):
    """Response schema for equipment."""

    id: uuid.UUID
    name: str
    laboratory_id: uuid.UUID
    category: EquipmentCategory
    status: EquipmentStatus
    model: str | None
    manufacturer: str | None
    serial_number: str | None
    description: str | None
    specifications: str | None
    quantity: int
    is_bookable: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EquipmentListResponse(BaseModel):
    """Paginated list response for equipment."""

    items: list[EquipmentResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Maintenance window schemas
# ---------------------------------------------------------------------------


class MaintenanceWindowCreate(BaseModel):
    """Request schema for adding a maintenance window."""

    starts_at: datetime
    ends_at: datetime
    reason: str | None = None
    is_confirmed: bool = False


class MaintenanceWindowResponse(BaseModel):
    """Response schema for a maintenance window."""

    id: uuid.UUID
    equipment_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    reason: str | None
    is_confirmed: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Compatibility schemas
# ---------------------------------------------------------------------------


class CompatibilityCreate(BaseModel):
    """Request schema for declaring equipment compatibility."""

    compatible_equipment_id: uuid.UUID
    notes: str | None = None


class CompatibilityResponse(BaseModel):
    """Response schema for a compatibility record."""

    id: uuid.UUID
    equipment_id: uuid.UUID
    compatible_equipment_id: uuid.UUID
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
