"""
LabLink — FastAPI application entry point.

Creates and configures the FastAPI application instance.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import v1_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import register_middleware

settings = get_settings()


def create_application() -> FastAPI:
    """
    Application factory.

    Creates and fully configures the FastAPI application.
    """
    configure_logging(settings.app_log_level)

    application = FastAPI(
        title="LabLink API",
        description=(
            "Intelligent Laboratory Resource Management Platform — "
            "campus-wide equipment discovery, booking, and AI-powered allocation."
        ),
        version="0.1.0",
        docs_url="/docs" if settings.app_debug else None,
        redoc_url="/redoc" if settings.app_debug else None,
        openapi_url="/openapi.json" if settings.app_debug else None,
    )

    # CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Application-level middleware
    register_middleware(application)

    # Exception handlers
    register_exception_handlers(application)

    # API routes
    application.include_router(v1_router, prefix="/api/v1")

    return application


app: FastAPI = create_application()
