"""
Service: Project and resource requirement management.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.dependency_graph import DependencyCycleError, validate_no_cycle
from app.domain.enums import DependencyType, ProjectPriority, ProjectStatus, UserRole
from app.models.project import Project, ProjectResourceRequirement, RequirementDependency
from app.repositories.equipment import EquipmentRepository
from app.repositories.organisation import DepartmentRepository
from app.repositories.project import ProjectRepository, RequirementRepository


class ProjectService:
    """Application service for project lifecycle management."""

    def __init__(self, session: Session) -> None:
        self._repo = ProjectRepository(session)
        self._dept_repo = DepartmentRepository(session)
        self._req_repo = RequirementRepository(session)
        self._equip_repo = EquipmentRepository(session)

    # ------------------------------------------------------------------
    # Project CRUD
    # ------------------------------------------------------------------

    def create_project(
        self,
        *,
        name: str,
        submitter_name: str,
        submitter_email: str,
        submitter_role: UserRole = UserRole.STUDENT,
        department_id: uuid.UUID | None = None,
        description: str | None = None,
        priority: ProjectPriority = ProjectPriority.MEDIUM,
        deadline: datetime | None = None,
        preferred_start: datetime | None = None,
        preferred_end: datetime | None = None,
    ) -> Project:
        """Create a new project in DRAFT status."""
        if department_id is not None:
            dept = self._dept_repo.get_by_id(department_id)
            if dept is None:
                raise NotFoundError(f"Department '{department_id}' not found.")

        project = Project(
            name=name,
            submitter_name=submitter_name,
            submitter_email=submitter_email,
            submitter_role=submitter_role,
            department_id=department_id,
            description=description,
            priority=priority,
            deadline=deadline,
            preferred_start=preferred_start,
            preferred_end=preferred_end,
        )
        return self._repo.create(project)

    def get_project(self, project_id: uuid.UUID) -> Project:
        """Retrieve a project or raise NotFoundError."""
        project = self._repo.get_by_id(project_id)
        if project is None:
            raise NotFoundError(f"Project '{project_id}' not found.")
        return project

    def get_project_with_requirements(self, project_id: uuid.UUID) -> Project:
        """Retrieve a project with its resource requirements loaded."""
        project = self._repo.get_by_id_with_requirements(project_id)
        if project is None:
            raise NotFoundError(f"Project '{project_id}' not found.")
        return project

    def list_projects(
        self,
        *,
        department_id: uuid.UUID | None = None,
        status: ProjectStatus | None = None,
        submitter_email: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Project], int]:
        """Return (items, total_count)."""
        return self._repo.list_all(
            department_id=department_id,
            status=status,
            submitter_email=submitter_email,
            limit=limit,
            offset=offset,
        )

    def update_project(
        self,
        project_id: uuid.UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        priority: ProjectPriority | None = None,
        status: ProjectStatus | None = None,
        deadline: datetime | None = None,
        preferred_start: datetime | None = None,
        preferred_end: datetime | None = None,
    ) -> Project:
        """Partially update a project."""
        project = self.get_project(project_id)
        if project.status == ProjectStatus.CANCELLED:
            raise ValidationError("Cannot modify a cancelled project.")
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if priority is not None:
            project.priority = priority
        if status is not None:
            project.status = status
        if deadline is not None:
            project.deadline = deadline
        if preferred_start is not None:
            project.preferred_start = preferred_start
        if preferred_end is not None:
            project.preferred_end = preferred_end
        return self._repo.update(project)

    # ------------------------------------------------------------------
    # Resource requirements
    # ------------------------------------------------------------------

    def add_requirement(
        self,
        *,
        project_id: uuid.UUID,
        equipment_id: uuid.UUID,
        quantity_required: int = 1,
        duration_minutes: int,
        earliest_start: datetime | None = None,
        latest_end: datetime | None = None,
        notes: str | None = None,
        is_critical: bool = False,
    ) -> ProjectResourceRequirement:
        """Add a resource requirement to a project."""
        project = self.get_project(project_id)
        if project.status not in {ProjectStatus.DRAFT, ProjectStatus.ACTIVE}:
            raise ValidationError(
                f"Cannot add requirements to a project in '{project.status.value}' status."
            )
        equip = self._equip_repo.get_by_id(equipment_id)
        if equip is None:
            raise NotFoundError(f"Equipment '{equipment_id}' not found.")
        if quantity_required < 1:
            raise ValidationError("Quantity required must be at least 1.")
        if duration_minutes < 1:
            raise ValidationError("Duration must be at least 1 minute.")
        if earliest_start and latest_end and latest_end <= earliest_start:
            raise ValidationError("Latest end must be after earliest start.")

        req = ProjectResourceRequirement(
            project_id=project_id,
            equipment_id=equipment_id,
            quantity_required=quantity_required,
            duration_minutes=duration_minutes,
            earliest_start=earliest_start,
            latest_end=latest_end,
            notes=notes,
            is_critical=is_critical,
        )
        return self._req_repo.create(req)

    def get_requirement(self, req_id: uuid.UUID) -> ProjectResourceRequirement:
        """Retrieve a requirement or raise NotFoundError."""
        req = self._req_repo.get_by_id(req_id)
        if req is None:
            raise NotFoundError(f"Requirement '{req_id}' not found.")
        return req

    def list_requirements(self, project_id: uuid.UUID) -> list[ProjectResourceRequirement]:
        """Return all requirements for a project."""
        self.get_project(project_id)  # validate project exists
        return self._req_repo.list_for_project(project_id)

    def delete_requirement(self, req_id: uuid.UUID) -> None:
        """Remove a resource requirement from its project."""
        req = self.get_requirement(req_id)
        project = self.get_project(req.project_id)
        if project.status not in {ProjectStatus.DRAFT, ProjectStatus.ACTIVE}:
            raise ValidationError(
                f"Cannot remove requirements from a project in '{project.status.value}' status."
            )
        self._req_repo.delete(req)

    # ------------------------------------------------------------------
    # Dependency graph
    # ------------------------------------------------------------------

    def add_dependency(
        self,
        *,
        project_id: uuid.UUID,
        predecessor_id: uuid.UUID,
        successor_id: uuid.UUID,
        dependency_type: DependencyType = DependencyType.SEQUENTIAL,
    ) -> RequirementDependency:
        """
        Add a DAG dependency edge between two requirements.

        Validates that:
        - Both requirements belong to the same project.
        - The edge does not introduce a cycle.
        - The edge does not already exist.
        """
        self.get_project(project_id)
        pred = self.get_requirement(predecessor_id)
        succ = self.get_requirement(successor_id)

        if pred.project_id != project_id or succ.project_id != project_id:
            raise ValidationError("Both requirements must belong to the specified project.")
        if predecessor_id == successor_id:
            raise ValidationError("A requirement cannot depend on itself.")

        existing = self._req_repo.get_dependency(predecessor_id, successor_id)
        if existing is not None:
            raise ConflictError("A dependency between these requirements already exists.")

        # Cycle detection
        adjacency = self._req_repo.build_adjacency(project_id)
        try:
            validate_no_cycle(adjacency, predecessor_id, successor_id)
        except DependencyCycleError as exc:
            raise ValidationError(str(exc)) from exc

        dep = RequirementDependency(
            predecessor_id=predecessor_id,
            successor_id=successor_id,
            dependency_type=dependency_type,
        )
        return self._req_repo.create_dependency(dep)
