"""
LIAE: Explainability Engine.

Generates human-readable, auditable decision justifications for every resource
requirement, explaining why an allocation was granted or why it remained unmet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.intelligence.allocation.data_types import (
        AllocationInput,
        ScheduledAssignment,
    )


def generate_assignment_explanation(
    assignment: ScheduledAssignment,
    input_data: AllocationInput,
) -> tuple[str, list[str]]:
    """
    Produce an explainable diagnostic text and list of contributing factors for an assignment.
    """
    factors: list[str] = []

    # Find project and requirement
    project = next((p for p in input_data.projects if p.id == assignment.project_id), None)
    req = None
    if project:
        req = next((r for r in project.requirements if r.id == assignment.requirement_id), None)

    if not assignment.is_satisfied:
        # Explain why unmet
        reasons = [
            "Requirement could not be satisfied within the horizon under hard constraints."
        ]
        factors.append("hard_constraints_active")

        if req and req.is_critical:
            reasons.append("Requirement was marked critical, but no feasible slot was found.")
            factors.append("critical_requirement_unsatisfied")

        if req and req.earliest_start and req.latest_end:
            reasons.append(
                f"Constrained by time window: "
                f"[{req.earliest_start.isoformat()} to {req.latest_end.isoformat()}]."
            )
            factors.append("time_window_constraint")

        # Check if equipment has conflicting commitments
        if req:
            commitments = [c for c in input_data.commitments if c.equipment_id == req.equipment_id]
            if commitments:
                reasons.append(
                    f"Target equipment has {len(commitments)} existing commitments "
                    f"(confirmed bookings/maintenance) limiting capacity."
                )
                factors.append("equipment_commitments_collision")

        return " ".join(reasons), factors

    # Satisfied requirement
    equip = next((e for e in input_data.equipment if e.id == assignment.equipment_id), None)
    equip_name = equip.name if equip else str(assignment.equipment_id)
    factors.append("hard_constraints_satisfied")

    text_parts = []
    if assignment.is_primary_match:
        text_parts.append(f"Allocated primary requested equipment '{equip_name}'.")
        factors.append("primary_equipment_match")
    else:
        text_parts.append(f"Allocated registered compatible substitute equipment '{equip_name}'.")
        factors.append("substitute_equipment_match")

    if assignment.assigned_start and assignment.assigned_end:
        text_parts.append(
            f"Scheduled from {assignment.assigned_start.strftime('%Y-%m-%d %H:%M')} "
            f"to {assignment.assigned_end.strftime('%Y-%m-%d %H:%M')} UTC."
        )

    if project:
        p_val = project.priority.value if hasattr(project.priority, "value") else str(project.priority)
        text_parts.append(f"Project priority: {p_val.upper()}.")
        factors.append(f"priority_{p_val}")

        deadline = (
            project.deadline.replace(tzinfo=timezone.utc)
            if project.deadline and project.deadline.tzinfo is None
            else project.deadline
        )
        end_time = (
            assignment.assigned_end.replace(tzinfo=timezone.utc)
            if assignment.assigned_end and assignment.assigned_end.tzinfo is None
            else assignment.assigned_end
        )

        if deadline and end_time:
            if end_time <= deadline:
                text_parts.append("Satisfies project deadline.")
                factors.append("deadline_satisfied")
            else:
                text_parts.append("Warning: Scheduled beyond requested project deadline.")
                factors.append("deadline_exceeded")

    return " ".join(text_parts), factors


def generate_run_summary_explanation(
    status_str: str,
    total_reqs: int,
    satisfied_reqs: int,
    solve_time_seconds: float,
    unmet_critical: int,
) -> str:
    """
    Produce a top-level human-readable audit summary for the allocation run.
    """
    rate = (satisfied_reqs / total_reqs * 100) if total_reqs > 0 else 100.0
    summary = (
        f"LIAE solver finished in {solve_time_seconds:.3f}s with status '{status_str.upper()}'. "
        f"Satisfied {satisfied_reqs} of {total_reqs} requirements ({rate:.1f}% fulfillment rate). "
    )
    if unmet_critical > 0:
        summary += (
            f"CRITICAL ALERT: {unmet_critical} critical requirements could not be scheduled. "
        )
    else:
        summary += "All critical requirements (if any) were successfully satisfied. "

    return summary
