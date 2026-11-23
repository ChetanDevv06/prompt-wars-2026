"""
Repository: Equipment, EquipmentCompatibility, and MaintenanceWindow data access.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import EquipmentCategory, EquipmentStatus
from app.models.equipment import Equipment, EquipmentCompatibility, MaintenanceWindow


class EquipmentRepository:
    """Data access layer for Equipment entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, equipment_id: uuid.UUID) -> Equipment | None:
        """Retrieve equipment by primary key."""
        return self._session.get(Equipment, equipment_id)

    def get_by_id_with_relations(self, equipment_id: uuid.UUID) -> Equipment | None:
        """Load equipment with maintenance windows and compatibility info eagerly."""
        stmt = (
            select(Equipment)
            .options(
                selectinload(Equipment.maintenance_windows),
                selectinload(Equipment.compatible_as_primary),
            )
            .where(Equipment.id == equipment_id)
        )
        return self._session.scalar(stmt)

    def list_all(
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
        """
        Return (items, total_count) with optional filters.

        Supports pagination via limit/offset.
        """
        stmt = select(Equipment)
        count_stmt = select(Equipment)

        if laboratory_id is not None:
            stmt = stmt.where(Equipment.laboratory_id == laboratory_id)
            count_stmt = count_stmt.where(Equipment.laboratory_id == laboratory_id)
        if category is not None:
            stmt = stmt.where(Equipment.category == category.value)
            count_stmt = count_stmt.where(Equipment.category == category.value)
        if status is not None:
            stmt = stmt.where(Equipment.status == status.value)
            count_stmt = count_stmt.where(Equipment.status == status.value)
        if bookable_only:
            stmt = stmt.where(Equipment.is_bookable.is_(True))
            count_stmt = count_stmt.where(Equipment.is_bookable.is_(True))
        if search:
            pattern = f"%{search.lower()}%"
            search_filter = or_(
                Equipment.name.ilike(pattern),
                Equipment.model.ilike(pattern),
                Equipment.manufacturer.ilike(pattern),
                Equipment.description.ilike(pattern),
            )
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        total = len(list(self._session.scalars(count_stmt)))
        items = list(
            self._session.scalars(
                stmt.order_by(Equipment.name).limit(limit).offset(offset)
            )
        )
        return items, total

    def create(self, equipment: Equipment) -> Equipment:
        """Persist new equipment."""
        self._session.add(equipment)
        self._session.flush()
        return equipment

    def update(self, equipment: Equipment) -> Equipment:
        """Flush pending changes."""
        self._session.flush()
        return equipment

    def find_available_in_window(
        self,
        equipment_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime,
    ) -> bool:
        """
        Return True if the equipment has no CONFIRMED reservation
        overlapping the requested window and no active maintenance window.
        """
        from app.domain.enums import ReservationStatus
        from app.models.reservation import Reservation

        # Check confirmed reservations for overlap
        overlap_stmt = select(Reservation.id).where(
            and_(
                Reservation.equipment_id == equipment_id,
                Reservation.status == ReservationStatus.CONFIRMED.value,
                Reservation.starts_at < ends_at,
                Reservation.ends_at > starts_at,
            )
        )
        if self._session.scalar(overlap_stmt) is not None:
            return False

        # Check maintenance windows for overlap
        maintenance_stmt = select(MaintenanceWindow.id).where(
            and_(
                MaintenanceWindow.equipment_id == equipment_id,
                MaintenanceWindow.starts_at < ends_at,
                MaintenanceWindow.ends_at > starts_at,
            )
        )
        return self._session.scalar(maintenance_stmt) is None

    def get_active_maintenance_windows(
        self,
        equipment_id: uuid.UUID,
        after: datetime | None = None,
    ) -> list[MaintenanceWindow]:
        """Return upcoming or current maintenance windows for the equipment."""
        stmt = select(MaintenanceWindow).where(
            MaintenanceWindow.equipment_id == equipment_id
        )
        if after is not None:
            stmt = stmt.where(MaintenanceWindow.ends_at > after)
        return list(
            self._session.scalars(stmt.order_by(MaintenanceWindow.starts_at))
        )


class MaintenanceWindowRepository:
    """Data access layer for MaintenanceWindow entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, window_id: uuid.UUID) -> MaintenanceWindow | None:
        """Retrieve a maintenance window by primary key."""
        return self._session.get(MaintenanceWindow, window_id)

    def create(self, window: MaintenanceWindow) -> MaintenanceWindow:
        """Persist a new maintenance window."""
        self._session.add(window)
        self._session.flush()
        return window

    def delete(self, window: MaintenanceWindow) -> None:
        """Remove a maintenance window."""
        self._session.delete(window)
        self._session.flush()


class EquipmentCompatibilityRepository:
    """Data access layer for EquipmentCompatibility records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_alternatives(self, equipment_id: uuid.UUID) -> list[Equipment]:
        """Return equipment items that are listed as compatible with the given one."""
        stmt = (
            select(Equipment)
            .join(
                EquipmentCompatibility,
                EquipmentCompatibility.compatible_equipment_id == Equipment.id,
            )
            .where(EquipmentCompatibility.equipment_id == equipment_id)
        )
        return list(self._session.scalars(stmt))

    def create(self, compat: EquipmentCompatibility) -> EquipmentCompatibility:
        """Persist a new compatibility record."""
        self._session.add(compat)
        self._session.flush()
        return compat

    def get_pair(
        self, equipment_id: uuid.UUID, compatible_id: uuid.UUID
    ) -> EquipmentCompatibility | None:
        """Fetch the compatibility record for a specific pair."""
        stmt = select(EquipmentCompatibility).where(
            and_(
                EquipmentCompatibility.equipment_id == equipment_id,
                EquipmentCompatibility.compatible_equipment_id == compatible_id,
            )
        )
        return self._session.scalar(stmt)
