"""
Unit tests: Service layer with mocked repositories.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.enums import ReservationStatus

# ---------------------------------------------------------------------------
# Reservation service unit tests (using in-memory SQLite via service layer)
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_session():
    """Fast SQLite session for service-layer unit tests."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.models.base import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = session_factory()
    yield session
    session.rollback()
    session.close()
    Base.metadata.drop_all(engine)


def _make_dept_lab_equip(session):
    """Helper: create a dept, lab, and equipment in the given session."""
    from app.models.equipment import Equipment
    from app.models.organisation import Department, Laboratory

    dept = Department(name="Test Dept", code=f"TD{uuid.uuid4().hex[:4].upper()}")
    session.add(dept)
    session.flush()

    lab = Laboratory(
        name="Test Lab",
        code=f"TL{uuid.uuid4().hex[:4].upper()}",
        department_id=dept.id,
    )
    session.add(lab)
    session.flush()

    equip = Equipment(name="Test Equipment", laboratory_id=lab.id)
    session.add(equip)
    session.flush()
    return equip


class TestReservationServiceUnit:
    """Unit tests for the ReservationService using in-memory SQLite."""

    def test_create_reservation_success(self, sqlite_session) -> None:
        from app.services.reservation import ReservationService

        equip = _make_dept_lab_equip(sqlite_session)
        svc = ReservationService(sqlite_session)
        now = datetime.now(UTC)

        res = svc.create_reservation(
            equipment_id=equip.id,
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=2),
            requester_name="Alice",
            requester_email="alice@uni.edu",
        )
        sqlite_session.commit()
        assert res.status == ReservationStatus.PENDING
        assert res.requester_name == "Alice"

    def test_create_reservation_invalid_window_raises(self, sqlite_session) -> None:
        from app.services.reservation import ReservationService

        equip = _make_dept_lab_equip(sqlite_session)
        svc = ReservationService(sqlite_session)
        now = datetime.now(UTC)

        with pytest.raises(ValidationError, match="end time must be after"):
            svc.create_reservation(
                equipment_id=equip.id,
                starts_at=now + timedelta(hours=2),
                ends_at=now + timedelta(hours=1),
                requester_name="Alice",
                requester_email="alice@uni.edu",
            )

    def test_create_reservation_nonexistent_equipment_raises(self, sqlite_session) -> None:
        from app.services.reservation import ReservationService

        svc = ReservationService(sqlite_session)
        now = datetime.now(UTC)
        with pytest.raises(NotFoundError):
            svc.create_reservation(
                equipment_id=uuid.uuid4(),
                starts_at=now + timedelta(hours=1),
                ends_at=now + timedelta(hours=2),
                requester_name="Alice",
                requester_email="alice@uni.edu",
            )

    def test_state_transition_pending_to_allocated(self, sqlite_session) -> None:
        from app.services.reservation import ReservationService

        equip = _make_dept_lab_equip(sqlite_session)
        svc = ReservationService(sqlite_session)
        now = datetime.now(UTC)

        res = svc.create_reservation(
            equipment_id=equip.id,
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=2),
            requester_name="Bob",
            requester_email="bob@uni.edu",
        )
        sqlite_session.commit()

        allocated = svc.allocate(res.id)
        sqlite_session.commit()
        assert allocated.status == ReservationStatus.ALLOCATED

    def test_hold_then_confirm_lifecycle(self, sqlite_session) -> None:
        from app.services.reservation import ReservationService

        equip = _make_dept_lab_equip(sqlite_session)
        svc = ReservationService(sqlite_session)
        now = datetime.now(UTC)

        res = svc.create_reservation(
            equipment_id=equip.id,
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=2),
            requester_name="Carol",
            requester_email="carol@uni.edu",
        )
        sqlite_session.commit()

        svc.allocate(res.id)
        svc.place_hold(res.id, actor="system")
        confirmed = svc.confirm(res.id, approved_by="Dr. Smith")
        sqlite_session.commit()
        assert confirmed.status == ReservationStatus.CONFIRMED
        assert confirmed.approved_by == "Dr. Smith"
        assert confirmed.hold_expires_at is None

    def test_cancel_pending_reservation(self, sqlite_session) -> None:
        from app.services.reservation import ReservationService

        equip = _make_dept_lab_equip(sqlite_session)
        svc = ReservationService(sqlite_session)
        now = datetime.now(UTC)

        res = svc.create_reservation(
            equipment_id=equip.id,
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=2),
            requester_name="Dave",
            requester_email="dave@uni.edu",
        )
        sqlite_session.commit()

        cancelled = svc.cancel(res.id, actor="Dave", reason="No longer needed")
        sqlite_session.commit()
        assert cancelled.status == ReservationStatus.CANCELLED

    def test_cancel_confirmed_reservation(self, sqlite_session) -> None:
        from app.services.reservation import ReservationService

        equip = _make_dept_lab_equip(sqlite_session)
        svc = ReservationService(sqlite_session)
        now = datetime.now(UTC)

        res = svc.create_reservation(
            equipment_id=equip.id,
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=2),
            requester_name="Eve",
            requester_email="eve@uni.edu",
        )
        sqlite_session.commit()
        svc.allocate(res.id)
        svc.place_hold(res.id)
        svc.confirm(res.id, approved_by="Prof. Jones")
        cancelled = svc.cancel(res.id, actor="Eve")
        sqlite_session.commit()
        assert cancelled.status == ReservationStatus.CANCELLED

    def test_cannot_cancel_rejected_reservation(self, sqlite_session) -> None:
        from app.services.reservation import ReservationService

        equip = _make_dept_lab_equip(sqlite_session)
        svc = ReservationService(sqlite_session)
        now = datetime.now(UTC)

        res = svc.create_reservation(
            equipment_id=equip.id,
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=2),
            requester_name="Frank",
            requester_email="frank@uni.edu",
        )
        sqlite_session.commit()
        svc.reject(res.id, reason="Conflict", actor="admin")
        sqlite_session.commit()

        with pytest.raises(ValidationError, match="cannot be cancelled"):
            svc.cancel(res.id, actor="Frank")

    def test_conflict_detection_prevents_double_booking(self, sqlite_session) -> None:
        """Two reservations for the same equipment in the same window — second cannot confirm."""
        from app.services.reservation import ReservationService

        equip = _make_dept_lab_equip(sqlite_session)
        svc = ReservationService(sqlite_session)
        now = datetime.now(UTC)

        # First reservation — confirm it
        res1 = svc.create_reservation(
            equipment_id=equip.id,
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=3),
            requester_name="Greta",
            requester_email="g@uni.edu",
        )
        sqlite_session.commit()
        svc.allocate(res1.id)
        svc.place_hold(res1.id)
        svc.confirm(res1.id, approved_by="Dr. Admin")
        sqlite_session.commit()

        # Second overlapping reservation
        res2 = svc.create_reservation(
            equipment_id=equip.id,
            starts_at=now + timedelta(hours=2),
            ends_at=now + timedelta(hours=4),
            requester_name="Hans",
            requester_email="h@uni.edu",
        )
        sqlite_session.commit()
        svc.allocate(res2.id)

        # Placing a hold or confirming should raise ConflictError due to overlap with res1
        with pytest.raises(ConflictError, match="conflicts with existing"):
            svc.place_hold(res2.id)

    def test_expire_holds_marks_expired(self, sqlite_session) -> None:
        from app.services.reservation import ReservationService

        equip = _make_dept_lab_equip(sqlite_session)
        svc = ReservationService(sqlite_session)
        now = datetime.now(UTC)

        res = svc.create_reservation(
            equipment_id=equip.id,
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=2),
            requester_name="Iris",
            requester_email="iris@uni.edu",
        )
        sqlite_session.commit()
        svc.allocate(res.id)
        svc.place_hold(res.id, hold_minutes=1)
        sqlite_session.commit()

        # Simulate time passing
        future = now + timedelta(hours=1)
        expired = svc.expire_holds(as_of=future)
        sqlite_session.commit()
        assert len(expired) >= 1
        assert any(r.id == res.id for r in expired)
        assert res.status == ReservationStatus.EXPIRED

    def test_reservation_history_recorded(self, sqlite_session) -> None:
        from app.services.reservation import ReservationService

        equip = _make_dept_lab_equip(sqlite_session)
        svc = ReservationService(sqlite_session)
        now = datetime.now(UTC)

        res = svc.create_reservation(
            equipment_id=equip.id,
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=2),
            requester_name="James",
            requester_email="james@uni.edu",
        )
        sqlite_session.commit()

        full_res = svc.get_reservation_with_history(res.id)
        assert len(full_res.history) >= 1
        assert full_res.history[0].to_status == ReservationStatus.PENDING


class TestProjectServiceUnit:
    """Unit tests for ProjectService using in-memory SQLite."""

    def test_create_project_success(self, sqlite_session) -> None:
        from app.domain.enums import ProjectStatus
        from app.services.project import ProjectService

        svc = ProjectService(sqlite_session)
        project = svc.create_project(
            name="My Research Project",
            submitter_name="Alice",
            submitter_email="alice@uni.edu",
        )
        sqlite_session.commit()
        assert project.status == ProjectStatus.DRAFT
        assert project.name == "My Research Project"

    def test_add_requirement_success(self, sqlite_session) -> None:
        from app.services.project import ProjectService

        equip = _make_dept_lab_equip(sqlite_session)
        svc = ProjectService(sqlite_session)
        project = svc.create_project(
            name="Research X", submitter_name="Bob", submitter_email="bob@uni.edu"
        )
        sqlite_session.commit()

        req = svc.add_requirement(
            project_id=project.id,
            equipment_id=equip.id,
            duration_minutes=120,
            quantity_required=1,
        )
        sqlite_session.commit()
        assert req.project_id == project.id
        assert req.duration_minutes == 120

    def test_add_dependency_cycle_detection(self, sqlite_session) -> None:
        from app.services.project import ProjectService

        equip = _make_dept_lab_equip(sqlite_session)
        svc = ProjectService(sqlite_session)
        project = svc.create_project(
            name="Research Y", submitter_name="Carol", submitter_email="carol@uni.edu"
        )
        sqlite_session.commit()

        req_a = svc.add_requirement(
            project_id=project.id, equipment_id=equip.id, duration_minutes=60
        )
        req_b = svc.add_requirement(
            project_id=project.id, equipment_id=equip.id, duration_minutes=60
        )
        sqlite_session.commit()

        svc.add_dependency(
            project_id=project.id,
            predecessor_id=req_a.id,
            successor_id=req_b.id,
        )
        sqlite_session.commit()

        with pytest.raises(ValidationError, match=r"[Cc]ycle"):
            svc.add_dependency(
                project_id=project.id,
                predecessor_id=req_b.id,
                successor_id=req_a.id,
            )

    def test_add_duplicate_dependency_raises_conflict(self, sqlite_session) -> None:
        from app.services.project import ProjectService

        equip = _make_dept_lab_equip(sqlite_session)
        svc = ProjectService(sqlite_session)
        project = svc.create_project(
            name="Research Z", submitter_name="Dave", submitter_email="dave@uni.edu"
        )
        sqlite_session.commit()

        req_a = svc.add_requirement(
            project_id=project.id, equipment_id=equip.id, duration_minutes=60
        )
        req_b = svc.add_requirement(
            project_id=project.id, equipment_id=equip.id, duration_minutes=60
        )
        sqlite_session.commit()

        svc.add_dependency(
            project_id=project.id,
            predecessor_id=req_a.id,
            successor_id=req_b.id,
        )
        sqlite_session.commit()

        with pytest.raises(ConflictError):
            svc.add_dependency(
                project_id=project.id,
                predecessor_id=req_a.id,
                successor_id=req_b.id,
            )
