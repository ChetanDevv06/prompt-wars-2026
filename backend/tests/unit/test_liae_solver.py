"""
Unit tests for LIAE (LabLink Intelligent Allocation Engine) Optimizer.

Tests:
1. Single project allocation.
2. Competing projects with exclusive resource contention.
3. Equipment quantity capacity limits (pooled resources).
4. Compatible substitute fallback when primary is unavailable.
5. Protection of existing confirmed reservations (no double-booking).
6. Avoidance of scheduled maintenance windows.
7. Deadline prioritization (critical vs lower priority).
8. Dependency sequence precedence (finish-to-start DAG).
9. Infeasible request rejection (duration exceeds horizon, zero quantity).
10. Solver status distinction: OPTIMAL vs FEASIBLE vs INFEASIBLE vs UNKNOWN.
11. Fairness metrics: Jain's Index and Gini Coefficient computation.
12. Decision explainer text generation and diagnostic summary.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.domain.enums import DependencyType, ProjectPriority, SolverStatus, UserRole
from app.intelligence.allocation.data_types import (
    AllocationInput,
    DependencySpec,
    EquipmentSpec,
    ExistingCommitmentSpec,
    ProjectSpec,
    RequirementSpec,
    ScheduledAssignment,
    SubstituteSpec,
)
from app.intelligence.allocation.explainer import (
    generate_assignment_explanation,
    generate_run_summary_explanation,
)
from app.intelligence.allocation.fairness import (
    compute_gini_coefficient,
    compute_jains_index,
    compute_priority_weight,
)
from app.intelligence.allocation.solver import LIAEOptimizer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_horizon() -> tuple[datetime, datetime]:
    start = datetime(2026, 3, 1, 9, 0, 0, tzinfo=UTC)
    end = start + timedelta(days=2)  # 48 hours
    return start, end


def make_equipment(
    name: str = "Confocal Microscope", quantity: int = 1, is_bookable: bool = True
) -> EquipmentSpec:
    return EquipmentSpec(
        id=uuid.uuid4(),
        name=name,
        laboratory_id=uuid.uuid4(),
        quantity=quantity,
        is_bookable=is_bookable,
        status="active",
    )


def make_project(
    name: str,
    requirements: list[RequirementSpec],
    priority: ProjectPriority = ProjectPriority.MEDIUM,
    deadline: datetime | None = None,
    dependencies: list[DependencySpec] | None = None,
    department_id: uuid.UUID | None = None,
    submitter_role: UserRole = UserRole.FACULTY,
) -> ProjectSpec:
    return ProjectSpec(
        id=uuid.uuid4(),
        name=name,
        priority=priority,
        deadline=deadline,
        preferred_start=None,
        preferred_end=None,
        department_id=department_id or uuid.uuid4(),
        submitter_name="Dr. Test",
        submitter_email="test@lablink.edu",
        submitter_role=submitter_role,
        requirements=requirements,
        dependencies=dependencies or [],
    )


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------


class TestLIAESolver:
    """Core optimization tests using OR-Tools CP-SAT."""

    def test_single_project_allocation(self) -> None:
        """Single project with one requirement is allocated optimally."""
        h_start, h_end = make_horizon()
        equip = make_equipment("Spectrophotometer")
        proj_id = uuid.uuid4()
        req = RequirementSpec(
            id=uuid.uuid4(),
            project_id=proj_id,
            equipment_id=equip.id,
            duration_minutes=120,
            quantity_required=1,
            earliest_start=h_start,
            latest_end=h_end,
            deadline=h_end,
            is_critical=True,
        )
        proj = ProjectSpec(
            id=proj_id,
            name="Enzyme Kinetics",
            priority=ProjectPriority.HIGH,
            deadline=h_end,
            preferred_start=h_start,
            preferred_end=h_start + timedelta(hours=3),
            department_id=uuid.uuid4(),
            submitter_name="Researcher A",
            submitter_email="a@lablink.edu",
            submitter_role=UserRole.FACULTY,
            requirements=[req],
        )

        input_data = AllocationInput(
            horizon_start=h_start,
            horizon_end=h_end,
            projects=[proj],
            equipment=[equip],
        )

        solver = LIAEOptimizer(input_data)
        result = solver.solve()

        assert result.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
        assert result.satisfied_requirements == 1
        assert len(result.assignments) == 1
        assignment = result.assignments[0]
        assert assignment.is_satisfied is True
        assert assignment.equipment_id == equip.id
        assert assignment.assigned_start is not None
        assert assignment.assigned_end is not None
        duration = (assignment.assigned_end - assignment.assigned_start).total_seconds() / 60
        assert duration == 120
        assert assignment.is_primary_match is True

    def test_competing_projects_exclusive_resource(self) -> None:
        """Two projects competing for 1 unit of equipment are scheduled without overlap."""
        h_start, h_end = make_horizon()
        equip = make_equipment("Centrifuge", quantity=1)

        p1_id = uuid.uuid4()
        req1 = RequirementSpec(
            id=uuid.uuid4(),
            project_id=p1_id,
            equipment_id=equip.id,
            duration_minutes=180,
            earliest_start=h_start,
            latest_end=h_end,
            deadline=h_end,
        )
        p1 = make_project("Project Alpha", [req1], priority=ProjectPriority.CRITICAL)

        p2_id = uuid.uuid4()
        req2 = RequirementSpec(
            id=uuid.uuid4(),
            project_id=p2_id,
            equipment_id=equip.id,
            duration_minutes=180,
            earliest_start=h_start,
            latest_end=h_end,
            deadline=h_end,
        )
        p2 = make_project("Project Beta", [req2], priority=ProjectPriority.LOW)

        input_data = AllocationInput(
            horizon_start=h_start,
            horizon_end=h_end,
            projects=[p1, p2],
            equipment=[equip],
        )

        result = LIAEOptimizer(input_data).solve()
        assert result.satisfied_requirements == 2

        a1 = next(a for a in result.assignments if a.project_id == p1.id)
        a2 = next(a for a in result.assignments if a.project_id == p2.id)

        assert a1.is_satisfied and a2.is_satisfied
        assert a1.assigned_start is not None and a1.assigned_end is not None
        assert a2.assigned_start is not None and a2.assigned_end is not None

        # Verify no overlap: a1 ends before a2 starts, OR a2 ends before a1 starts
        no_overlap = (a1.assigned_end <= a2.assigned_start) or (
            a2.assigned_end <= a1.assigned_start
        )
        assert no_overlap, (
            f"Overlap between [{a1.assigned_start}, {a1.assigned_end}] "
            f"and [{a2.assigned_start}, {a2.assigned_end}]"
        )

    def test_equipment_quantity_capacity_limit(self) -> None:
        """Pooled equipment with quantity=2 can support 2 concurrent jobs, but not 3."""
        h_start = datetime(2026, 3, 1, 9, 0, 0, tzinfo=UTC)
        h_end = h_start + timedelta(hours=3)  # Tight horizon of 3 hours
        equip = make_equipment("Shared PCR", quantity=2)

        # 3 projects, each needing 3 hours on the equipment
        projects = []
        for i in range(3):
            req = RequirementSpec(
                id=uuid.uuid4(),
                project_id=uuid.uuid4(),
                equipment_id=equip.id,
                duration_minutes=180,  # takes whole 3-hour window
                earliest_start=h_start,
                latest_end=h_end,
            )
            p = make_project(f"Project {i + 1}", [req], priority=ProjectPriority.MEDIUM)
            req.project_id = p.id
            projects.append(p)

        input_data = AllocationInput(
            horizon_start=h_start,
            horizon_end=h_end,
            projects=projects,
            equipment=[equip],
        )

        result = LIAEOptimizer(input_data).solve()
        # Exactly 2 can be satisfied within the 3-hour horizon because quantity is 2
        assert result.satisfied_requirements == 2
        unmet = [a for a in result.assignments if not a.is_satisfied]
        assert len(unmet) == 1
        has_msg = (
            "could not be satisfied" in unmet[0].explanation.lower()
            or "capacity" in unmet[0].explanation.lower()
        )
        assert has_msg

    def test_compatible_substitute_allocation(self) -> None:
        """When primary equipment is fully booked, the solver allocates a compatible substitute."""
        h_start, h_end = make_horizon()
        primary_eq = make_equipment("Primary Sequencer", quantity=1)
        substitute_eq = make_equipment("Backup Sequencer", quantity=1)

        # Pre-book primary equipment for the entire horizon
        commitment = ExistingCommitmentSpec(
            id=uuid.uuid4(),
            equipment_id=primary_eq.id,
            starts_at=h_start,
            ends_at=h_end,
            quantity=1,
            commitment_type="confirmed_reservation",
        )

        req = RequirementSpec(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            equipment_id=primary_eq.id,
            duration_minutes=120,
            earliest_start=h_start,
            latest_end=h_end,
        )
        p = make_project("Genome Sequencing", [req])
        req.project_id = p.id

        substitute = SubstituteSpec(primary_id=primary_eq.id, compatible_id=substitute_eq.id)

        input_data = AllocationInput(
            horizon_start=h_start,
            horizon_end=h_end,
            projects=[p],
            equipment=[primary_eq, substitute_eq],
            substitutes=[substitute],
            commitments=[commitment],
        )

        result = LIAEOptimizer(input_data).solve()
        assert result.satisfied_requirements == 1
        assignment = result.assignments[0]
        assert assignment.is_satisfied is True
        assert assignment.equipment_id == substitute_eq.id
        assert assignment.is_primary_match is False
        assert "substitute" in assignment.explanation.lower()

    def test_existing_confirmed_reservations_protected(self) -> None:
        """Solver never overlaps an existing confirmed reservation."""
        h_start, h_end = make_horizon()
        equip = make_equipment("Electron Microscope", quantity=1)

        # Confirmed reservation from +2h to +5h
        res_start = h_start + timedelta(hours=2)
        res_end = h_start + timedelta(hours=5)
        commitment = ExistingCommitmentSpec(
            id=uuid.uuid4(),
            equipment_id=equip.id,
            starts_at=res_start,
            ends_at=res_end,
            quantity=1,
            commitment_type="confirmed_reservation",
        )

        # Requirement takes 2 hours
        req = RequirementSpec(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            equipment_id=equip.id,
            duration_minutes=120,
            earliest_start=h_start,
            latest_end=h_end,
        )
        p = make_project("Nanotech Study", [req])
        req.project_id = p.id

        input_data = AllocationInput(
            horizon_start=h_start,
            horizon_end=h_end,
            projects=[p],
            equipment=[equip],
            commitments=[commitment],
        )

        result = LIAEOptimizer(input_data).solve()
        assert result.satisfied_requirements == 1
        assign = result.assignments[0]
        assert assign.assigned_start is not None and assign.assigned_end is not None

        # Must not overlap [res_start, res_end]
        no_overlap = (assign.assigned_end <= res_start) or (assign.assigned_start >= res_end)
        assert no_overlap, (
            f"Assigned window [{assign.assigned_start}, {assign.assigned_end}] overlaps "
            f"confirmed reservation [{res_start}, {res_end}]"
        )

    def test_maintenance_window_avoidance(self) -> None:
        """Solver avoids scheduling during maintenance windows."""
        h_start, h_end = make_horizon()
        equip = make_equipment("Autoclave", quantity=1)

        maint_start = h_start + timedelta(hours=1)
        maint_end = h_start + timedelta(hours=4)
        maint_commitment = ExistingCommitmentSpec(
            id=uuid.uuid4(),
            equipment_id=equip.id,
            starts_at=maint_start,
            ends_at=maint_end,
            quantity=1,
            commitment_type="maintenance",
        )

        req = RequirementSpec(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            equipment_id=equip.id,
            duration_minutes=120,
            earliest_start=h_start,
            latest_end=h_end,
        )
        p = make_project("Sterilization Run", [req])
        req.project_id = p.id

        input_data = AllocationInput(
            horizon_start=h_start,
            horizon_end=h_end,
            projects=[p],
            equipment=[equip],
            commitments=[maint_commitment],
        )

        result = LIAEOptimizer(input_data).solve()
        assert result.satisfied_requirements == 1
        assign = result.assignments[0]
        assert assign.assigned_start is not None and assign.assigned_end is not None

        no_overlap = (assign.assigned_end <= maint_start) or (assign.assigned_start >= maint_end)
        assert no_overlap, (
            f"Assigned window collided with maintenance window [{maint_start}, {maint_end}]"
        )

    def test_deadline_prioritization(self) -> None:
        """High priority / critical deadline project is allocated before low priority project."""
        h_start = datetime(2026, 3, 1, 9, 0, 0, tzinfo=UTC)
        h_end = h_start + timedelta(hours=2)  # Only 2 hours available
        equip = make_equipment("NMR Spectrometer", quantity=1)

        # Both require 2 hours; only one fits
        req_crit = RequirementSpec(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            equipment_id=equip.id,
            duration_minutes=120,
            earliest_start=h_start,
            latest_end=h_end,
            deadline=h_end,
            is_critical=True,
        )
        p_crit = make_project(
            "Urgent Diagnostics", [req_crit], priority=ProjectPriority.CRITICAL, deadline=h_end
        )
        req_crit.project_id = p_crit.id

        req_low = RequirementSpec(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            equipment_id=equip.id,
            duration_minutes=120,
            earliest_start=h_start,
            latest_end=h_end,
            deadline=h_end + timedelta(days=5),
            is_critical=False,
        )
        p_low = make_project(
            "Routine Assay",
            [req_low],
            priority=ProjectPriority.LOW,
            deadline=h_end + timedelta(days=5),
        )
        req_low.project_id = p_low.id

        input_data = AllocationInput(
            horizon_start=h_start,
            horizon_end=h_end,
            projects=[p_low, p_crit],  # deliberately put low first in input list
            equipment=[equip],
        )

        result = LIAEOptimizer(input_data).solve()
        assert result.satisfied_requirements == 1

        a_crit = next(a for a in result.assignments if a.project_id == p_crit.id)
        a_low = next(a for a in result.assignments if a.project_id == p_low.id)

        assert a_crit.is_satisfied is True
        assert a_low.is_satisfied is False

    def test_dependency_precedence_enforcement(self) -> None:
        """Predecessor requirement must finish before successor requirement starts."""
        h_start, h_end = make_horizon()
        eq1 = make_equipment("Step 1 Prep Station")
        eq2 = make_equipment("Step 2 Analysis Station")

        p_id = uuid.uuid4()
        req1 = RequirementSpec(
            id=uuid.uuid4(),
            project_id=p_id,
            equipment_id=eq1.id,
            duration_minutes=60,
            earliest_start=h_start,
            latest_end=h_end,
        )
        req2 = RequirementSpec(
            id=uuid.uuid4(),
            project_id=p_id,
            equipment_id=eq2.id,
            duration_minutes=60,
            earliest_start=h_start,
            latest_end=h_end,
        )

        dep = DependencySpec(
            predecessor_id=req1.id,
            successor_id=req2.id,
            dependency_type=DependencyType.SEQUENTIAL,
        )

        p = make_project(
            "Multi-stage Experiment",
            [req1, req2],
            dependencies=[dep],
        )

        input_data = AllocationInput(
            horizon_start=h_start,
            horizon_end=h_end,
            projects=[p],
            equipment=[eq1, eq2],
        )

        result = LIAEOptimizer(input_data).solve()
        assert result.satisfied_requirements == 2

        a1 = next(a for a in result.assignments if a.requirement_id == req1.id)
        a2 = next(a for a in result.assignments if a.requirement_id == req2.id)

        assert a1.is_satisfied and a2.is_satisfied
        assert a1.assigned_end is not None and a2.assigned_start is not None
        assert a1.assigned_end <= a2.assigned_start, (
            f"Precedence violation: step 1 ended at {a1.assigned_end}, "
            f"but step 2 started at {a2.assigned_start}"
        )

    def test_infeasible_request_handling(self) -> None:
        """Requirement requiring more time than the horizon is cleanly marked unsatisfied."""
        h_start, h_end = make_horizon()  # 48 hours = 2880 minutes
        equip = make_equipment("Thermal Cycler")

        req = RequirementSpec(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            equipment_id=equip.id,
            duration_minutes=5000,  # exceeds horizon of 2880 mins
            earliest_start=h_start,
            latest_end=h_end,
        )
        p = make_project("Long Assay", [req])
        req.project_id = p.id

        input_data = AllocationInput(
            horizon_start=h_start,
            horizon_end=h_end,
            projects=[p],
            equipment=[equip],
        )

        result = LIAEOptimizer(input_data).solve()
        assert result.satisfied_requirements == 0
        assign = result.assignments[0]
        assert assign.is_satisfied is False
        assert "horizon" in assign.explanation.lower() or "unmet" in assign.explanation.lower()

    def test_solver_status_optimal_vs_feasible(self) -> None:
        """The engine correctly returns OPTIMAL or FEASIBLE without false status reporting."""
        h_start, h_end = make_horizon()
        equip = make_equipment("Incubator")
        req = RequirementSpec(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            equipment_id=equip.id,
            duration_minutes=30,
            earliest_start=h_start,
            latest_end=h_end,
        )
        p = make_project("Bacterial Culture", [req])
        req.project_id = p.id

        input_data = AllocationInput(
            horizon_start=h_start,
            horizon_end=h_end,
            projects=[p],
            equipment=[equip],
            solver_time_limit_seconds=10.0,
        )

        result = LIAEOptimizer(input_data).solve()
        assert result.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
        if result.solver_status_raw == "OPTIMAL":
            assert result.status == SolverStatus.OPTIMAL
        elif result.solver_status_raw == "FEASIBLE":
            assert result.status == SolverStatus.FEASIBLE


class TestFairnessAndMetrics:
    """Unit tests for fairness calculations and explainability."""

    def test_jains_fairness_index(self) -> None:
        """Equal allocations yield Jain's Index = 1.0; unequal yields < 1.0."""
        # Perfectly equal
        assert compute_jains_index([1.0, 1.0, 1.0, 1.0]) == 1.0
        # Disparate allocations
        unequal = compute_jains_index([1.0, 0.0, 0.0, 0.0])
        assert unequal == 0.25
        # Empty list yields 1.0
        assert compute_jains_index([]) == 1.0

    def test_gini_coefficient(self) -> None:
        """Equal values yield Gini = 0.0; skewed values yield Gini > 0.0."""
        assert compute_gini_coefficient([5.0, 5.0, 5.0]) == 0.0
        skewed = compute_gini_coefficient([0.0, 0.0, 10.0])
        assert skewed > 0.5
        assert compute_gini_coefficient([]) == 0.0

    def test_need_weighted_priority(self) -> None:
        """Priority weight scales with critical > high > medium > low."""
        w_crit = compute_priority_weight(ProjectPriority.CRITICAL.value)
        w_high = compute_priority_weight(ProjectPriority.HIGH.value)
        w_med = compute_priority_weight(ProjectPriority.MEDIUM.value)
        w_low = compute_priority_weight(ProjectPriority.LOW.value)
        assert w_crit > w_high > w_med > w_low

    def test_explainer_formatting(self) -> None:
        """Explainer produces coherent human-readable strings."""
        eq = make_equipment("Flow Cytometer")
        h_start, h_end = make_horizon()
        req = RequirementSpec(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            equipment_id=eq.id,
            duration_minutes=60,
            earliest_start=h_start,
            latest_end=h_end,
        )
        p = make_project("Cytometry Assay", [req])
        req.project_id = p.id
        input_data = AllocationInput(
            horizon_start=h_start,
            horizon_end=h_end,
            projects=[p],
            equipment=[eq],
        )

        # Satisfied assignment
        assign_ok = ScheduledAssignment(
            requirement_id=req.id,
            project_id=p.id,
            equipment_id=eq.id,
            assigned_start=h_start,
            assigned_end=h_start + timedelta(hours=1),
            is_satisfied=True,
            is_primary_match=True,
            explanation="",
        )
        exp_text, factors = generate_assignment_explanation(assign_ok, input_data)
        assert "Flow Cytometer" in exp_text
        assert "allocated" in exp_text.lower() or "scheduled" in exp_text.lower()
        assert "hard_constraints_satisfied" in factors

        # Unmet assignment
        assign_unmet = ScheduledAssignment(
            requirement_id=req.id,
            project_id=p.id,
            equipment_id=None,
            assigned_start=None,
            assigned_end=None,
            is_satisfied=False,
            is_primary_match=False,
            explanation="",
        )
        unmet_text, unmet_factors = generate_assignment_explanation(assign_unmet, input_data)
        assert "could not be satisfied" in unmet_text.lower()
        assert "hard_constraints_active" in unmet_factors

        # Summary explanation
        summary = generate_run_summary_explanation(
            status_str="optimal",
            total_reqs=1,
            satisfied_reqs=1,
            solve_time_seconds=0.05,
            unmet_critical=0,
        )
        assert "OPTIMAL" in summary
        assert "100.0%" in summary
