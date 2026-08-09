from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.models import User
from app.schemas_dashboards import GenerateKmPlanRequest, WeeklyKmPlanSchema
from app.services.volume_planning import generate_cycle_km_plan

router = APIRouter(prefix="/api/volume-planning", tags=["volume-planning"])


@router.post("/km-plan", response_model=list[WeeklyKmPlanSchema])
def km_plan(payload: GenerateKmPlanRequest, current_user: User = Depends(get_current_user)):
    plans = generate_cycle_km_plan(
        cycle=payload.cycle.to_dataclass(),
        avg_match_distance_km=payload.avg_match_distance_km,
        min_recovery_km_per_training=payload.min_recovery_km_per_training,
    )
    return [WeeklyKmPlanSchema.model_validate(p) for p in plans]
