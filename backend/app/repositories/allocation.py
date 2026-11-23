"""
Repository: AllocationRun and AllocationAssignment data access.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import ReservationStatus
from app.intelligence.allocation.data_types import HistoricalUsageSpec
from app.models.allocation import AllocationAssignment, AllocationRun
from app.models.project import Project
from app.models.reservation import Reservation


class AllocationRepository:
    """Data access layer for LIAE allocation records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, run_id: uuid.UUID) -> AllocationRun | None:
        """Retrieve an allocation run by primary key."""
        return self._session.get(AllocationRun, run_id)

    def get_by_id_with_assignments(self, run_id: uuid.UUID) -> AllocationRun | None:
        """Load an allocation run with all its assignments eagerly."""
        stmt = (
            select(AllocationRun)
            .options(selectinload(AllocationRun.assignments))
            .where(AllocationRun.id == run_id)
        )
        return self._session.scalar(stmt)

    def list_runs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AllocationRun], int]:
        """Return (items, total_count) of allocation runs."""
        stmt = select(AllocationRun)
        count_stmt = select(AllocationRun)
        total = len(list(self._session.scalars(count_stmt)))
        items = list(
            self._session.scalars(
                stmt.order_by(AllocationRun.created_at.desc()).limit(limit).offset(offset)
            )
        )
        return items, total

    def create_run(self, run: AllocationRun) -> AllocationRun:
        """Persist a new allocation run."""
        self._session.add(run)
        self._session.flush()
        return run

    def create_assignment(self, assignment: AllocationAssignment) -> AllocationAssignment:
        """Persist an individual assignment."""
        self._session.add(assignment)
        self._session.flush()
        return assignment

    def get_historical_usage(self) -> list[HistoricalUsageSpec]:
        """
        Aggregate historical confirmed reservation data grouped by project department.

        Used by LIAE to enforce L3 need-aware fairness.
        """
        stmt = (
            select(
                Project.department_id,
                func.count(Reservation.id).label("confirmed_count"),
                func.sum(
                    func.extract("epoch", Reservation.ends_at - Reservation.starts_at) / 3600.0
                ).label("total_hours"),
            )
            .join(Project, Reservation.project_id == Project.id)
            .where(Reservation.status == ReservationStatus.CONFIRMED.value)
            .group_by(Project.department_id)
        )
        rows = self._session.execute(stmt).all()
        results: list[HistoricalUsageSpec] = []
        for dept_id, count, total_hours in rows:
            results.append(
                HistoricalUsageSpec(
                    department_id=dept_id,
                    confirmed_reservations_count=int(count or 0),
                    total_hours_used=float(total_hours or 0.0),
                )
            )
        return results
