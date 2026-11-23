"""
API v1 router.

Aggregates all v1 endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.equipment import router as equipment_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.matching import router as matching_router
from app.api.v1.endpoints.organisation import router as organisation_router
from app.api.v1.endpoints.project import router as project_router
from app.api.v1.endpoints.reservation import router as reservation_router

v1_router = APIRouter()

v1_router.include_router(health_router, tags=["health"])
v1_router.include_router(organisation_router, tags=["organisation"])
v1_router.include_router(equipment_router, tags=["equipment"])
v1_router.include_router(project_router, tags=["projects"])
v1_router.include_router(reservation_router, tags=["reservations"])
v1_router.include_router(matching_router, tags=["matching"])
