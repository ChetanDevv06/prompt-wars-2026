"""
Service: Reservation lifecycle management.

Implements the full reservation workflow:
  PENDING → ALLOCATED → PROVISIONALLY_HELD → CONFIRMED
                       → REJECTED | EXPIRED | CANCELLED

Critical guarantees:
- No overlapping CONFIRMED reservations for the same equipment.
- State transitions are validated against the domain state machine.
- All transitions are recorded in ReservationHistory.
- Conflict detection uses the repository for atomic overlap queries.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.enums import ApprovalStatus, ReservationStatus, UserRole
from app.domain.reservation_rules import (
    InvalidStateTransitionError,
    can_cancel,
    validate_state_transition,
)
from app.models.reservation import Reservation, ReservationHistory
from app.repositories.equipment import EquipmentRepository
from app.repositories.reservation import ReservationRepository

# Default provisional hold duration (minutes)
DEFAULT_HOLD_MINUTES = 60


class ReservationService:
    """Application service managing the full reservation lifecycle."""

    def __init__(self, session: Session) -> None:
        self._repo = ReservationRepository(session)
        self._equip_repo = EquipmentRepository(session)

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def create_reservation(
        self,
        *,
        equipment_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime,
        requester_name: str,
        requester_email: str,
        requester_role: UserRole = UserRole.STUDENT,
        quantity_reserved: int = 1,
        notes: str | None = None,
        project_id: uuid.UUID | None = None,
        requirement_id: uuid.UUID | None = None,
    ) -> Reservation:
        """
        Create a new PENDING reservation.

        Validates:
        - Equipment exists and is bookable.
        - Time window is valid.
        - Quantity does not exceed available units.
        """
        self._validate_equipment(equipment_id)
        self._validate_time_window(starts_at, ends_at)
        equip = self._equip_repo.get_by_id(equipment_id)
        assert equip is not None
        if quantity_reserved < 1:
            raise ValidationError("Quantity must be at least 1.")
        if quantity_reserved > equip.quantity:
            raise ValidationError(
                f"Requested {quantity_reserved} units but only "
                f"{equip.quantity} units exist for this equipment."
            )

        reservation = Reservation(
            equipment_id=equipment_id,
            starts_at=starts_at,
            ends_at=ends_at,
            requester_name=requester_name,
            requester_email=requester_email,
            requester_role=requester_role,
            quantity_reserved=quantity_reserved,
            notes=notes,
            project_id=project_id,
            requirement_id=requirement_id,
            status=ReservationStatus.PENDING,
        )
        self._repo.create(reservation)
        self._record_history(
            reservation=reservation,
            from_status=None,
            to_status=ReservationStatus.PENDING,
            changed_by=requester_name,
            reason="Reservation created.",
        )
        return reservation

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def allocate(
        self,
        reservation_id: uuid.UUID,
        *,
        actor: str = "system",
    ) -> Reservation:
        """Transition PENDING → ALLOCATED (allocation engine has selected this slot)."""
        return self._transition(
            reservation_id,
            to_status=ReservationStatus.ALLOCATED,
            actor=actor,
            reason="Resource allocated by matching engine.",
        )

    def place_hold(
        self,
        reservation_id: uuid.UUID,
        *,
        hold_minutes: int = DEFAULT_HOLD_MINUTES,
        actor: str = "system",
    ) -> Reservation:
        """
        Transition ALLOCATED → PROVISIONALLY_HELD.

        Checks for conflicts with existing CONFIRMED or HELD reservations
        before placing the hold.
        """
        reservation = self._get_or_raise(reservation_id)
        self._check_no_conflict(reservation)

        reservation.hold_expires_at = datetime.now(UTC) + timedelta(minutes=hold_minutes)
        return self._transition_existing(
            reservation,
            to_status=ReservationStatus.PROVISIONALLY_HELD,
            actor=actor,
            reason=f"Provisional hold placed (expires in {hold_minutes} min).",
        )

    def confirm(
        self,
        reservation_id: uuid.UUID,
        *,
        approved_by: str,
        actor: str = "system",
    ) -> Reservation:
        """
        Transition PROVISIONALLY_HELD → CONFIRMED.

        Re-validates no overlapping confirmed reservations exist before committing.
        """
        reservation = self._get_or_raise(reservation_id)

        # Re-validate availability before confirming (SRS FR-056)
        conflicts = self._repo.find_conflicting_confirmed(
            equipment_id=reservation.equipment_id,
            starts_at=reservation.starts_at,
            ends_at=reservation.ends_at,
            exclude_id=reservation_id,
        )
        if conflicts:
            conflicting_ids = [str(c.id) for c in conflicts]
            raise ConflictError(
                f"Cannot confirm reservation: overlapping confirmed/held reservations "
                f"exist: {', '.join(conflicting_ids)}"
            )

        reservation.approval_status = ApprovalStatus.APPROVED
        reservation.approved_by = approved_by
        reservation.approved_at = datetime.now(UTC)
        reservation.hold_expires_at = None  # hold no longer needed once confirmed

        return self._transition_existing(
            reservation,
            to_status=ReservationStatus.CONFIRMED,
            actor=actor,
            reason=f"Confirmed by {approved_by}.",
        )

    def reject(
        self,
        reservation_id: uuid.UUID,
        *,
        reason: str,
        actor: str = "system",
    ) -> Reservation:
        """Reject a reservation (PENDING, ALLOCATED, or PROVISIONALLY_HELD → REJECTED)."""
        reservation = self._get_or_raise(reservation_id)
        reservation.rejection_reason = reason
        reservation.approval_status = ApprovalStatus.REJECTED
        return self._transition_existing(
            reservation,
            to_status=ReservationStatus.REJECTED,
            actor=actor,
            reason=reason,
        )

    def cancel(
        self,
        reservation_id: uuid.UUID,
        *,
        actor: str,
        reason: str | None = None,
    ) -> Reservation:
        """Cancel a reservation if it is in a cancellable state."""
        reservation = self._get_or_raise(reservation_id)
        if not can_cancel(reservation.status):
            st_val = getattr(reservation.status, "value", str(reservation.status))
            raise ValidationError(f"Reservation in '{st_val}' state cannot be cancelled.")
        return self._transition_existing(
            reservation,
            to_status=ReservationStatus.CANCELLED,
            actor=actor,
            reason=reason or "Cancelled by user.",
        )

    def release(
        self,
        reservation_id: uuid.UUID,
        *,
        actor: str = "system",
        reason: str | None = None,
    ) -> Reservation:
        """Mark a CONFIRMED reservation as RELEASED (resource returned)."""
        return self._transition(
            reservation_id,
            to_status=ReservationStatus.RELEASED,
            actor=actor,
            reason=reason or "Reservation released.",
        )

    def expire_holds(self, *, as_of: datetime | None = None) -> list[Reservation]:
        """
        Expire all PROVISIONALLY_HELD reservations whose hold time has passed.

        Returns the list of reservations that were expired.
        """
        now = as_of or datetime.now(UTC)
        expired = self._repo.find_expired_holds(now)
        for reservation in expired:
            reservation.approval_status = ApprovalStatus.REJECTED
            self._transition_existing(
                reservation,
                to_status=ReservationStatus.EXPIRED,
                actor="system",
                reason="Provisional hold expired automatically.",
            )
        return expired

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_reservation(self, reservation_id: uuid.UUID) -> Reservation:
        """Retrieve a reservation or raise NotFoundError."""
        return self._get_or_raise(reservation_id)

    def get_reservation_with_history(self, reservation_id: uuid.UUID) -> Reservation:
        """Retrieve a reservation with its full status history."""
        reservation = self._repo.get_by_id_with_history(reservation_id)
        if reservation is None:
            raise NotFoundError(f"Reservation '{reservation_id}' not found.")
        return reservation

    def list_reservations(
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
        return self._repo.list_all(
            equipment_id=equipment_id,
            project_id=project_id,
            status=status,
            requester_email=requester_email,
            from_dt=from_dt,
            to_dt=to_dt,
            limit=limit,
            offset=offset,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_or_raise(self, reservation_id: uuid.UUID) -> Reservation:
        reservation = self._repo.get_by_id(reservation_id)
        if reservation is None:
            raise NotFoundError(f"Reservation '{reservation_id}' not found.")
        return reservation

    def _validate_equipment(self, equipment_id: uuid.UUID) -> None:
        equip = self._equip_repo.get_by_id(equipment_id)
        if equip is None:
            raise NotFoundError(f"Equipment '{equipment_id}' not found.")
        if not equip.is_bookable:
            raise ValidationError("Equipment is not available for booking.")

    def _validate_time_window(self, starts_at: datetime, ends_at: datetime) -> None:
        if ends_at <= starts_at:
            raise ValidationError("Reservation end time must be after start time.")

    def _check_no_conflict(self, reservation: Reservation) -> None:
        """Raise ConflictError if overlapping confirmed/held reservations exist."""
        conflicts = self._repo.find_conflicting_confirmed(
            equipment_id=reservation.equipment_id,
            starts_at=reservation.starts_at,
            ends_at=reservation.ends_at,
            exclude_id=reservation.id,
        )
        if conflicts:
            conflicting_ids = [str(c.id) for c in conflicts]
            raise ConflictError(
                f"Reservation conflicts with existing reservations: {', '.join(conflicting_ids)}"
            )

    def _transition(
        self,
        reservation_id: uuid.UUID,
        *,
        to_status: ReservationStatus,
        actor: str,
        reason: str,
    ) -> Reservation:
        reservation = self._get_or_raise(reservation_id)
        return self._transition_existing(
            reservation, to_status=to_status, actor=actor, reason=reason
        )

    def _transition_existing(
        self,
        reservation: Reservation,
        *,
        to_status: ReservationStatus,
        actor: str,
        reason: str,
    ) -> Reservation:
        try:
            validate_state_transition(reservation.status, to_status)
        except InvalidStateTransitionError as exc:
            raise ValidationError(str(exc)) from exc

        from_status = reservation.status
        reservation.status = to_status
        self._repo.update(reservation)
        self._record_history(
            reservation=reservation,
            from_status=from_status,
            to_status=to_status,
            changed_by=actor,
            reason=reason,
        )
        return reservation

    def _record_history(
        self,
        *,
        reservation: Reservation,
        from_status: ReservationStatus | None,
        to_status: ReservationStatus,
        changed_by: str,
        reason: str | None,
    ) -> None:
        entry = ReservationHistory(
            reservation_id=reservation.id,
            from_status=from_status,
            to_status=to_status,
            changed_by=changed_by,
            changed_at=datetime.now(UTC),
            reason=reason,
        )
        self._repo.add_history_entry(entry)
