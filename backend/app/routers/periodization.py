from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import CycleLength as DbCycleLength
from app.models import TrainingCycle as DbTrainingCycle
from app.models import TrainingCycleWeek as DbTrainingCycleWeek
from app.models import User
from app.models import WeekFocus as DbWeekFocus
from app.schemas_dashboards import BuildCycleRequest, RescheduleCycleRequest, TrainingCycleSchema
from app.services.periodization import build_cycle, handle_match_cancellation

router = APIRouter(prefix="/api/periodization", tags=["periodization"])

_LENGTH_WEEKS_TO_DB = {
    4: DbCycleLength.FOUR_WEEKS,
    6: DbCycleLength.SIX_WEEKS,
    8: DbCycleLength.EIGHT_WEEKS,
}


def _persist_as_active_cycle(cycle, club_id, db: Session) -> None:
    """Stores the computed cycle as the club's one active training cycle, so
    server-side lookups (e.g. POST /api/makeup-programs/generate-for-match) can
    resolve "the active cycle/week" without the frontend re-sending it."""
    for existing in db.scalars(
        select(DbTrainingCycle).where(DbTrainingCycle.club_id == club_id, DbTrainingCycle.is_active.is_(True))
    ):
        existing.is_active = False

    db_cycle = DbTrainingCycle(
        club_id=club_id,
        name=cycle.name,
        length_type=_LENGTH_WEEKS_TO_DB[cycle.length_weeks],
        start_date=cycle.start_date,
        end_date=cycle.end_date(),
        is_active=True,
        shift_count=cycle.shift_count,
    )
    db.add(db_cycle)
    db.flush()

    for week in cycle.weeks:
        db.add(
            DbTrainingCycleWeek(
                training_cycle_id=db_cycle.id,
                week_number=week.week_number,
                week_start_date=week.week_start_date,
                focus=DbWeekFocus(week.focus.value),
                planned_load_pct=week.planned_load_pct,
            )
        )
    db.commit()


@router.post("/cycles", response_model=TrainingCycleSchema)
def create_cycle(
    payload: BuildCycleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cycle = build_cycle(
        name=payload.name,
        length_weeks=payload.length_weeks,
        start_date=payload.start_date,
        target_match_date=payload.target_match_date,
        target_peak_weekly_km=payload.target_peak_weekly_km,
    )
    _persist_as_active_cycle(cycle, current_user.club_id, db)
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
