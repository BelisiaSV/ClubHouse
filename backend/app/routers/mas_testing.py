from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import get_current_user
from app.models import User
from app.schemas_dashboards import PlanNextMasTestRequest, TestPlanningResultSchema, TrainingZoneSchema
from app.services.mas_testing import plan_next_mas_test, recalculate_training_zones

router = APIRouter(prefix="/api/mas-testing", tags=["mas-testing"])


@router.post("/plan-next-test", response_model=TestPlanningResultSchema)
def plan_next_test(payload: PlanNextMasTestRequest, current_user: User = Depends(get_current_user)):
    result = plan_next_mas_test(
        player_name=payload.player_name,
        last_test_date=payload.last_test_date,
        cycle=payload.cycle.to_dataclass(),
        today=payload.today,
        due_soon_window_days=payload.due_soon_window_days,
    )
    return TestPlanningResultSchema.model_validate(result)


@router.get("/zones", response_model=list[TrainingZoneSchema])
def zones(mas_kmh: float = Query(gt=0), current_user: User = Depends(get_current_user)):
    try:
        result = recalculate_training_zones(mas_kmh)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [TrainingZoneSchema.model_validate(z) for z in result]
