"""
Repository: Project and ProjectResourceRequirement data access.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import ProjectStatus
from app.models.project import Project, ProjectResourceRequirement, RequirementDependency


class ProjectRepository:
    """Data access layer for Project entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        """Retrieve a project by primary key."""
        return self._session.get(Project, project_id)

    def get_by_id_with_requirements(self, project_id: uuid.UUID) -> Project | None:
        """Load a project with its resource requirements eagerly."""
        stmt = (
            select(Project)
            .options(selectinload(Project.resource_requirements))
            .where(Project.id == project_id)
        )
        return self._session.scalar(stmt)

    def list_all(
        self,
        *,
        department_id: uuid.UUID | None = None,
        status: ProjectStatus | None = None,
        submitter_email: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Project], int]:
        """Return (items, total_count) with optional filters."""
        stmt = select(Project)
        count_stmt = select(Project)

        if department_id is not None:
            stmt = stmt.where(Project.department_id == department_id)
            count_stmt = count_stmt.where(Project.department_id == department_id)
        if status is not None:
            stmt = stmt.where(Project.status == status.value)
            count_stmt = count_stmt.where(Project.status == status.value)
        if submitter_email is not None:
            stmt = stmt.where(Project.submitter_email == submitter_email)
            count_stmt = count_stmt.where(Project.submitter_email == submitter_email)

        total = len(list(self._session.scalars(count_stmt)))
        items = list(
            self._session.scalars(
                stmt.order_by(Project.created_at.desc()).limit(limit).offset(offset)
            )
        )
        return items, total

    def create(self, project: Project) -> Project:
        """Persist a new project."""
        self._session.add(project)
        self._session.flush()
        return project

    def update(self, project: Project) -> Project:
        """Flush pending changes."""
        self._session.flush()
        return project


class RequirementRepository:
    """Data access layer for ProjectResourceRequirement and dependency edges."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, req_id: uuid.UUID) -> ProjectResourceRequirement | None:
        """Retrieve a requirement by primary key."""
        return self._session.get(ProjectResourceRequirement, req_id)

    def list_for_project(self, project_id: uuid.UUID) -> list[ProjectResourceRequirement]:
        """Return all requirements belonging to a project."""
        stmt = (
            select(ProjectResourceRequirement)
            .where(ProjectResourceRequirement.project_id == project_id)
            .options(
                selectinload(ProjectResourceRequirement.outgoing_dependencies),
                selectinload(ProjectResourceRequirement.incoming_dependencies),
            )
        )
        return list(self._session.scalars(stmt))

    def create(self, requirement: ProjectResourceRequirement) -> ProjectResourceRequirement:
        """Persist a new requirement."""
        self._session.add(requirement)
        self._session.flush()
        return requirement

    def delete(self, requirement: ProjectResourceRequirement) -> None:
        """Remove a requirement (cascades to dependencies)."""
        self._session.delete(requirement)
        self._session.flush()

    def get_dependency(
        self, predecessor_id: uuid.UUID, successor_id: uuid.UUID
    ) -> RequirementDependency | None:
        """Fetch a specific dependency edge."""
        stmt = select(RequirementDependency).where(
            RequirementDependency.predecessor_id == predecessor_id,
            RequirementDependency.successor_id == successor_id,
        )
        return self._session.scalar(stmt)

    def create_dependency(
        self, dependency: RequirementDependency
    ) -> RequirementDependency:
        """Persist a new dependency edge."""
        self._session.add(dependency)
        self._session.flush()
        return dependency

    def build_adjacency(
        self, project_id: uuid.UUID
    ) -> dict[uuid.UUID, list[uuid.UUID]]:
        """
        Build adjacency map (predecessor → list[successor]) for a project's DAG.

        Used for cycle detection before adding new dependency edges.
        """
        reqs = self.list_for_project(project_id)
        adjacency: dict[uuid.UUID, list[uuid.UUID]] = {r.id: [] for r in reqs}
        for req in reqs:
            for dep in req.outgoing_dependencies:
                adjacency[req.id].append(dep.successor_id)
        return adjacency
