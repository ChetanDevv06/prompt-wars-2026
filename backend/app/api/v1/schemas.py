"""
Shared API response schemas.

Provides consistent success and error envelope shapes
used across all v1 endpoints.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class SuccessResponse[T](BaseModel):
    """Standard success envelope."""

    success: bool = True
    data: T


class ErrorDetail(BaseModel):
    """Structured error detail."""

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Standard error envelope."""

    success: bool = False
    error: ErrorDetail
