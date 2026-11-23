"""
API endpoints: Resource matching.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.schemas.matching import CandidateResultSchema, MatchRequest, MatchResultSchema
from app.api.v1.schemas_common import SuccessResponse
from app.infrastructure.database import get_db
from app.intelligence.matching import ResourceMatchingService

router = APIRouter()


@router.post(
    "/matching/check",
    response_model=SuccessResponse[MatchResultSchema],
    summary="Check resource availability",
    description=(
        "Evaluate whether a resource requirement can be satisfied. "
        "Returns the primary candidate and any compatible alternatives "
        "with availability reasons. Does not create a reservation."
    ),
)
def check_resource_match(
    body: MatchRequest,
    session: Session = Depends(get_db),
) -> SuccessResponse[MatchResultSchema]:
    """Check resource availability for a requirement."""
    svc = ResourceMatchingService(session)
    result = svc.match_requirement(
        equipment_id=body.equipment_id,
        quantity_required=body.quantity_required,
        duration_minutes=body.duration_minutes,
        window_start=body.window_start,
        window_end=body.window_end,
        requirement_id=body.requirement_id,
    )
    return SuccessResponse(
        data=MatchResultSchema(
            requirement_id=result.requirement_id,
            equipment_id=result.equipment_id,
            quantity_required=result.quantity_required,
            duration_minutes=result.duration_minutes,
            window_start=result.window_start,
            window_end=result.window_end,
            candidates=[
                CandidateResultSchema(
                    equipment_id=c.equipment_id,
                    equipment_name=c.equipment_name,
                    laboratory_id=c.laboratory_id,
                    is_available=c.is_available,
                    is_primary_match=c.is_primary_match,
                    quantity_available=c.quantity_available,
                    reasons=c.reasons,
                )
                for c in result.candidates
            ],
            can_be_satisfied=result.can_be_satisfied,
        )
    )
