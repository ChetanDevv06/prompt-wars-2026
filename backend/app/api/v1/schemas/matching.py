"""
Pydantic schemas for resource-matching API responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class CandidateResultSchema(BaseModel):
    """A single equipment candidate evaluated for a requirement."""

    equipment_id: uuid.UUID
    equipment_name: str
    laboratory_id: uuid.UUID
    is_available: bool
    is_primary_match: bool
    quantity_available: int
    reasons: list[str]


class MatchResultSchema(BaseModel):
    """Full matching result for a resource requirement."""

    requirement_id: uuid.UUID | None
    equipment_id: uuid.UUID
    quantity_required: int
    duration_minutes: int
    window_start: datetime | None
    window_end: datetime | None
    candidates: list[CandidateResultSchema]
    can_be_satisfied: bool


class MatchRequest(BaseModel):
    """Request body for the resource-matching endpoint."""

    equipment_id: uuid.UUID
    quantity_required: int = 1
    duration_minutes: int
    window_start: datetime | None = None
    window_end: datetime | None = None
    requirement_id: uuid.UUID | None = None
