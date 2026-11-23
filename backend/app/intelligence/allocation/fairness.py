"""
LIAE: Need-Aware Fairness & Historical Load Calculations.

Calculates fairness metrics (Jain's index, Gini coefficient) and scoring weights
based on genuine project needs, urgency, scarcity, and historical access.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.intelligence.allocation.data_types import (
        FairnessMetrics,
        HistoricalUsageSpec,
        ProjectSpec,
        RequirementSpec,
    )


def compute_priority_weight(priority_value: str | object) -> int:
    """
    Map project priority to an integer weight for L2 need-weighted fulfillment.

    CRITICAL = 40, HIGH = 25, MEDIUM = 15, LOW = 5.
    """
    p_str = (
        priority_value.value
        if hasattr(priority_value, "value")
        else str(priority_value)
    )
    weights = {
        "critical": 40,
        "high": 25,
        "medium": 15,
        "low": 5,
    }
    return weights.get(p_str.lower(), 15)


def compute_fairness_multiplier(
    dept_id: uuid.UUID | None,
    historical_records: list[HistoricalUsageSpec],
) -> int:
    """
    Compute integer multiplier for L3 fairness.

    Under-served departments receive higher reward points when their requirements are fulfilled.
    If no historical records exist, returns neutral baseline (10).
    """
    if not historical_records or dept_id is None:
        return 10

    dept_history = next(
        (h for h in historical_records if h.department_id == dept_id),
        None,
    )
    if dept_history is None:
        # No past bookings: maximum priority boost for new/under-served department
        return 20

    count = dept_history.confirmed_reservations_count
    if count == 0:
        return 20
    elif count <= 2:
        return 15
    elif count <= 5:
        return 10
    else:
        # Heavy past usage: lower multiplier to prevent monopolization
        return 5


def compute_jains_index(allocations: list[float]) -> float:
    """
    Compute Jain's Fairness Index for a list of allocation shares.

    J(x) = (sum(x_i))^2 / (n * sum(x_i^2))
    Returns 1.0 (perfectly fair) if empty or all equal, 1/n in worst case.
    """
    if not allocations:
        return 1.0
    n = len(allocations)
    sum_x = sum(allocations)
    sum_sq = sum(x * x for x in allocations)
    if sum_sq == 0:
        return 1.0
    return float((sum_x * sum_x) / (n * sum_sq))


def compute_gini_coefficient(values: list[float]) -> float:
    """
    Compute Gini coefficient of inequality for allocation distribution.

    0.0 = perfect equality, 1.0 = maximum inequality.
    """
    if not values or len(values) < 2:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    total = sum(sorted_vals)
    if total == 0:
        return 0.0
    cumulative = 0.0
    for i, val in enumerate(sorted_vals, 1):
        cumulative += val * (2 * i - n - 1)
    return float(cumulative / (n * total))


def evaluate_run_fairness(
    projects: list[ProjectSpec],
    satisfied_req_ids: set[uuid.UUID],
    historical_records: list[HistoricalUsageSpec],
) -> FairnessMetrics:
    """
    Evaluate overall allocation fairness across departments.
    """
    from app.intelligence.allocation.data_types import FairnessMetrics

    if not projects:
        return FairnessMetrics(
            jains_fairness_index=1.0,
            gini_coefficient=0.0,
            department_fulfillment_rates={},
            historical_data_available=bool(historical_records),
            notes="No projects evaluated.",
        )

    dept_reqs: dict[str, list[RequirementSpec]] = {}
    for p in projects:
        key = str(p.department_id) if p.department_id else "independent"
        dept_reqs.setdefault(key, []).extend(p.requirements)

    fulfillment_rates: dict[str, float] = {}
    rate_values: list[float] = []

    for dept_key, reqs in dept_reqs.items():
        if not reqs:
            continue
        sat_count = sum(1 for r in reqs if r.id in satisfied_req_ids)
        rate = sat_count / len(reqs)
        fulfillment_rates[dept_key] = round(rate, 4)
        rate_values.append(rate)

    jains = compute_jains_index(rate_values)
    gini = compute_gini_coefficient(rate_values)

    has_history = bool(historical_records)
    hist_text = "incorporated" if has_history else "unavailable (neutral baseline applied)"
    notes = (
        f"Evaluated across {len(fulfillment_rates)} department group(s). "
        f"Historical usage data was {hist_text}."
    )

    return FairnessMetrics(
        jains_fairness_index=round(jains, 4),
        gini_coefficient=round(gini, 4),
        department_fulfillment_rates=fulfillment_rates,
        historical_data_available=has_history,
        notes=notes,
    )
