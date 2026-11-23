"""
Integration tests for LIAE API endpoints:
- POST /api/v1/allocations/optimise (immediate allocation)
- POST /api/v1/allocations/batch (multi-project batch allocation)
- GET /api/v1/allocations (list historical runs)
- GET /api/v1/allocations/{id} (get run and assignments)
- GET /api/v1/allocations/{id}/explanation (explainability and diagnostic report)
- POST /api/v1/allocations/{id}/apply (apply assignments to reservations)
- Concurrent booking collision protection during apply (ConflictError)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.enums import (
    EquipmentStatus,
    ProjectPriority,
    ProjectStatus,
    ReservationStatus,
    UserRole,
)
from app.infrastructure.database import get_db
from app.models.base import Base
from app.models.equipment import Equipment
from app.models.organisation import Department, Laboratory
from app.models.project import Project, ProjectResourceRequirement
from app.models.reservation import Reservation

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def alloc_engine():
    """Create in-memory SQLite engine with all tables."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="module")
def alloc_client(alloc_engine):
    """TestClient configured with overridden get_db to in-memory SQLite."""
    session_factory = sessionmaker(
        bind=alloc_engine, autocommit=False, autoflush=False, expire_on_commit=False
    )

    def override_get_db():
        session = session_factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    with patch(
        "app.api.v1.endpoints.health.check_database_connection",
        return_value=True,
    ):
        from app.main import app

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
        app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def seeded_data(alloc_engine):
    """Seed department, lab, equipment, and projects."""
    session_factory = sessionmaker(bind=alloc_engine, expire_on_commit=False)
    session = session_factory()

    dept = Department(
        name="Biomedical Engineering",
        code="BME",
        contact_email="bme@lablink.edu",
    )
    session.add(dept)
    session.flush()

    lab = Laboratory(
        name="Microbiology Lab A",
        code="MIC-A",
        department_id=dept.id,
        location="BioSci 301",
        capacity=15,
        is_active=True,
    )
    session.add(lab)
    session.flush()

    equip1 = Equipment(
        name="Confocal Microscope Zeiss",
        laboratory_id=lab.id,
        quantity=1,
        is_bookable=True,
        status=EquipmentStatus.AVAILABLE,
    )
    equip2 = Equipment(
        name="Centrifuge 5424R",
        laboratory_id=lab.id,
        quantity=2,
        is_bookable=True,
        status=EquipmentStatus.AVAILABLE,
    )
    session.add_all([equip1, equip2])
    session.flush()

    # Project 1
    proj1 = Project(
        name="Cellular Imaging Study",
        department_id=dept.id,
        status=ProjectStatus.ACTIVE,
        priority=ProjectPriority.HIGH,
        deadline=datetime.now(UTC) + timedelta(days=7),
        submitter_name="Dr. Alice",
        submitter_email="alice@lablink.edu",
        submitter_role=UserRole.FACULTY,
    )
    session.add(proj1)
    session.flush()

    req1 = ProjectResourceRequirement(
        project_id=proj1.id,
        equipment_id=equip1.id,
        duration_minutes=90,
        quantity_required=1,
        is_critical=True,
    )
    session.add(req1)

    # Project 2
    proj2 = Project(
        name="Protein Purification",
        department_id=dept.id,
        status=ProjectStatus.ACTIVE,
        priority=ProjectPriority.MEDIUM,
        deadline=datetime.now(UTC) + timedelta(days=5),
        submitter_name="Bob Student",
        submitter_email="bob@lablink.edu",
        submitter_role=UserRole.STUDENT,
    )
    session.add(proj2)
    session.flush()

    req2 = ProjectResourceRequirement(
        project_id=proj2.id,
        equipment_id=equip2.id,
        duration_minutes=60,
        quantity_required=1,
        is_critical=False,
    )
    session.add(req2)
    session.commit()
    session.close()

    return {
        "dept_id": dept.id,
        "lab_id": lab.id,
        "equip1_id": equip1.id,
        "equip2_id": equip2.id,
        "proj1_id": proj1.id,
        "req1_id": req1.id,
        "proj2_id": proj2.id,
        "req2_id": req2.id,
    }


# ---------------------------------------------------------------------------
# Test API Workflows
# ---------------------------------------------------------------------------


class TestAllocationAPI:
    """REST API integration tests for LIAE allocation workflows."""

    def test_immediate_allocation_success(
        self, alloc_client: TestClient, seeded_data: dict
    ) -> None:
        """POST /api/v1/allocations/optimise allocates resources for a single project."""
        now = datetime.now(UTC)
        payload = {
            "project_id": str(seeded_data["proj1_id"]),
            "horizon_start": now.isoformat(),
            "horizon_end": (now + timedelta(days=2)).isoformat(),
            "solver_time_limit": 5.0,
        }

        resp = alloc_client.post("/api/v1/allocations/optimise", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]

        assert data["run_type"] == "immediate"
        assert data["status"] in ("optimal", "feasible")
        assert data["total_projects"] == 1
        assert data["allocated_projects"] == 1
        assert data["satisfied_requirements"] == 1
        assert len(data["assignments"]) == 1
        assign = data["assignments"][0]
        assert assign["is_satisfied"] is True
        assert assign["equipment_id"] == str(seeded_data["equip1_id"])
        assert assign["assigned_start"] is not None

    def test_batch_allocation_success(self, alloc_client: TestClient, seeded_data: dict) -> None:
        """POST /api/v1/allocations/batch optimizes across all active projects."""
        now = datetime.now(UTC)
        payload = {
            "project_ids": [str(seeded_data["proj1_id"]), str(seeded_data["proj2_id"])],
            "horizon_start": now.isoformat(),
            "horizon_end": (now + timedelta(days=3)).isoformat(),
            "solver_time_limit": 5.0,
        }

        resp = alloc_client.post("/api/v1/allocations/batch", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]

        assert data["run_type"] == "batch"
        assert data["status"] in ("optimal", "feasible")
        assert data["total_projects"] == 2
        assert data["satisfied_requirements"] >= 2
        assert len(data["assignments"]) == 2

    def test_list_and_get_allocation_runs(self, alloc_client: TestClient) -> None:
        """GET /api/v1/allocations lists past runs; GET /api/v1/allocations/{id} returns details."""
        list_resp = alloc_client.get("/api/v1/allocations?limit=10&offset=0")
        assert list_resp.status_code == 200
        list_data = list_resp.json()["data"]
        assert list_data["total"] >= 1
        assert len(list_data["items"]) >= 1

        run_id = list_data["items"][0]["id"]
        get_resp = alloc_client.get(f"/api/v1/allocations/{run_id}")
        assert get_resp.status_code == 200
        run_data = get_resp.json()["data"]
        assert run_data["id"] == run_id
        assert len(run_data["assignments"]) > 0

    def test_get_allocation_explanation(self, alloc_client: TestClient) -> None:
        """GET /api/v1/allocations/{id}/explanation returns structured diagnostics."""
        list_resp = alloc_client.get("/api/v1/allocations?limit=1")
        run_id = list_resp.json()["data"]["items"][0]["id"]

        exp_resp = alloc_client.get(f"/api/v1/allocations/{run_id}/explanation")
        assert exp_resp.status_code == 200
        exp_data = exp_resp.json()["data"]

        assert exp_data["run_id"] == run_id
        assert "LIAE run" in exp_data["summary"]
        assert "objective_values" in exp_data
        assert "fairness_metrics" in exp_data
        assert len(exp_data["assignments_explanations"]) > 0
        assert "explanation" in exp_data["assignments_explanations"][0]

    def test_apply_allocation_to_reservations(
        self, alloc_client: TestClient, seeded_data: dict
    ) -> None:
        """POST /api/v1/allocations/{id}/apply commits assignments as provisional reservations."""
        now = datetime.now(UTC) + timedelta(days=10)  # Future horizon to avoid collision
        payload = {
            "project_id": str(seeded_data["proj2_id"]),
            "horizon_start": now.isoformat(),
            "horizon_end": (now + timedelta(days=1)).isoformat(),
            "solver_time_limit": 5.0,
        }
        opt_resp = alloc_client.post("/api/v1/allocations/optimise", json=payload)
        assert opt_resp.status_code == 200
        run_id = opt_resp.json()["data"]["id"]

        apply_payload = {
            "as_status": "provisionally_held",
            "hold_minutes": 120,
        }
        apply_resp = alloc_client.post(f"/api/v1/allocations/{run_id}/apply", json=apply_payload)
        assert apply_resp.status_code == 201, apply_resp.text
        apply_data = apply_resp.json()["data"]
        assert apply_data["reservations_created"] == 1
        assert len(apply_data["reservation_ids"]) == 1
        assert apply_data["status"] == "provisionally_held"

    def test_apply_allocation_conflict_protection(
        self, alloc_client: TestClient, seeded_data: dict, alloc_engine
    ) -> None:
        """Applying an allocation that collides with a confirmed booking raises 409 Conflict."""
        now = datetime.now(UTC) + timedelta(days=20)
        payload = {
            "project_id": str(seeded_data["proj1_id"]),
            "horizon_start": now.isoformat(),
            "horizon_end": (now + timedelta(days=1)).isoformat(),
            "solver_time_limit": 5.0,
        }
        opt_resp = alloc_client.post("/api/v1/allocations/optimise", json=payload)
        assert opt_resp.status_code == 200
        run_data = opt_resp.json()["data"]
        run_id = run_data["id"]
        assigned_start = datetime.fromisoformat(run_data["assignments"][0]["assigned_start"])
        assigned_end = datetime.fromisoformat(run_data["assignments"][0]["assigned_end"])

        # Inject an interfering CONFIRMED reservation into the DB directly
        session_factory = sessionmaker(bind=alloc_engine, expire_on_commit=False)
        session = session_factory()
        interfering = Reservation(
            equipment_id=seeded_data["equip1_id"],
            starts_at=assigned_start,
            ends_at=assigned_end,
            status=ReservationStatus.CONFIRMED,
            quantity_reserved=1,
            requester_name="Dr. Conflictor",
            requester_email="conflict@lablink.edu",
            requester_role=UserRole.FACULTY,
        )
        session.add(interfering)
        session.commit()
        session.close()

        # Now try to apply the allocation run — must detect the concurrent collision!
        apply_payload = {
            "as_status": "confirmed",
            "approved_by": "Approver Admin",
        }
        apply_resp = alloc_client.post(f"/api/v1/allocations/{run_id}/apply", json=apply_payload)
        assert apply_resp.status_code == 409
        err = apply_resp.json()
        assert "Concurrent booking conflict" in err["error"]["message"]
