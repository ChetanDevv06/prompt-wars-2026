"""
Centralised exception handling.

Defines domain exception classes and registers FastAPI
exception handlers that return consistent error responses.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------


class LabLinkError(Exception):
    """Base class for all LabLink domain errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(LabLinkError):
    """Resource not found."""

    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"


class ConflictError(LabLinkError):
    """Resource conflict (e.g. duplicate)."""

    status_code = status.HTTP_409_CONFLICT
    error_code = "CONFLICT"


class ValidationError(LabLinkError):
    """Business-rule validation failure."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "VALIDATION_ERROR"


class UnauthorisedError(LabLinkError):
    """Authentication required."""

    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "UNAUTHORISED"


class ForbiddenError(LabLinkError):
    """Insufficient permissions."""

    status_code = status.HTTP_403_FORBIDDEN
    error_code = "FORBIDDEN"


# ---------------------------------------------------------------------------
# Error response schema
# ---------------------------------------------------------------------------


def _error_body(error_code: str, message: str) -> dict[str, object]:
    return {
        "success": False,
        "error": {
            "code": error_code,
            "message": message,
        },
    }


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI application."""

    @app.exception_handler(LabLinkError)
    async def lablink_error_handler(
        request: Request, exc: LabLinkError
    ) -> JSONResponse:
        logger.warning(
            "domain_error",
            error_code=exc.error_code,
            message=exc.message,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.error_code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Flatten Pydantic v2 error list into a readable message
        details = "; ".join(
            f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        )
        logger.info(
            "request_validation_error",
            path=request.url.path,
            details=details,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body("REQUEST_VALIDATION_ERROR", details),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "unhandled_error",
            path=request.url.path,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                "INTERNAL_ERROR",
                "An unexpected error occurred. Please try again later.",
            ),
        )
