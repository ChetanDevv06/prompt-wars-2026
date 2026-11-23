"""
ORM model registry.

Importing this package ensures all models are registered with SQLAlchemy's
declarative Base metadata, which is required for Alembic autogeneration.
"""

from app.models.base import (
    Base,
    IntegerPrimaryKeyMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.models.equipment import Equipment, EquipmentCompatibility, MaintenanceWindow
from app.models.organisation import Department, Laboratory
from app.models.project import Project, ProjectResourceRequirement, RequirementDependency
from app.models.reservation import Reservation, ReservationHistory

__all__ = [
    "Base",
    "Department",
    "Equipment",
    "EquipmentCompatibility",
    "IntegerPrimaryKeyMixin",
    "Laboratory",
    "MaintenanceWindow",
    "Project",
    "ProjectResourceRequirement",
    "RequirementDependency",
    "Reservation",
    "ReservationHistory",
    "SoftDeleteMixin",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
]
