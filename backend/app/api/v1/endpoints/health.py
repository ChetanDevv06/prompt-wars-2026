"""
Health check endpoint.

GET /api/v1/health

Returns meaningful application status without exposing
secrets, internal paths, or sensitive configuration.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.infrastructure.database import check_database_connection

router = APIRouter()


class DatabaseStatus(BaseModel):
    """Database connectivity status."""

    connected: bool
    status: Literal["ok", "degraded"]


class HealthResponse(BaseModel):
    """Health check response payload."""

    status: Literal["ok", "degraded"]
    timestamp: datetime
    version: str
    environment: str
    python_version: str = Field(description="Python interpreter version")
    database: DatabaseStatus


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Application health check",
    description=(
        "Returns the current health status of the LabLink API, "
        "including database connectivity. No secrets or internal "
        "paths are included in the response."
    ),
)
def health_check() -> HealthResponse:
    """
    Perform a lightweight health check.

    Verifies database connectivity and returns aggregate status.
    Status is 'ok' when all checks pass, 'degraded' otherwise.
    """
    settings = get_settings()
    db_connected = check_database_connection()

    db_status = DatabaseStatus(
        connected=db_connected,
        status="ok" if db_connected else "degraded",
    )

    overall_status: Literal["ok", "degraded"] = (
        "ok" if db_connected else "degraded"
    )

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.now(UTC),
        version="0.1.0",
        environment=settings.app_env,
        python_version=(
            f"{sys.version_info.major}."
            f"{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        ),
        database=db_status,
    )
