"""
Pydantic schemas for Department and Laboratory API endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Department schemas
# ---------------------------------------------------------------------------


class DepartmentCreate(BaseModel):
    """Request schema for creating a department."""

    name: str = Field(..., min_length=1, max_length=255, examples=["Computer Science"])
    code: str = Field(..., min_length=1, max_length=20, examples=["CS"])
    description: str | None = None
    contact_email: str | None = Field(None, examples=["cs@university.edu"])

    @field_validator("code")
    @classmethod
    def uppercase_code(cls, v: str) -> str:
        """Normalise code to uppercase."""
        return v.upper().strip()


class DepartmentUpdate(BaseModel):
    """Request schema for updating a department (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    contact_email: str | None = None
    is_active: bool | None = None


class DepartmentResponse(BaseModel):
    """Response schema for a department."""

    id: uuid.UUID
    name: str
    code: str
    description: str | None
    contact_email: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Laboratory schemas
# ---------------------------------------------------------------------------


class LaboratoryCreate(BaseModel):
    """Request schema for creating a laboratory."""

    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=30)
    department_id: uuid.UUID
    location: str | None = None
    description: str | None = None
    capacity: int | None = Field(None, ge=1)

    @field_validator("code")
    @classmethod
    def uppercase_code(cls, v: str) -> str:
        return v.upper().strip()


class LaboratoryUpdate(BaseModel):
    """Request schema for updating a laboratory (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    location: str | None = None
    description: str | None = None
    capacity: int | None = Field(None, ge=1)
    is_active: bool | None = None


class LaboratoryResponse(BaseModel):
    """Response schema for a laboratory."""

    id: uuid.UUID
    name: str
    code: str
    department_id: uuid.UUID
    location: str | None
    description: str | None
    capacity: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
