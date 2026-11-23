"""
Pydantic schemas for Project and ResourceRequirement API endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import DependencyType, ProjectPriority, ProjectStatus, UserRole

# ---------------------------------------------------------------------------
# Project schemas
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    """Request schema for creating a project."""

    name: str = Field(..., min_length=1, max_length=255)
    submitter_name: str = Field(..., min_length=1, max_length=255)
    submitter_email: str = Field(..., min_length=1, max_length=255)
    submitter_role: UserRole = UserRole.STUDENT
    department_id: uuid.UUID | None = None
    description: str | None = None
    priority: ProjectPriority = ProjectPriority.MEDIUM
    deadline: datetime | None = None
    preferred_start: datetime | None = None
    preferred_end: datetime | None = None


class ProjectUpdate(BaseModel):
    """Request schema for updating a project (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    priority: ProjectPriority | None = None
    status: ProjectStatus | None = None
    deadline: datetime | None = None
    preferred_start: datetime | None = None
    preferred_end: datetime | None = None


class ProjectResponse(BaseModel):
    """Response schema for a project."""

    id: uuid.UUID
    name: str
    submitter_name: str
    submitter_email: str
    submitter_role: UserRole
    department_id: uuid.UUID | None
    description: str | None
    status: ProjectStatus
    priority: ProjectPriority
    deadline: datetime | None
    preferred_start: datetime | None
    preferred_end: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """Paginated list response for projects."""

    items: list[ProjectResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Resource requirement schemas
# ---------------------------------------------------------------------------


class RequirementCreate(BaseModel):
    """Request schema for adding a resource requirement to a project."""

    equipment_id: uuid.UUID
    quantity_required: int = Field(default=1, ge=1)
    duration_minutes: int = Field(..., ge=1)
    earliest_start: datetime | None = None
    latest_end: datetime | None = None
    notes: str | None = None
    is_critical: bool = False


class RequirementResponse(BaseModel):
    """Response schema for a resource requirement."""

    id: uuid.UUID
    project_id: uuid.UUID
    equipment_id: uuid.UUID
    quantity_required: int
    duration_minutes: int
    earliest_start: datetime | None
    latest_end: datetime | None
    notes: str | None
    is_critical: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Dependency schemas
# ---------------------------------------------------------------------------


class DependencyCreate(BaseModel):
    """Request schema for adding a dependency between requirements."""

    predecessor_id: uuid.UUID
    successor_id: uuid.UUID
    dependency_type: DependencyType = DependencyType.SEQUENTIAL


class DependencyResponse(BaseModel):
    """Response schema for a requirement dependency."""

    id: uuid.UUID
    predecessor_id: uuid.UUID
    successor_id: uuid.UUID
    dependency_type: DependencyType
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
