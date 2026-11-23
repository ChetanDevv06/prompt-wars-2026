"""
API v1 router.

Aggregates all v1 endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router

v1_router = APIRouter()

v1_router.include_router(health_router, tags=["health"])
