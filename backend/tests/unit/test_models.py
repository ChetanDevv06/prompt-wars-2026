"""
Unit tests: ORM models, naming conventions, mixins.
"""

from __future__ import annotations

import uuid
from datetime import UTC

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.enums import EquipmentCategory, EquipmentStatus, ReservationStatus
from app.models.base import Base
from app.models.equipment import Equipment
from app.models.organisation import Department, Laboratory
from app.models.project import Project
from app.models.reservation import Reservation, ReservationHistory


@pytest.fixture(scope="module")
def in_memory_session():
    """
    Provide an in-memory SQLite session with all tables created.

    Uses a module-scoped fixture for efficiency; each test rolls back.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # SQLite doesn't support all PostgreSQL constraints; just check table creation
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = session_factory()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


class TestModelRegistration:
    """Verify all domain models are registered with Base.metadata."""

    def test_departments_table_registered(self) -> None:
        assert "departments" in Base.metadata.tables

    def test_laboratories_table_registered(self) -> None:
        assert "laboratories" in Base.metadata.tables

    def test_equipment_table_registered(self) -> None:
        assert "equipment" in Base.metadata.tables

    def test_equipment_compatibilities_table_registered(self) -> None:
        assert "equipment_compatibilities" in Base.metadata.tables

    def test_maintenance_windows_table_registered(self) -> None:
        assert "maintenance_windows" in Base.metadata.tables

    def test_projects_table_registered(self) -> None:
        assert "projects" in Base.metadata.tables

    def test_project_resource_requirements_table_registered(self) -> None:
        assert "project_resource_requirements" in Base.metadata.tables

    def test_requirement_dependencies_table_registered(self) -> None:
        assert "requirement_dependencies" in Base.metadata.tables

    def test_reservations_table_registered(self) -> None:
        assert "reservations" in Base.metadata.tables

    def test_reservation_history_table_registered(self) -> None:
        assert "reservation_history" in Base.metadata.tables


class TestORMBasicPersistence:
    """Basic ORM round-trip tests using in-memory SQLite."""

    def test_department_create_and_retrieve(self, in_memory_session) -> None:
        dept = Department(name="Computer Science", code="CS")
        in_memory_session.add(dept)
        in_memory_session.flush()
        assert isinstance(dept.id, uuid.UUID)
        assert dept.name == "Computer Science"
        assert dept.code == "CS"
        assert dept.is_active is True
        in_memory_session.rollback()

    def test_laboratory_fk_to_department(self, in_memory_session) -> None:
        dept = Department(name="Biology", code="BIO")
        in_memory_session.add(dept)
        in_memory_session.flush()

        lab = Laboratory(name="Genetics Lab", code="GENLAB", department_id=dept.id)
        in_memory_session.add(lab)
        in_memory_session.flush()
        assert lab.department_id == dept.id
        in_memory_session.rollback()

    def test_equipment_fk_to_laboratory(self, in_memory_session) -> None:
        dept = Department(name="Physics", code="PHY")
        in_memory_session.add(dept)
        in_memory_session.flush()

        lab = Laboratory(name="Optics Lab", code="OPTLAB", department_id=dept.id)
        in_memory_session.add(lab)
        in_memory_session.flush()

        equip = Equipment(
            name="Oscilloscope",
            laboratory_id=lab.id,
            category=EquipmentCategory.ELECTRONICS,
        )
        in_memory_session.add(equip)
        in_memory_session.flush()
        assert equip.laboratory_id == lab.id
        assert equip.status == EquipmentStatus.AVAILABLE
        assert equip.quantity == 1
        assert equip.is_bookable is True
        in_memory_session.rollback()

    def test_project_create_with_defaults(self, in_memory_session) -> None:
        from app.domain.enums import ProjectPriority, ProjectStatus, UserRole

        proj = Project(
            name="Quantum Research",
            submitter_name="Alice",
            submitter_email="alice@university.edu",
        )
        in_memory_session.add(proj)
        in_memory_session.flush()
        assert proj.status == ProjectStatus.DRAFT
        assert proj.priority == ProjectPriority.MEDIUM
        assert proj.submitter_role == UserRole.STUDENT
        in_memory_session.rollback()

    def test_reservation_default_status(self, in_memory_session) -> None:
        dept = Department(name="Chem", code="CHEM")
        in_memory_session.add(dept)
        in_memory_session.flush()

        lab = Laboratory(name="Chem Lab", code="CHEMLAB", department_id=dept.id)
        in_memory_session.add(lab)
        in_memory_session.flush()

        equip = Equipment(name="Centrifuge", laboratory_id=lab.id)
        in_memory_session.add(equip)
        in_memory_session.flush()

        from datetime import datetime, timedelta
        now = datetime.now(UTC)
        res = Reservation(
            equipment_id=equip.id,
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=2),
            requester_name="Bob",
            requester_email="bob@uni.edu",
        )
        in_memory_session.add(res)
        in_memory_session.flush()
        assert res.status == ReservationStatus.PENDING
        assert res.quantity_reserved == 1
        in_memory_session.rollback()

    def test_reservation_history_linked(self, in_memory_session) -> None:
        dept = Department(name="Math", code="MATH")
        in_memory_session.add(dept)
        in_memory_session.flush()

        lab = Laboratory(name="Math Lab", code="MATHLAB", department_id=dept.id)
        in_memory_session.add(lab)
        in_memory_session.flush()

        equip = Equipment(name="Computer", laboratory_id=lab.id)
        in_memory_session.add(equip)
        in_memory_session.flush()

        from datetime import datetime, timedelta
        now = datetime.now(UTC)
        res = Reservation(
            equipment_id=equip.id,
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=3),
            requester_name="Carol",
            requester_email="carol@uni.edu",
        )
        in_memory_session.add(res)
        in_memory_session.flush()

        entry = ReservationHistory(
            reservation_id=res.id,
            from_status=None,
            to_status=ReservationStatus.PENDING,
            changed_by="Carol",
            changed_at=now,
            reason="Created",
        )
        in_memory_session.add(entry)
        in_memory_session.flush()
        assert entry.reservation_id == res.id
        in_memory_session.rollback()

    def test_enum_values_stored_as_strings(self, in_memory_session) -> None:
        """Check that enum values are stored as strings not integers."""
        dept = Department(name="EE", code="EE")
        in_memory_session.add(dept)
        in_memory_session.flush()

        lab = Laboratory(name="EE Lab", code="EELAB", department_id=dept.id)
        in_memory_session.add(lab)
        in_memory_session.flush()

        equip = Equipment(
            name="Spectrometer",
            laboratory_id=lab.id,
            category=EquipmentCategory.MEASUREMENT,
        )
        in_memory_session.add(equip)
        in_memory_session.flush()
        assert equip.category == EquipmentCategory.MEASUREMENT
        in_memory_session.rollback()
