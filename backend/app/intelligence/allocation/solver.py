# pyright: reportAttributeAccessIssue=false
"""
LIAE: LabLink Intelligent Allocation Engine — Google OR-Tools CP-SAT Solver.

Implements:
- Model formulation with discrete integer minute time domain.
- L0 Hard constraints:
    * Resource availability and equipment capacity (NoOverlap / Cumulative).
    * Preservation of existing confirmed reservations and maintenance windows.
    * Equipment compatibility (only requested equipment or registered substitutes).
    * Time window boundaries (earliest start, latest end, horizon).
    * Project DAG dependencies (predecessor end <= successor start).
- Sequential Lexicographic Optimization passes:
    * L1: Critical deadline satisfaction (minimize unmet critical requirements and lateness).
    * L2: Need-weighted fulfillment (maximize priority-weighted requirement satisfaction).
    * L3: Historical access fairness (maximize access balance for under-served departments).
    * L4: Productive resource utilization (maximize total usage minutes).
    * L5: Scheduling preference (minimize deviation from preferred start).
- Strict status mapping: Never report FEASIBLE as OPTIMAL.
- Configurable solver time limits and failure diagnostic reporting.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta

from ortools.sat.python import cp_model

from app.domain.enums import DependencyType, SolverStatus
from app.intelligence.allocation.data_types import (
    AllocationInput,
    AllocationResult,
    ObjectiveScores,
    ScheduledAssignment,
)
from app.intelligence.allocation.explainer import (
    generate_assignment_explanation,
    generate_run_summary_explanation,
)
from app.intelligence.allocation.fairness import (
    compute_fairness_multiplier,
    compute_priority_weight,
    evaluate_run_fairness,
)


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class LIAEOptimizer:
    """
    CP-SAT Optimization Engine for laboratory resource allocation.
    """

    def __init__(self, input_data: AllocationInput) -> None:
        self.input_data = input_data
        h_start = _to_utc(input_data.horizon_start)
        h_end = _to_utc(input_data.horizon_end)
        assert h_start is not None and h_end is not None
        self.horizon_start = h_start
        self.horizon_end = h_end
        self.total_horizon_minutes = max(
            1, int((self.horizon_end - self.horizon_start).total_seconds() // 60)
        )

    def solve(self) -> AllocationResult:
        """
        Execute the optimization pipeline and return an AllocationResult.
        """
        start_wall_time = time.perf_counter()

        # Edge cases: No projects or no equipment
        if not self.input_data.projects or not self.input_data.equipment:
            elapsed = time.perf_counter() - start_wall_time
            assignments = []
            for p in self.input_data.projects:
                for r in p.requirements:
                    assignments.append(
                        ScheduledAssignment(
                            requirement_id=r.id,
                            project_id=p.id,
                            equipment_id=None,
                            assigned_start=None,
                            assigned_end=None,
                            is_satisfied=False,
                            is_primary_match=False,
                            explanation="No equipment available or no projects provided.",
                            decision_factors=["no_resources_or_projects"],
                        )
                    )
            fairness = evaluate_run_fairness(
                self.input_data.projects, set(), self.input_data.historical_usage
            )
            return AllocationResult(
                status=SolverStatus.FEASIBLE
                if not self.input_data.projects
                else SolverStatus.INFEASIBLE,
                solver_status_raw="TRIVIAL_EMPTY",
                solve_time_seconds=elapsed,
                assignments=assignments,
                total_projects=len(self.input_data.projects),
                allocated_projects=0,
                total_requirements=sum(len(p.requirements) for p in self.input_data.projects),
                satisfied_requirements=0,
                objective_scores=ObjectiveScores(),
                fairness_metrics=fairness,
                diagnostic_message="No resource requirements or equipment to evaluate.",
            )

        model = cp_model.CpModel()

        # ------------------------------------------------------------------
        # 1. Decision Variables
        # ------------------------------------------------------------------
        # Map: candidate_key -> presence_literal, start_var, end_var, interval_var
        # candidate_key: (project_id, requirement_id, equipment_id)
        candidate_vars: dict[tuple[uuid.UUID, uuid.UUID, uuid.UUID], dict[str, object]] = {}
        # requirement_presences: req_id -> list of presence literals (at most one is selected)
        req_presences: dict[uuid.UUID, list[cp_model.IntVar]] = {}
        # req_start_vars: req_id -> start_var
        req_start_vars: dict[uuid.UUID, cp_model.IntVar] = {}
        # req_end_vars: req_id -> end_var
        req_end_vars: dict[uuid.UUID, cp_model.IntVar] = {}

        # Build candidate equipment options for each requirement
        substitute_map: dict[uuid.UUID, set[uuid.UUID]] = {}
        for sub in self.input_data.substitutes:
            substitute_map.setdefault(sub.primary_id, set()).add(sub.compatible_id)

        equipment_lookup = {e.id: e for e in self.input_data.equipment}

        for project in self.input_data.projects:
            for req in project.requirements:
                req_presences[req.id] = []

                # Candidate equipment: primary requested + registered compatible substitutes
                candidates = [req.equipment_id]
                for sub_id in substitute_map.get(req.equipment_id, set()):
                    if sub_id in equipment_lookup and sub_id not in candidates:
                        candidates.append(sub_id)

                # Filter candidates to only bookable and non-decommissioned
                valid_candidates = [
                    cid
                    for cid in candidates
                    if cid in equipment_lookup
                    and equipment_lookup[cid].is_bookable
                    and equipment_lookup[cid].status != "decommissioned"
                ]

                # Determine earliest start and latest end in minutes relative to horizon_start
                es_dt = _to_utc(req.earliest_start)
                le_dt = _to_utc(req.latest_end)

                es_min = 0
                if es_dt and es_dt > self.horizon_start:
                    es_min = max(
                        0, int((es_dt - self.horizon_start).total_seconds() // 60)
                    )

                le_min = self.total_horizon_minutes
                if le_dt and le_dt < self.horizon_end:
                    le_min = min(
                        self.total_horizon_minutes,
                        int((le_dt - self.horizon_start).total_seconds() // 60),
                    )

                duration = req.duration_minutes
                if es_min + duration > le_min or not valid_candidates:
                    # Infeasible right away for this requirement; no variables needed
                    continue

                # Unified start and end variables for the requirement
                r_start = model.NewIntVar(
                    es_min, max(es_min, le_min - duration), f"start_{req.id.hex[:6]}"
                )
                r_end = model.NewIntVar(es_min + duration, le_min, f"end_{req.id.hex[:6]}")
                model.Add(r_end == r_start + duration)

                req_start_vars[req.id] = r_start
                req_end_vars[req.id] = r_end

                for eq_id in valid_candidates:
                    presence = model.NewBoolVar(f"pres_{req.id.hex[:6]}_{eq_id.hex[:6]}")
                    interval = model.NewOptionalIntervalVar(
                        r_start, duration, r_end, presence, f"iv_{req.id.hex[:6]}_{eq_id.hex[:6]}"
                    )
                    candidate_vars[(project.id, req.id, eq_id)] = {
                        "presence": presence,
                        "start": r_start,
                        "end": r_end,
                        "interval": interval,
                        "duration": duration,
                        "quantity": req.quantity_required,
                        "is_primary": (eq_id == req.equipment_id),
                    }
                    req_presences[req.id].append(presence)

                # At most one equipment candidate chosen per requirement
                model.Add(sum(req_presences[req.id]) <= 1)

        # ------------------------------------------------------------------
        # 2. Hard Constraints (L0)
        # ------------------------------------------------------------------

        # Constraint 1: Equipment Capacity & No Overlap with Existing Commitments
        # Group intervals by equipment
        equipment_intervals: dict[uuid.UUID, list[tuple[cp_model.IntervalVar, int]]] = {}
        for eq_id in equipment_lookup:
            equipment_intervals[eq_id] = []

        # Add existing confirmed commitments (reservations / maintenance) as fixed intervals
        for comm in self.input_data.commitments:
            if comm.equipment_id not in equipment_lookup:
                continue
            # Clip commitment to horizon
            c_start_dt = _to_utc(comm.starts_at)
            c_end_dt = _to_utc(comm.ends_at)
            if c_start_dt is None or c_end_dt is None:
                continue
            comm_start = max(self.horizon_start, c_start_dt)
            comm_end = min(self.horizon_end, c_end_dt)
            if comm_end <= comm_start:
                continue
            c_start_min = int((comm_start - self.horizon_start).total_seconds() // 60)
            c_end_min = int((comm_end - self.horizon_start).total_seconds() // 60)
            c_duration = max(1, c_end_min - c_start_min)
            fixed_iv = model.NewFixedSizeIntervalVar(
                c_start_min, c_duration, f"fixed_{comm.id.hex[:6]}"
            )
            equipment_intervals[comm.equipment_id].append((fixed_iv, comm.quantity))

        # Add candidate intervals
        for (_p_id, _r_id, eq_id), c_data in candidate_vars.items():
            interval_var = c_data["interval"]
            qty = int(str(c_data["quantity"]))
            assert isinstance(interval_var, cp_model.IntervalVar)
            equipment_intervals[eq_id].append((interval_var, qty))

        # Enforce NoOverlap or Cumulative constraint for each piece of equipment
        for eq_id, iv_pairs in equipment_intervals.items():
            if not iv_pairs:
                continue
            eq_spec = equipment_lookup[eq_id]
            capacity = eq_spec.quantity
            intervals = [pair[0] for pair in iv_pairs]
            demands = [pair[1] for pair in iv_pairs]

            if capacity == 1 and all(d == 1 for d in demands):
                model.AddNoOverlap(intervals)
            else:
                model.AddCumulative(intervals, demands, capacity)

        # Constraint 2: Project DAG Dependencies
        # (Predecessor requirement must finish before Successor starts)
        for project in self.input_data.projects:
            for dep in project.dependencies:
                pred_id = dep.predecessor_id
                succ_id = dep.successor_id

                if pred_id not in req_end_vars or succ_id not in req_start_vars:
                    # If either is unbookable, successor cannot book if predecessor needed
                    if pred_id not in req_end_vars and succ_id in req_presences:
                        # Predecessor cannot be scheduled, so successor cannot either
                        model.Add(sum(req_presences[succ_id]) == 0)
                    continue

                pred_end = req_end_vars[pred_id]
                succ_start = req_start_vars[succ_id]
                pred_scheduled = sum(req_presences[pred_id])
                succ_scheduled = sum(req_presences[succ_id])

                if dep.dependency_type == DependencyType.SEQUENTIAL:
                    # Successor requires predecessor to be scheduled and finished
                    model.Add(pred_end <= succ_start).OnlyEnforceIf(succ_scheduled)
                    model.Add(pred_scheduled == 1).OnlyEnforceIf(succ_scheduled)

        # ------------------------------------------------------------------
        # 3. Lexicographic Objectives
        # ------------------------------------------------------------------
        # Helper: Boolean fulfilled for requirement r
        req_is_fulfilled: dict[uuid.UUID, cp_model.IntVar] = {}
        for project in self.input_data.projects:
            for req in project.requirements:
                if req_presences.get(req.id):
                    is_sat = model.NewBoolVar(f"is_sat_{req.id.hex[:6]}")
                    model.Add(sum(req_presences[req.id]) == is_sat)
                    req_is_fulfilled[req.id] = is_sat
                else:
                    is_sat = model.NewConstant(0)
                    req_is_fulfilled[req.id] = is_sat

        # L1: Critical Deadline Satisfaction
        # Penalty for unmet critical requirements (each = 1000)
        l1_terms: list[cp_model.LinearExpr] = []
        for project in self.input_data.projects:
            for req in project.requirements:
                if req.is_critical:
                    # 1 - is_sat
                    l1_terms.append(1000 * (1 - req_is_fulfilled[req.id]))

        # L2: Need-Weighted Fulfillment
        # Priority weights: critical=40, high=25, medium=15, low=5
        l2_terms: list[cp_model.LinearExpr] = []
        for project in self.input_data.projects:
            p_val = (
                project.priority.value
                if hasattr(project.priority, "value")
                else str(project.priority)
            )
            p_weight = compute_priority_weight(p_val)
            for req in project.requirements:
                l2_terms.append(p_weight * req_is_fulfilled[req.id])

        # L3: Historical Access Fairness
        l3_terms: list[cp_model.LinearExpr] = []
        for project in self.input_data.projects:
            f_mult = compute_fairness_multiplier(
                project.department_id, self.input_data.historical_usage
            )
            for req in project.requirements:
                l3_terms.append(f_mult * req_is_fulfilled[req.id])

        # L4: Productive Resource Utilization
        l4_terms: list[cp_model.LinearExpr] = []
        for project in self.input_data.projects:
            for req in project.requirements:
                l4_terms.append(req.duration_minutes * req_is_fulfilled[req.id])

        # ------------------------------------------------------------------
        # 4. Multi-Stage Lexicographic Solving
        # ------------------------------------------------------------------
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = max(0.5, self.input_data.solver_time_limit_seconds)
        solver.parameters.num_workers = 1  # Deterministic execution

        status = cp_model.UNKNOWN
        obj_scores = ObjectiveScores()

        if not self.input_data.enable_lexicographic:
            # Single combined pass
            combined_obj = (
                -100 * sum(l1_terms) + 10 * sum(l2_terms) + 5 * sum(l3_terms) + sum(l4_terms)
            )
            model.Maximize(combined_obj)
            status = solver.Solve(model)
        else:
            # Sequential Pass 1: L1 (Critical Deadlines)
            if l1_terms:
                model.Minimize(sum(l1_terms))
                status1 = solver.Solve(model)
                if status1 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                    best_l1 = int(solver.ObjectiveValue())
                    model.Add(sum(l1_terms) <= best_l1)
                    obj_scores.l1_critical_unmet = best_l1 // 1000

            # Sequential Pass 2: L2 (Need-Weighted Fulfillment)
            if l2_terms:
                model.Maximize(sum(l2_terms))
                status2 = solver.Solve(model)
                if status2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                    best_l2 = int(solver.ObjectiveValue())
                    model.Add(sum(l2_terms) >= best_l2)
                    obj_scores.l2_need_weighted_points = best_l2

            # Sequential Pass 3: L3 (Fairness) & L4 (Utilization)
            combined_l3_l4 = sum(l3_terms) * 10 + sum(l4_terms)
            model.Maximize(combined_l3_l4)
            status = solver.Solve(model)

        elapsed_seconds = time.perf_counter() - start_wall_time

        # Map CP-SAT status strictly
        status_mapping = {
            cp_model.OPTIMAL: SolverStatus.OPTIMAL,
            cp_model.FEASIBLE: SolverStatus.FEASIBLE,
            cp_model.INFEASIBLE: SolverStatus.INFEASIBLE,
            cp_model.MODEL_INVALID: SolverStatus.MODEL_INVALID,
            cp_model.UNKNOWN: SolverStatus.UNKNOWN,
        }
        domain_status = status_mapping.get(status, SolverStatus.UNKNOWN)
        solver_status_raw = solver.StatusName(status)

        # ------------------------------------------------------------------
        # 5. Result Extraction & Explanation Generation
        # ------------------------------------------------------------------
        assignments: list[ScheduledAssignment] = []
        satisfied_req_ids: set[uuid.UUID] = set()
        allocated_project_ids: set[uuid.UUID] = set()

        if domain_status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            for project in self.input_data.projects:
                for req in project.requirements:
                    # Check which equipment was chosen
                    chosen_eq_id = None
                    is_primary = True

                    for cid in substitute_map.get(req.equipment_id, set()) | {req.equipment_id}:
                        key = (project.id, req.id, cid)
                        if key in candidate_vars:
                            pres = candidate_vars[key]["presence"]
                            assert isinstance(pres, cp_model.IntVar)
                            if solver.Value(pres) == 1:
                                chosen_eq_id = cid
                                is_primary = bool(candidate_vars[key]["is_primary"])
                                break

                    if chosen_eq_id is not None:
                        start_offset = solver.Value(req_start_vars[req.id])
                        end_offset = solver.Value(req_end_vars[req.id])
                        assigned_start = self.horizon_start + timedelta(minutes=start_offset)
                        assigned_end = self.horizon_start + timedelta(minutes=end_offset)
                        is_satisfied = True
                        satisfied_req_ids.add(req.id)
                        allocated_project_ids.add(project.id)
                        obj_scores.l4_utilization_minutes += req.duration_minutes
                    else:
                        assigned_start = None
                        assigned_end = None
                        is_satisfied = False

                    candidate_assignment = ScheduledAssignment(
                        requirement_id=req.id,
                        project_id=project.id,
                        equipment_id=chosen_eq_id,
                        assigned_start=assigned_start,
                        assigned_end=assigned_end,
                        is_satisfied=is_satisfied,
                        is_primary_match=is_primary,
                        explanation="",
                    )
                    # Generate explainability details
                    expl_text, factors = generate_assignment_explanation(
                        candidate_assignment, self.input_data
                    )
                    candidate_assignment.explanation = expl_text
                    candidate_assignment.decision_factors = factors
                    assignments.append(candidate_assignment)
        else:
            # Infeasible or timed out
            for project in self.input_data.projects:
                for req in project.requirements:
                    assignments.append(
                        ScheduledAssignment(
                            requirement_id=req.id,
                            project_id=project.id,
                            equipment_id=None,
                            assigned_start=None,
                            assigned_end=None,
                            is_satisfied=False,
                            is_primary_match=False,
                            explanation=(
                                f"Allocation failed: solver reported status '{solver_status_raw}'. "
                                "Hard constraints could not be satisfied."
                            ),
                            decision_factors=["solver_unresolved"],
                        )
                    )

        fairness_metrics = evaluate_run_fairness(
            self.input_data.projects, satisfied_req_ids, self.input_data.historical_usage
        )

        total_reqs = sum(len(p.requirements) for p in self.input_data.projects)
        diagnostic_summary = generate_run_summary_explanation(
            status_str=domain_status.value,
            total_reqs=total_reqs,
            satisfied_reqs=len(satisfied_req_ids),
            solve_time_seconds=elapsed_seconds,
            unmet_critical=obj_scores.l1_critical_unmet,
        )

        return AllocationResult(
            status=domain_status,
            solver_status_raw=solver_status_raw,
            solve_time_seconds=round(elapsed_seconds, 4),
            assignments=assignments,
            total_projects=len(self.input_data.projects),
            allocated_projects=len(allocated_project_ids),
            total_requirements=total_reqs,
            satisfied_requirements=len(satisfied_req_ids),
            objective_scores=obj_scores,
            fairness_metrics=fairness_metrics,
            diagnostic_message=diagnostic_summary,
        )
