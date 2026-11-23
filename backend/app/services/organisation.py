"""
Service: Organisation management (departments and laboratories).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.organisation import Department, Laboratory
from app.repositories.organisation import DepartmentRepository, LaboratoryRepository


class DepartmentService:
    """Application service for department management."""

    def __init__(self, session: Session) -> None:
        self._repo = DepartmentRepository(session)

    def create_department(
        self,
        *,
        name: str,
        code: str,
        description: str | None = None,
        contact_email: str | None = None,
    ) -> Department:
        """Create a new department. Raises ConflictError if the code is taken."""
        code_upper = code.upper()
        if self._repo.exists_by_code(code_upper):
            raise ConflictError(f"A department with code '{code_upper}' already exists.")
        dept = Department(
            name=name,
            code=code_upper,
            description=description,
            contact_email=contact_email,
        )
        return self._repo.create(dept)

    def get_department(self, dept_id: uuid.UUID) -> Department:
        """Retrieve department or raise NotFoundError."""
        dept = self._repo.get_by_id(dept_id)
        if dept is None:
            raise NotFoundError(f"Department '{dept_id}' not found.")
        return dept

    def list_departments(self, *, active_only: bool = True) -> list[Department]:
        """Return all departments."""
        return self._repo.list_all(active_only=active_only)

    def update_department(
        self,
        dept_id: uuid.UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        contact_email: str | None = None,
        is_active: bool | None = None,
    ) -> Department:
        """Partially update a department."""
        dept = self.get_department(dept_id)
        if name is not None:
            dept.name = name
        if description is not None:
            dept.description = description
        if contact_email is not None:
            dept.contact_email = contact_email
        if is_active is not None:
            dept.is_active = is_active
        return self._repo.update(dept)


class LaboratoryService:
    """Application service for laboratory management."""

    def __init__(self, session: Session) -> None:
        self._repo = LaboratoryRepository(session)
        self._dept_repo = DepartmentRepository(session)

    def create_laboratory(
        self,
        *,
        name: str,
        code: str,
        department_id: uuid.UUID,
        location: str | None = None,
        description: str | None = None,
        capacity: int | None = None,
    ) -> Laboratory:
        """Create a new laboratory. Raises ConflictError or NotFoundError as needed."""
        code_upper = code.upper()
        if self._repo.exists_by_code(code_upper):
            raise ConflictError(f"A laboratory with code '{code_upper}' already exists.")
        dept = self._dept_repo.get_by_id(department_id)
        if dept is None:
            raise NotFoundError(f"Department '{department_id}' not found.")
        lab = Laboratory(
            name=name,
            code=code_upper,
            department_id=department_id,
            location=location,
            description=description,
            capacity=capacity,
        )
        return self._repo.create(lab)

    def get_laboratory(self, lab_id: uuid.UUID) -> Laboratory:
        """Retrieve laboratory or raise NotFoundError."""
        lab = self._repo.get_by_id(lab_id)
        if lab is None:
            raise NotFoundError(f"Laboratory '{lab_id}' not found.")
        return lab

    def list_laboratories(
        self,
        *,
        department_id: uuid.UUID | None = None,
        active_only: bool = True,
    ) -> list[Laboratory]:
        """Return all laboratories, optionally filtered."""
        return self._repo.list_all(department_id=department_id, active_only=active_only)

    def update_laboratory(
        self,
        lab_id: uuid.UUID,
        *,
        name: str | None = None,
        location: str | None = None,
        description: str | None = None,
        capacity: int | None = None,
        is_active: bool | None = None,
    ) -> Laboratory:
        """Partially update a laboratory."""
        lab = self.get_laboratory(lab_id)
        if name is not None:
            lab.name = name
        if location is not None:
            lab.location = location
        if description is not None:
            lab.description = description
        if capacity is not None:
            lab.capacity = capacity
        if is_active is not None:
            lab.is_active = is_active
        return self._repo.update(lab)
