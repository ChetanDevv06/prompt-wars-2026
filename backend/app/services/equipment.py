"""
Service: Equipment management (equipment, compatibility, maintenance windows).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.enums import EquipmentCategory, EquipmentStatus
from app.models.equipment import Equipment, EquipmentCompatibility, MaintenanceWindow
from app.repositories.equipment import (
    EquipmentCompatibilityRepository,
    EquipmentRepository,
    MaintenanceWindowRepository,
)
from app.repositories.organisation import LaboratoryRepository


class EquipmentService:
    """Application service for equipment management."""

    def __init__(self, session: Session) -> None:
        self._repo = EquipmentRepository(session)
        self._lab_repo = LaboratoryRepository(session)
        self._compat_repo = EquipmentCompatibilityRepository(session)
        self._maint_repo = MaintenanceWindowRepository(session)

    # ------------------------------------------------------------------
    # Equipment CRUD
    # ------------------------------------------------------------------

    def create_equipment(
        self,
        *,
        name: str,
        laboratory_id: uuid.UUID,
        category: EquipmentCategory = EquipmentCategory.OTHER,
        model: str | None = None,
        manufacturer: str | None = None,
        serial_number: str | None = None,
        description: str | None = None,
        specifications: str | None = None,
        quantity: int = 1,
        is_bookable: bool = True,
    ) -> Equipment:
        """Register a new piece of equipment in a laboratory."""
        lab = self._lab_repo.get_by_id(laboratory_id)
        if lab is None:
            raise NotFoundError(f"Laboratory '{laboratory_id}' not found.")
        if not lab.is_active:
            raise ValidationError("Cannot add equipment to an inactive laboratory.")
        if quantity < 1:
            raise ValidationError("Equipment quantity must be at least 1.")

        equip = Equipment(
            name=name,
            laboratory_id=laboratory_id,
            category=category,
            model=model,
            manufacturer=manufacturer,
            serial_number=serial_number,
            description=description,
            specifications=specifications,
            quantity=quantity,
            is_bookable=is_bookable,
        )
        return self._repo.create(equip)

    def get_equipment(self, equipment_id: uuid.UUID) -> Equipment:
        """Retrieve equipment or raise NotFoundError."""
        equip = self._repo.get_by_id(equipment_id)
        if equip is None:
            raise NotFoundError(f"Equipment '{equipment_id}' not found.")
        return equip

    def list_equipment(
        self,
        *,
        laboratory_id: uuid.UUID | None = None,
        category: EquipmentCategory | None = None,
        status: EquipmentStatus | None = None,
        bookable_only: bool = False,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Equipment], int]:
        """Return (items, total_count) with optional filters."""
        return self._repo.list_all(
            laboratory_id=laboratory_id,
            category=category,
            status=status,
            bookable_only=bookable_only,
            search=search,
            limit=limit,
            offset=offset,
        )

    def update_equipment(
        self,
        equipment_id: uuid.UUID,
        *,
        name: str | None = None,
        category: EquipmentCategory | None = None,
        status: EquipmentStatus | None = None,
        model: str | None = None,
        manufacturer: str | None = None,
        description: str | None = None,
        specifications: str | None = None,
        quantity: int | None = None,
        is_bookable: bool | None = None,
    ) -> Equipment:
        """Partially update equipment details."""
        equip = self.get_equipment(equipment_id)
        if name is not None:
            equip.name = name
        if category is not None:
            equip.category = category
        if status is not None:
            equip.status = status
        if model is not None:
            equip.model = model
        if manufacturer is not None:
            equip.manufacturer = manufacturer
        if description is not None:
            equip.description = description
        if specifications is not None:
            equip.specifications = specifications
        if quantity is not None:
            if quantity < 1:
                raise ValidationError("Equipment quantity must be at least 1.")
            equip.quantity = quantity
        if is_bookable is not None:
            equip.is_bookable = is_bookable
        return self._repo.update(equip)

    # ------------------------------------------------------------------
    # Maintenance windows
    # ------------------------------------------------------------------

    def add_maintenance_window(
        self,
        *,
        equipment_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime,
        reason: str | None = None,
        is_confirmed: bool = False,
    ) -> MaintenanceWindow:
        """Add a maintenance / unavailability window to equipment."""
        self.get_equipment(equipment_id)  # validate exists
        if ends_at <= starts_at:
            raise ValidationError("Maintenance window must end after it starts.")

        window = MaintenanceWindow(
            equipment_id=equipment_id,
            starts_at=starts_at,
            ends_at=ends_at,
            reason=reason,
            is_confirmed=is_confirmed,
        )
        return self._maint_repo.create(window)

    def delete_maintenance_window(self, window_id: uuid.UUID) -> None:
        """Remove a maintenance window."""
        window = self._maint_repo.get_by_id(window_id)
        if window is None:
            raise NotFoundError(f"Maintenance window '{window_id}' not found.")
        self._maint_repo.delete(window)

    # ------------------------------------------------------------------
    # Compatibility
    # ------------------------------------------------------------------

    def add_compatibility(
        self,
        *,
        equipment_id: uuid.UUID,
        compatible_equipment_id: uuid.UUID,
        notes: str | None = None,
    ) -> EquipmentCompatibility:
        """Declare that compatible_equipment can substitute for equipment."""
        self.get_equipment(equipment_id)
        self.get_equipment(compatible_equipment_id)
        if equipment_id == compatible_equipment_id:
            raise ValidationError("Equipment cannot be declared compatible with itself.")

        existing = self._compat_repo.get_pair(equipment_id, compatible_equipment_id)
        if existing is not None:
            raise ConflictError("Compatibility record already exists for this pair.")

        compat = EquipmentCompatibility(
            equipment_id=equipment_id,
            compatible_equipment_id=compatible_equipment_id,
            notes=notes,
        )
        return self._compat_repo.create(compat)
