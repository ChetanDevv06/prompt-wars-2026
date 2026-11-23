"""
Application-level middleware.

Registers request ID injection and structured request logging.
"""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = structlog.get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Injects a unique request ID into each request context and
    logs structured request/response information.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        # Bind request context for downstream log statements
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        logger.info(
            "request_complete",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        response.headers["X-Request-ID"] = request_id
        return response


def register_middleware(app: FastAPI) -> None:
    """Register all application middleware on the FastAPI app."""
    app.add_middleware(RequestContextMiddleware)
