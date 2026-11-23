"""
Schemas package for API v1.
"""

from app.api.v1.schemas.allocation import (
    AllocationExplanationResponse,
    AllocationListResponse,
    AllocationRunResponse,
    ApplyAllocationRequest,
    ApplyAllocationResponse,
    BatchAllocationRequest,
    ImmediateAllocationRequest,
    ScheduledAssignmentResponse,
)
from app.api.v1.schemas.common import ErrorDetail, ErrorResponse, SuccessResponse

__all__ = [
    "AllocationExplanationResponse",
    "AllocationListResponse",
    "AllocationRunResponse",
    "ApplyAllocationRequest",
    "ApplyAllocationResponse",
    "BatchAllocationRequest",
    "ErrorDetail",
    "ErrorResponse",
    "ImmediateAllocationRequest",
    "ScheduledAssignmentResponse",
    "SuccessResponse",
]
