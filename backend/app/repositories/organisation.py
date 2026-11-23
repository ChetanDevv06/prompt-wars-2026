"""
Repository: Department and Laboratory data access.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.organisation import Department, Laboratory

# ---------------------------------------------------------------------------
# Department
# ---------------------------------------------------------------------------


class DepartmentRepository:
    """Data access layer for Department entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, dept_id: uuid.UUID) -> Department | None:
        """Retrieve a department by its primary key."""
        return self._session.get(Department, dept_id)

    def get_by_code(self, code: str) -> Department | None:
        """Retrieve a department by its unique code."""
        stmt = select(Department).where(Department.code == code.upper())
        return self._session.scalar(stmt)

    def list_all(self, *, active_only: bool = True) -> list[Department]:
        """Return all departments, optionally filtered to active ones."""
        stmt = select(Department).order_by(Department.name)
        if active_only:
            stmt = stmt.where(Department.is_active.is_(True))
        return list(self._session.scalars(stmt))

    def create(self, department: Department) -> Department:
        """Persist a new department."""
        self._session.add(department)
        self._session.flush()
        return department

    def update(self, department: Department) -> Department:
        """Flush pending changes to an existing department."""
        self._session.flush()
        return department

    def exists_by_code(self, code: str, exclude_id: uuid.UUID | None = None) -> bool:
        """Check whether a department with the given code already exists."""
        stmt = select(Department.id).where(Department.code == code.upper())
        if exclude_id is not None:
            stmt = stmt.where(Department.id != exclude_id)
        return self._session.scalar(stmt) is not None


# ---------------------------------------------------------------------------
# Laboratory
# ---------------------------------------------------------------------------


class LaboratoryRepository:
    """Data access layer for Laboratory entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, lab_id: uuid.UUID) -> Laboratory | None:
        """Retrieve a laboratory by its primary key."""
        return self._session.get(Laboratory, lab_id)

    def get_by_code(self, code: str) -> Laboratory | None:
        """Retrieve a laboratory by its unique code."""
        stmt = select(Laboratory).where(Laboratory.code == code.upper())
        return self._session.scalar(stmt)

    def list_all(
        self,
        *,
        department_id: uuid.UUID | None = None,
        active_only: bool = True,
    ) -> list[Laboratory]:
        """Return laboratories, optionally filtered by department or active status."""
        stmt = select(Laboratory).order_by(Laboratory.name)
        if active_only:
            stmt = stmt.where(Laboratory.is_active.is_(True))
        if department_id is not None:
            stmt = stmt.where(Laboratory.department_id == department_id)
        return list(self._session.scalars(stmt))

    def create(self, laboratory: Laboratory) -> Laboratory:
        """Persist a new laboratory."""
        self._session.add(laboratory)
        self._session.flush()
        return laboratory

    def update(self, laboratory: Laboratory) -> Laboratory:
        """Flush pending changes."""
        self._session.flush()
        return laboratory

    def exists_by_code(self, code: str, exclude_id: uuid.UUID | None = None) -> bool:
        """Check whether a laboratory with the given code already exists."""
        stmt = select(Laboratory.id).where(Laboratory.code == code.upper())
        if exclude_id is not None:
            stmt = stmt.where(Laboratory.id != exclude_id)
        return self._session.scalar(stmt) is not None
