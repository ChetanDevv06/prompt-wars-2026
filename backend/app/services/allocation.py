"""
Service: LIAE Allocation Management & Workflow Orchestration.

Coordinates:
- Extracting domain data (projects, requirements, equipment, substitutes, commitments, history).
- Executing LIAEOptimizer CP-SAT engine.
- Persisting AllocationRun and AllocationAssignment records.
- Applying allocations to provisional holds or confirmed reservations with conflict checks.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.enums import AllocationRunType, ProjectStatus, ReservationStatus, UserRole
from app.intelligence.allocation.data_types import (
    AllocationInput,
    DependencySpec,
    EquipmentSpec,
    ExistingCommitmentSpec,
    ProjectSpec,
    RequirementSpec,
    SubstituteSpec,
)
from app.intelligence.allocation.solver import LIAEOptimizer
from app.models.allocation import AllocationAssignment, AllocationRun
from app.models.project import Project
from app.models.reservation import Reservation, ReservationHistory
from app.repositories.allocation import AllocationRepository
from app.repositories.equipment import EquipmentCompatibilityRepository, EquipmentRepository
from app.repositories.project import ProjectRepository, RequirementRepository
from app.repositories.reservation import ReservationRepository


class AllocationService:
    """Application service for LIAE optimization workflows."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._alloc_repo = AllocationRepository(session)
        self._project_repo = ProjectRepository(session)
        self._req_repo = RequirementRepository(session)
        self._equip_repo = EquipmentRepository(session)
        self._compat_repo = EquipmentCompatibilityRepository(session)
        self._res_repo = ReservationRepository(session)

    # ------------------------------------------------------------------
    # Optimization Workflows
    # ------------------------------------------------------------------

    def run_immediate_allocation(
        self,
        *,
        project_id: uuid.UUID,
        horizon_start: datetime,
        horizon_end: datetime,
        solver_time_limit: float = 10.0,
    ) -> AllocationRun:
        """
        Run immediate allocation for a single project's resource requirements.
        """
        project = self._project_repo.get_by_id_with_requirements(project_id)
        if project is None:
            raise NotFoundError(f"Project '{project_id}' not found.")
        if not project.resource_requirements:
            raise ValidationError(
                f"Project '{project_id}' has no resource requirements to allocate."
            )

        return self._execute_solver_pipeline(
            projects=[project],
            run_type=AllocationRunType.IMMEDIATE,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            solver_time_limit=solver_time_limit,
        )

    def run_batch_allocation(
        self,
        *,
        project_ids: list[uuid.UUID] | None = None,
        horizon_start: datetime,
        horizon_end: datetime,
        solver_time_limit: float = 15.0,
    ) -> AllocationRun:
        """
        Run batch allocation across multiple competing projects.
        """
        if project_ids:
            projects: list[Project] = []
            for pid in project_ids:
                p = self._project_repo.get_by_id_with_requirements(pid)
                if p and p.resource_requirements:
                    projects.append(p)
            if not projects:
                raise ValidationError("None of the specified projects exist or have requirements.")
        else:
            # Batch allocate for all active / draft projects
            all_projects, _ = self._project_repo.list_all(limit=100)
            projects = [
                p
                for p in all_projects
                if p.status
                in (
                    ProjectStatus.DRAFT,
                    ProjectStatus.ACTIVE,
                    ProjectStatus.DRAFT.value,
                    ProjectStatus.ACTIVE.value,
                )
            ]
            # Eager load requirements
            loaded_projects = []
            for p in projects:
                p_loaded = self._project_repo.get_by_id_with_requirements(p.id)
                if p_loaded and p_loaded.resource_requirements:
                    loaded_projects.append(p_loaded)
            projects = loaded_projects

        if not projects:
            raise ValidationError(
                "No eligible projects with resource requirements found for batch allocation."
            )

        return self._execute_solver_pipeline(
            projects=projects,
            run_type=AllocationRunType.BATCH,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            solver_time_limit=solver_time_limit,
        )

    # ------------------------------------------------------------------
    # Apply Allocation as Reservations
    # ------------------------------------------------------------------

    def apply_allocation(
        self,
        run_id: uuid.UUID,
        *,
        as_status: ReservationStatus = ReservationStatus.PROVISIONALLY_HELD,
        hold_minutes: int = 60,
        approved_by: str | None = None,
    ) -> list[Reservation]:
        """
        Convert satisfied allocation assignments into actual Reservation records.

        Guarantees:
        - Re-validates against concurrent double-booking conflicts before confirming.
        - Existing confirmed reservations are protected.
        - Transactional safety: rolls back if any conflict arises.
        """
        run = self._alloc_repo.get_by_id_with_assignments(run_id)
        if run is None:
            raise NotFoundError(f"Allocation run '{run_id}' not found.")

        created_reservations: list[Reservation] = []
        now = datetime.now(UTC)

        for assign in run.assignments:
            if (
                not assign.is_satisfied
                or not assign.equipment_id
                or not assign.assigned_start
                or not assign.assigned_end
            ):
                continue

            # Skip if already converted
            if assign.reservation_id is not None:
                continue

            # Re-validate no overlap exists before persisting (conflict protection)
            conflicts = self._res_repo.find_conflicting_confirmed(
                equipment_id=assign.equipment_id,
                starts_at=assign.assigned_start,
                ends_at=assign.assigned_end,
            )
            if conflicts:
                conflicting_ids = [str(c.id) for c in conflicts]
                raise ConflictError(
                    f"Concurrent booking conflict: Equipment '{assign.equipment_id}' "
                    f"is already booked during [{assign.assigned_start} - {assign.assigned_end}]. "
                    f"Conflicting reservations: {', '.join(conflicting_ids)}"
                )

            project = self._project_repo.get_by_id(assign.project_id)
            req_name = project.submitter_name if project else "LIAE System"
            req_email = project.submitter_email if project else "liae@lablink.edu"
            req_role = project.submitter_role if project else UserRole.STUDENT

            hold_expires = (
                now + timedelta(minutes=hold_minutes)
                if as_status == ReservationStatus.PROVISIONALLY_HELD
                else None
            )

            reservation = Reservation(
                equipment_id=assign.equipment_id,
                starts_at=assign.assigned_start,
                ends_at=assign.assigned_end,
                status=as_status,
                hold_expires_at=hold_expires,
                quantity_reserved=1,
                requester_name=req_name,
                requester_email=req_email,
                requester_role=req_role,
                project_id=assign.project_id,
                requirement_id=assign.requirement_id,
                approved_by=approved_by if as_status == ReservationStatus.CONFIRMED else None,
                approved_at=now if as_status == ReservationStatus.CONFIRMED else None,
            )
            self._res_repo.create(reservation)

            # Record history
            entry = ReservationHistory(
                reservation_id=reservation.id,
                from_status=None,
                to_status=as_status,
                changed_by=approved_by or "LIAE Optimizer",
                changed_at=now,
                reason=f"Created via allocation run {run_id} ({assign.explanation})",
            )
            self._res_repo.add_history_entry(entry)

            assign.reservation_id = reservation.id
            created_reservations.append(reservation)

        self._session.flush()
        return created_reservations

    # ------------------------------------------------------------------
    # Query Run & Explanation
    # ------------------------------------------------------------------

    def get_allocation_run(self, run_id: uuid.UUID) -> AllocationRun:
        """Retrieve allocation run by ID."""
        run = self._alloc_repo.get_by_id_with_assignments(run_id)
        if run is None:
            raise NotFoundError(f"Allocation run '{run_id}' not found.")
        return run

    def list_allocation_runs(
        self, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[AllocationRun], int]:
        """List past allocation runs."""
        return self._alloc_repo.list_runs(limit=limit, offset=offset)

    # ------------------------------------------------------------------
    # Private Solver Orchestrator
    # ------------------------------------------------------------------

    def _execute_solver_pipeline(
        self,
        *,
        projects: list[Project],
        run_type: AllocationRunType,
        horizon_start: datetime,
        horizon_end: datetime,
        solver_time_limit: float,
    ) -> AllocationRun:
        if horizon_end <= horizon_start:
            raise ValidationError("Scheduling horizon end must be after horizon start.")

        # 1. Build ProjectSpecs & RequirementSpecs
        project_specs: list[ProjectSpec] = []
        needed_equipment_ids: set[uuid.UUID] = set()

        for p in projects:
            req_specs: list[RequirementSpec] = []
            for r in p.resource_requirements:
                req_specs.append(
                    RequirementSpec(
                        id=r.id,
                        project_id=p.id,
                        equipment_id=r.equipment_id,
                        duration_minutes=r.duration_minutes,
                        quantity_required=r.quantity_required,
                        earliest_start=r.earliest_start,
                        latest_end=r.latest_end,
                        deadline=p.deadline,
                        is_critical=r.is_critical,
                        notes=r.notes,
                    )
                )
                needed_equipment_ids.add(r.equipment_id)

            # Dependencies
            dep_specs: list[DependencySpec] = []
            for r in p.resource_requirements:
                for dep in r.outgoing_dependencies:
                    dep_specs.append(
                        DependencySpec(
                            predecessor_id=dep.predecessor_id,
                            successor_id=dep.successor_id,
                            dependency_type=dep.dependency_type,
                        )
                    )

            project_specs.append(
                ProjectSpec(
                    id=p.id,
                    name=p.name,
                    priority=p.priority,
                    deadline=p.deadline,
                    preferred_start=p.preferred_start,
                    preferred_end=p.preferred_end,
                    department_id=p.department_id,
                    submitter_name=p.submitter_name,
                    submitter_email=p.submitter_email,
                    submitter_role=p.submitter_role,
                    requirements=req_specs,
                    dependencies=dep_specs,
                )
            )

        # 2. Gather candidate substitutes
        substitute_specs: list[SubstituteSpec] = []
        all_relevant_equip_ids = set(needed_equipment_ids)

        for eq_id in needed_equipment_ids:
            alts = self._compat_repo.find_alternatives(eq_id)
            for alt in alts:
                substitute_specs.append(SubstituteSpec(primary_id=eq_id, compatible_id=alt.id))
                all_relevant_equip_ids.add(alt.id)

        # 3. Gather Equipment Specs
        equipment_specs: list[EquipmentSpec] = []
        for eq_id in all_relevant_equip_ids:
            eq = self._equip_repo.get_by_id(eq_id)
            if eq:
                eq_status_val = eq.status.value if hasattr(eq.status, "value") else str(eq.status)
                equipment_specs.append(
                    EquipmentSpec(
                        id=eq.id,
                        name=eq.name,
                        laboratory_id=eq.laboratory_id,
                        quantity=eq.quantity,
                        is_bookable=eq.is_bookable,
                        status=eq_status_val,
                    )
                )

        # 4. Gather Existing Commitments (Confirmed reservations + Maintenance windows)
        commitment_specs: list[ExistingCommitmentSpec] = []
        for eq_id in all_relevant_equip_ids:
            # Existing confirmed reservations
            res_items, _ = self._res_repo.list_all(
                equipment_id=eq_id,
                from_dt=horizon_start,
                to_dt=horizon_end,
                limit=200,
            )
            for res in res_items:
                res_status_val = res.status.value if hasattr(res.status, "value") else str(res.status)
                if res_status_val in (
                    ReservationStatus.CONFIRMED.value,
                    ReservationStatus.PROVISIONALLY_HELD.value,
                ):
                    commitment_specs.append(
                        ExistingCommitmentSpec(
                            id=res.id,
                            equipment_id=res.equipment_id,
                            starts_at=res.starts_at,
                            ends_at=res.ends_at,
                            quantity=res.quantity_reserved,
                            commitment_type=f"reservation_{res_status_val}",
                        )
                    )

            # Maintenance windows
            windows = self._equip_repo.get_active_maintenance_windows(eq_id, after=horizon_start)
            for w in windows:
                commitment_specs.append(
                    ExistingCommitmentSpec(
                        id=w.id,
                        equipment_id=w.equipment_id,
                        starts_at=w.starts_at,
                        ends_at=w.ends_at,
                        quantity=1,
                        commitment_type="maintenance",
                    )
                )

        # 5. Gather Historical Data for Fairness
        historical_records = self._alloc_repo.get_historical_usage()

        # 6. Package Input & Run Solver
        alloc_input = AllocationInput(
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            projects=project_specs,
            equipment=equipment_specs,
            substitutes=substitute_specs,
            commitments=commitment_specs,
            historical_usage=historical_records,
            solver_time_limit_seconds=solver_time_limit,
            enable_lexicographic=True,
        )

        optimizer = LIAEOptimizer(alloc_input)
        solver_result = optimizer.solve()

        # 7. Persist Run & Assignments
        obj_scores = solver_result.objective_scores
        fair_metrics = solver_result.fairness_metrics
        obj_json = json.dumps(
            {
                "l1_critical_unmet": obj_scores.l1_critical_unmet,
                "l1_deadline_lateness_minutes": obj_scores.l1_deadline_lateness_minutes,
                "l2_need_weighted_points": obj_scores.l2_need_weighted_points,
                "l3_fairness_balance_score": obj_scores.l3_fairness_balance_score,
                "l4_utilization_minutes": obj_scores.l4_utilization_minutes,
                "l5_preference_deviation_minutes": obj_scores.l5_preference_deviation_minutes,
            }
        )

        fairness_json = json.dumps(
            {
                "jains_fairness_index": fair_metrics.jains_fairness_index,
                "gini_coefficient": fair_metrics.gini_coefficient,
                "department_fulfillment_rates": fair_metrics.department_fulfillment_rates,
                "historical_data_available": fair_metrics.historical_data_available,
                "notes": fair_metrics.notes,
            }
        )

        allocation_run = AllocationRun(
            run_type=run_type,
            status=solver_result.status,
            solver_status_raw=solver_result.solver_status_raw,
            solve_time_seconds=solver_result.solve_time_seconds,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            total_projects=solver_result.total_projects,
            allocated_projects=solver_result.allocated_projects,
            total_requirements=solver_result.total_requirements,
            satisfied_requirements=solver_result.satisfied_requirements,
            objective_values=obj_json,
            fairness_metrics=fairness_json,
            diagnostics=solver_result.diagnostic_message,
        )
        self._alloc_repo.create_run(allocation_run)

        for scheduled in solver_result.assignments:
            assignment_model = AllocationAssignment(
                allocation_run_id=allocation_run.id,
                project_id=scheduled.project_id,
                requirement_id=scheduled.requirement_id,
                equipment_id=scheduled.equipment_id,
                assigned_start=scheduled.assigned_start,
                assigned_end=scheduled.assigned_end,
                is_satisfied=scheduled.is_satisfied,
                is_primary_match=scheduled.is_primary_match,
                explanation=scheduled.explanation,
            )
            self._alloc_repo.create_assignment(assignment_model)

        self._session.flush()
        return allocation_run
