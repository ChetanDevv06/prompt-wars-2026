"""
Intelligence: Deterministic resource-matching service.

Identifies candidate equipment that can satisfy a project resource requirement,
checking compatibility, availability windows, maintenance periods, and status.

This is intentionally separate from the CP-SAT optimisation engine (M04).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.enums import EquipmentStatus
from app.models.equipment import Equipment
from app.repositories.equipment import EquipmentCompatibilityRepository, EquipmentRepository


@dataclass
class CandidateResult:
    """
    A single equipment item evaluated as a candidate for a resource requirement.
    """

    equipment_id: uuid.UUID
    equipment_name: str
    laboratory_id: uuid.UUID
    is_available: bool
    is_primary_match: bool  # True = exact match, False = compatible alternative
    quantity_available: int
    reasons: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    """
    The full set of matching results for a resource requirement.
    """

    requirement_id: uuid.UUID | None
    equipment_id: uuid.UUID  # the originally requested equipment
    quantity_required: int
    duration_minutes: int
    window_start: datetime | None
    window_end: datetime | None
    candidates: list[CandidateResult] = field(default_factory=list)
    can_be_satisfied: bool = False


class ResourceMatchingService:
    """
    Deterministic resource-matching service.

    Evaluates whether a requested piece of equipment (and compatible alternatives)
    can satisfy a resource requirement during the requested time window.

    Does NOT perform CP-SAT optimisation. That is deferred to M04 (LIAE).
    """

    def __init__(self, session: Session) -> None:
        self._equip_repo = EquipmentRepository(session)
        self._compat_repo = EquipmentCompatibilityRepository(session)

    def match_requirement(
        self,
        *,
        equipment_id: uuid.UUID,
        quantity_required: int,
        duration_minutes: int,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
        requirement_id: uuid.UUID | None = None,
    ) -> MatchResult:
        """
        Find candidate equipment that can fulfil the requirement.

        Args:
            equipment_id:       The originally requested equipment ID.
            quantity_required:  Number of units needed.
            duration_minutes:   How long the equipment is needed.
            window_start:       Earliest acceptable start (optional).
            window_end:         Latest acceptable end (optional).
            requirement_id:     Back-reference to the requirement (optional).

        Returns:
            MatchResult with primary candidate and compatible alternatives.
        """
        result = MatchResult(
            requirement_id=requirement_id,
            equipment_id=equipment_id,
            quantity_required=quantity_required,
            duration_minutes=duration_minutes,
            window_start=window_start,
            window_end=window_end,
        )

        # Evaluate the primary (requested) equipment
        primary = self._equip_repo.get_by_id_with_relations(equipment_id)
        if primary is not None:
            candidate = self._evaluate_candidate(
                equipment=primary,
                quantity_required=quantity_required,
                window_start=window_start,
                window_end=window_end,
                is_primary=True,
            )
            result.candidates.append(candidate)

        # Evaluate compatible alternatives
        alternatives = self._compat_repo.find_alternatives(equipment_id)
        for alt in alternatives:
            alt_detail = self._equip_repo.get_by_id_with_relations(alt.id)
            if alt_detail is None:
                continue
            candidate = self._evaluate_candidate(
                equipment=alt_detail,
                quantity_required=quantity_required,
                window_start=window_start,
                window_end=window_end,
                is_primary=False,
            )
            result.candidates.append(candidate)

        result.can_be_satisfied = any(c.is_available for c in result.candidates)
        return result

    def _evaluate_candidate(
        self,
        *,
        equipment: Equipment,
        quantity_required: int,
        window_start: datetime | None,
        window_end: datetime | None,
        is_primary: bool,
    ) -> CandidateResult:
        """
        Assess a single equipment candidate against the requirement constraints.
        """
        reasons: list[str] = []
        is_available = True

        # 1. Status check
        if not equipment.is_bookable:
            reasons.append("Equipment is not bookable.")
            is_available = False
        if equipment.status == EquipmentStatus.DECOMMISSIONED:
            reasons.append("Equipment is decommissioned.")
            is_available = False
        elif equipment.status == EquipmentStatus.UNDER_MAINTENANCE:
            reasons.append("Equipment is currently under maintenance.")
            is_available = False
        elif equipment.status == EquipmentStatus.UNAVAILABLE:
            reasons.append("Equipment is marked unavailable.")
            is_available = False

        # 2. Quantity check
        if equipment.quantity < quantity_required:
            reasons.append(
                f"Insufficient quantity: {equipment.quantity} available, "
                f"{quantity_required} required."
            )
            is_available = False

        # 3. Window / time-overlap check
        if window_start and window_end and is_available:
            window_ok = self._equip_repo.find_available_in_window(
                equipment.id, window_start, window_end
            )
            if not window_ok:
                reasons.append(
                    "Equipment is unavailable during the requested time window "
                    "(confirmed reservation or maintenance overlap)."
                )
                is_available = False

        if is_available:
            reasons.append("Equipment is available and meets all constraints.")

        return CandidateResult(
            equipment_id=equipment.id,
            equipment_name=equipment.name,
            laboratory_id=equipment.laboratory_id,
            is_available=is_available,
            is_primary_match=is_primary,
            quantity_available=equipment.quantity,
            reasons=reasons,
        )
