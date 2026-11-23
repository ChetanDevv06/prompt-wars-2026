"""
Domain logic: reservation state-machine rules.

Pure Python — no ORM, no HTTP, no FastAPI concerns.
"""

from __future__ import annotations

from app.domain.enums import VALID_RESERVATION_TRANSITIONS, ReservationStatus


class InvalidStateTransitionError(ValueError):
    """Raised when a requested state transition is not permitted."""

    def __init__(self, from_state: ReservationStatus, to_state: ReservationStatus) -> None:
        super().__init__(
            f"Cannot transition reservation from '{from_state.value}' to '{to_state.value}'."
        )
        self.from_state = from_state
        self.to_state = to_state


def validate_state_transition(
    current: ReservationStatus | str,
    target: ReservationStatus | str,
) -> None:
    """
    Assert that a reservation state transition is valid.

    Raises InvalidStateTransitionError if the transition is not permitted.
    """
    curr = ReservationStatus(current) if isinstance(current, str) else current
    tgt = ReservationStatus(target) if isinstance(target, str) else target
    allowed = VALID_RESERVATION_TRANSITIONS.get(curr, set())
    if tgt not in allowed:
        raise InvalidStateTransitionError(curr, tgt)


def is_terminal_state(status: ReservationStatus | str) -> bool:
    """Return True if the status is a terminal (non-modifiable) state."""
    st = ReservationStatus(status) if isinstance(status, str) else status
    return not VALID_RESERVATION_TRANSITIONS.get(st)


def can_cancel(status: ReservationStatus | str) -> bool:
    """Return True if a reservation in the given status may be cancelled."""
    st = ReservationStatus(status) if isinstance(status, str) else status
    return ReservationStatus.CANCELLED in VALID_RESERVATION_TRANSITIONS.get(st, set())
