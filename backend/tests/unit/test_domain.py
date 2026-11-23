"""
Unit tests: Domain logic (enums, state machine, dependency graph).
"""

from __future__ import annotations

import uuid

import pytest

from app.domain.dependency_graph import (
    DependencyCycleError,
    detect_cycle,
    topological_sort,
    validate_no_cycle,
)
from app.domain.enums import VALID_RESERVATION_TRANSITIONS, ReservationStatus
from app.domain.reservation_rules import (
    InvalidStateTransitionError,
    can_cancel,
    is_terminal_state,
    validate_state_transition,
)

# ---------------------------------------------------------------------------
# Enum / state machine tests
# ---------------------------------------------------------------------------


class TestReservationStateMachine:
    """Tests for the reservation state machine rules."""

    def test_valid_transition_pending_to_allocated(self) -> None:
        validate_state_transition(
            ReservationStatus.PENDING, ReservationStatus.ALLOCATED
        )

    def test_valid_transition_allocated_to_held(self) -> None:
        validate_state_transition(
            ReservationStatus.ALLOCATED, ReservationStatus.PROVISIONALLY_HELD
        )

    def test_valid_transition_held_to_confirmed(self) -> None:
        validate_state_transition(
            ReservationStatus.PROVISIONALLY_HELD, ReservationStatus.CONFIRMED
        )

    def test_valid_transition_confirmed_to_cancelled(self) -> None:
        validate_state_transition(
            ReservationStatus.CONFIRMED, ReservationStatus.CANCELLED
        )

    def test_valid_transition_confirmed_to_released(self) -> None:
        validate_state_transition(
            ReservationStatus.CONFIRMED, ReservationStatus.RELEASED
        )

    def test_invalid_transition_confirmed_to_pending(self) -> None:
        with pytest.raises(InvalidStateTransitionError):
            validate_state_transition(
                ReservationStatus.CONFIRMED, ReservationStatus.PENDING
            )

    def test_invalid_transition_rejected_to_anything(self) -> None:
        with pytest.raises(InvalidStateTransitionError):
            validate_state_transition(
                ReservationStatus.REJECTED, ReservationStatus.PENDING
            )

    def test_invalid_transition_expired_to_confirmed(self) -> None:
        with pytest.raises(InvalidStateTransitionError):
            validate_state_transition(
                ReservationStatus.EXPIRED, ReservationStatus.CONFIRMED
            )

    def test_terminal_states_have_no_transitions(self) -> None:
        terminals = [
            ReservationStatus.REJECTED,
            ReservationStatus.EXPIRED,
            ReservationStatus.RELEASED,
            ReservationStatus.CANCELLED,
        ]
        for state in terminals:
            assert is_terminal_state(state), f"{state} should be terminal"

    def test_non_terminal_states_are_not_terminal(self) -> None:
        non_terminals = [
            ReservationStatus.PENDING,
            ReservationStatus.ALLOCATED,
            ReservationStatus.PROVISIONALLY_HELD,
            ReservationStatus.CONFIRMED,
        ]
        for state in non_terminals:
            assert not is_terminal_state(state), f"{state} should not be terminal"

    def test_can_cancel_pending(self) -> None:
        assert can_cancel(ReservationStatus.PENDING)

    def test_can_cancel_held(self) -> None:
        assert can_cancel(ReservationStatus.PROVISIONALLY_HELD)

    def test_cannot_cancel_rejected(self) -> None:
        assert not can_cancel(ReservationStatus.REJECTED)

    def test_cannot_cancel_expired(self) -> None:
        assert not can_cancel(ReservationStatus.EXPIRED)

    def test_all_states_covered_in_transition_map(self) -> None:
        """Every ReservationStatus should appear as a key in the transition map."""
        for status in ReservationStatus:
            assert status in VALID_RESERVATION_TRANSITIONS, (
                f"Status {status} missing from VALID_RESERVATION_TRANSITIONS"
            )

    def test_error_message_contains_states(self) -> None:
        exc = InvalidStateTransitionError(
            ReservationStatus.EXPIRED, ReservationStatus.CONFIRMED
        )
        assert "expired" in str(exc)
        assert "confirmed" in str(exc)


# ---------------------------------------------------------------------------
# Dependency graph tests
# ---------------------------------------------------------------------------


class TestDependencyGraph:
    """Tests for the DAG dependency validation logic."""

    def _make_uuid(self) -> uuid.UUID:
        return uuid.uuid4()

    def test_detect_cycle_simple_cycle(self) -> None:
        a, b, c = self._make_uuid(), self._make_uuid(), self._make_uuid()
        # a → b → c → a
        adj: dict[uuid.UUID, list[uuid.UUID]] = {a: [b], b: [c], c: [a]}
        cycle = detect_cycle(adj, a)
        assert cycle is not None

    def test_detect_cycle_no_cycle(self) -> None:
        a, b, c = self._make_uuid(), self._make_uuid(), self._make_uuid()
        adj: dict[uuid.UUID, list[uuid.UUID]] = {a: [b], b: [c], c: []}
        cycle = detect_cycle(adj, a)
        assert cycle is None

    def test_topological_sort_linear_chain(self) -> None:
        a, b, c = self._make_uuid(), self._make_uuid(), self._make_uuid()
        adj: dict[uuid.UUID, list[uuid.UUID]] = {a: [b], b: [c], c: []}
        order = topological_sort(adj)
        assert order.index(a) < order.index(b)
        assert order.index(b) < order.index(c)

    def test_topological_sort_raises_on_cycle(self) -> None:
        a, b = self._make_uuid(), self._make_uuid()
        adj: dict[uuid.UUID, list[uuid.UUID]] = {a: [b], b: [a]}
        with pytest.raises(DependencyCycleError):
            topological_sort(adj)

    def test_validate_no_cycle_ok(self) -> None:
        a, b, c = self._make_uuid(), self._make_uuid(), self._make_uuid()
        adj: dict[uuid.UUID, list[uuid.UUID]] = {a: [b], b: [], c: []}
        # Adding c → a should be fine
        validate_no_cycle(adj, c, a)

    def test_validate_no_cycle_raises_on_cycle(self) -> None:
        a, b = self._make_uuid(), self._make_uuid()
        adj: dict[uuid.UUID, list[uuid.UUID]] = {a: [b], b: []}
        # Adding b → a creates a cycle
        with pytest.raises(DependencyCycleError):
            validate_no_cycle(adj, b, a)

    def test_cycle_error_message_contains_path(self) -> None:
        a, b = self._make_uuid(), self._make_uuid()
        exc = DependencyCycleError([a, b])
        assert str(a) in str(exc)
        assert str(b) in str(exc)

    def test_empty_graph_no_cycle(self) -> None:
        a = self._make_uuid()
        adj: dict[uuid.UUID, list[uuid.UUID]] = {a: []}
        cycle = detect_cycle(adj, a)
        assert cycle is None

    def test_diamond_dag_no_cycle(self) -> None:
        """A diamond-shaped DAG (a→b, a→c, b→d, c→d) should not trigger cycle."""
        a, b, c, d = (self._make_uuid() for _ in range(4))
        adj: dict[uuid.UUID, list[uuid.UUID]] = {
            a: [b, c], b: [d], c: [d], d: []
        }
        cycle = detect_cycle(adj, a)
        assert cycle is None
