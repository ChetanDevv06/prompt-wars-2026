"""
Shared API response schema re-exports for endpoint modules.
"""

from app.api.v1.schemas.common import ErrorDetail, ErrorResponse, SuccessResponse

__all__ = ["ErrorDetail", "ErrorResponse", "SuccessResponse"]
