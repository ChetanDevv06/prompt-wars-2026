"""
Repository: Reservation and ReservationHistory data access.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import ReservationStatus
from app.models.reservation import Reservation, ReservationHistory


class ReservationRepository:
    """Data access layer for Reservation entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, reservation_id: uuid.UUID) -> Reservation | None:
        """Retrieve a reservation by primary key."""
        return self._session.get(Reservation, reservation_id)

    def get_by_id_with_history(self, reservation_id: uuid.UUID) -> Reservation | None:
        """Load a reservation with its full status history."""
        stmt = (
            select(Reservation)
            .options(selectinload(Reservation.history))
            .where(Reservation.id == reservation_id)
        )
        return self._session.scalar(stmt)

    def list_all(
        self,
        *,
        equipment_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        status: ReservationStatus | None = None,
        requester_email: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Reservation], int]:
        """Return (items, total_count) with optional filters."""
        stmt = select(Reservation)
        if equipment_id is not None:
            stmt = stmt.where(Reservation.equipment_id == equipment_id)
        if project_id is not None:
            stmt = stmt.where(Reservation.project_id == project_id)
        if status is not None:
            st_val = status.value if hasattr(status, "value") else str(status)
            stmt = stmt.where(Reservation.status == st_val)
        if requester_email is not None:
            stmt = stmt.where(Reservation.requester_email == requester_email)
        if from_dt is not None:
            stmt = stmt.where(Reservation.starts_at >= from_dt)
        if to_dt is not None:
            stmt = stmt.where(Reservation.ends_at <= to_dt)

        total = len(list(self._session.scalars(stmt).all()))
        items = list(
            self._session.scalars(
                stmt.order_by(Reservation.starts_at.desc()).limit(limit).offset(offset)
            )
        )
        return items, total

    def find_conflicting_confirmed(
        self,
        equipment_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime,
        exclude_id: uuid.UUID | None = None,
    ) -> list[Reservation]:
        """
        Return CONFIRMED or PROVISIONALLY_HELD reservations that overlap
        the requested time window for the given equipment.

        Used for conflict detection before confirming a new reservation.
        """
        stmt = select(Reservation).where(
            and_(
                Reservation.equipment_id == equipment_id,
                Reservation.status.in_(
                    [
                        ReservationStatus.CONFIRMED.value,
                        ReservationStatus.PROVISIONALLY_HELD.value,
                    ]
                ),
                Reservation.starts_at < ends_at,
                Reservation.ends_at > starts_at,
            )
        )
        if exclude_id is not None:
            stmt = stmt.where(Reservation.id != exclude_id)
        return list(self._session.scalars(stmt))

    def find_expired_holds(self, as_of: datetime) -> list[Reservation]:
        """Return PROVISIONALLY_HELD reservations whose hold has expired."""
        stmt = select(Reservation).where(
            and_(
                Reservation.status == ReservationStatus.PROVISIONALLY_HELD.value,
                Reservation.hold_expires_at.is_not(None),
                Reservation.hold_expires_at <= as_of,
            )
        )
        return list(self._session.scalars(stmt))

    def create(self, reservation: Reservation) -> Reservation:
        """Persist a new reservation."""
        self._session.add(reservation)
        self._session.flush()
        return reservation

    def update(self, reservation: Reservation) -> Reservation:
        """Flush pending changes."""
        self._session.flush()
        return reservation

    def add_history_entry(self, entry: ReservationHistory) -> ReservationHistory:
        """Record a status-change audit entry."""
        self._session.add(entry)
        self._session.flush()
        return entry
