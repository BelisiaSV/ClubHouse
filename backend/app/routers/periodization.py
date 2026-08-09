from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_current_user
from app.models import User
from app.schemas_dashboards import BuildCycleRequest, RescheduleCycleRequest, TrainingCycleSchema
from app.services.periodization import build_cycle, handle_match_cancellation

router = APIRouter(prefix="/api/periodization", tags=["periodization"])


@router.post("/cycles", response_model=TrainingCycleSchema)
def create_cycle(payload: BuildCycleRequest, current_user: User = Depends(get_current_user)):
    cycle = build_cycle(
        name=payload.name,
        length_weeks=payload.length_weeks,
        start_date=payload.start_date,
        target_match_date=payload.target_match_date,
        target_peak_weekly_km=payload.target_peak_weekly_km,
    )
    return TrainingCycleSchema.model_validate(cycle)


@router.post("/cycles/reschedule", response_model=TrainingCycleSchema)
def reschedule_cycle(payload: RescheduleCycleRequest, current_user: User = Depends(get_current_user)):
    """Herberekent een cyclus wanneer de doelwedstrijd wordt afgelast: schuift de
    resterende weken op en injecteert onderhoudsweken zodat er geen trainingsgat
    ontstaat."""
    cycle = payload.cycle.to_dataclass()
    try:
        updated = handle_match_cancellation(
            cycle,
            cancelled_match_date=payload.cancelled_match_date,
            new_match_date=payload.new_match_date,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TrainingCycleSchema.model_validate(updated)
