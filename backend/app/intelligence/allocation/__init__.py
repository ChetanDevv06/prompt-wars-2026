"""
LIAE: LabLink Intelligent Allocation Engine package.

Google OR-Tools CP-SAT powered optimization engine for laboratory resource scheduling.
"""

from app.intelligence.allocation.data_types import (
    AllocationInput,
    AllocationResult,
    DependencySpec,
    EquipmentSpec,
    ExistingCommitmentSpec,
    FairnessMetrics,
    HistoricalUsageSpec,
    ObjectiveScores,
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
    compute_fairness_multiplier,
    compute_gini_coefficient,
    compute_jains_index,
    compute_priority_weight,
    evaluate_run_fairness,
)
from app.intelligence.allocation.solver import LIAEOptimizer

__all__ = [
    "AllocationInput",
    "AllocationResult",
    "DependencySpec",
    "EquipmentSpec",
    "ExistingCommitmentSpec",
    "FairnessMetrics",
    "HistoricalUsageSpec",
    "LIAEOptimizer",
    "ObjectiveScores",
    "ProjectSpec",
    "RequirementSpec",
    "ScheduledAssignment",
    "SubstituteSpec",
    "compute_fairness_multiplier",
    "compute_gini_coefficient",
    "compute_jains_index",
    "compute_priority_weight",
    "evaluate_run_fairness",
    "generate_assignment_explanation",
    "generate_run_summary_explanation",
]
