import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import CycleLength as DbCycleLength
from app.models import TrainingCycle as DbTrainingCycle
from app.models import TrainingCycleWeek as DbTrainingCycleWeek
from app.models import User
from app.models import WeekFocus as DbWeekFocus
from app.schemas_dashboards import (
    BuildCycleRequest,
    QueueNextCycleRequest,
    RescheduleCycleRequest,
    TrainingCycleSchema,
)
from app.services.periodization import CycleWeek as ServiceCycleWeek
from app.services.periodization import Season
from app.services.periodization import TrainingCycle as ServiceTrainingCycle
from app.services.periodization import WeekFocus as ServiceWeekFocus
from app.services.periodization import build_cycle, handle_match_cancellation
from app.services.periodization import queue_next_cycle as svc_queue_next_cycle

router = APIRouter(prefix="/api/periodization", tags=["periodization"])

_LENGTH_WEEKS_TO_DB = {
    4: DbCycleLength.FOUR_WEEKS,
    6: DbCycleLength.SIX_WEEKS,
    8: DbCycleLength.EIGHT_WEEKS,
}
_DB_LENGTH_TO_WEEKS = {v: k for k, v in _LENGTH_WEEKS_TO_DB.items()}


def load_season_from_db(club_id: uuid.UUID, db: Session) -> tuple[Season, list[uuid.UUID]]:
    """Reconstructs a Season (all of the club's cycles, chronologically) from
    training_cycles/training_cycle_weeks, DB rows -> service dataclasses. The
    club's DB is_active flag is deliberately ignored here — which cycle/week
    counts as active is always recomputed dynamically from dates (see
    Season.get_active_cycle_and_week's docstring), never trusted from a
    static column. Returns the Season alongside a parallel list of each
    cycle's DB id (same order as season.cycles), so callers can tell whether
    queue_next_cycle() appended a brand new cycle or overwrote the existing
    last one, and persist accordingly."""
    db_cycles = db.scalars(
        select(DbTrainingCycle).where(DbTrainingCycle.club_id == club_id).order_by(DbTrainingCycle.start_date)
    ).all()
    season = Season(name="Season")
    cycle_db_ids: list[uuid.UUID] = []
    for db_cycle in db_cycles:
        week_rows = db.scalars(
            select(DbTrainingCycleWeek)
            .where(DbTrainingCycleWeek.training_cycle_id == db_cycle.id)
            .order_by(DbTrainingCycleWeek.week_number)
        ).all()
        season.cycles.append(
            ServiceTrainingCycle(
                name=db_cycle.name,
                length_weeks=_DB_LENGTH_TO_WEEKS[db_cycle.length_type],
                start_date=db_cycle.start_date,
                target_match_date=db_cycle.target_match_date,
                weeks=[
                    ServiceCycleWeek(
                        week_number=w.week_number,
                        week_start_date=w.week_start_date,
                        focus=ServiceWeekFocus(w.focus.value),
                        planned_load_pct=float(w.planned_load_pct or 0),
                    )
                    for w in week_rows
                ],
                shift_count=db_cycle.shift_count,
            )
        )
        cycle_db_ids.append(db_cycle.id)
    return season, cycle_db_ids


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
        target_match_date=cycle.target_match_date,
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


@router.post("/cycles/queue-next", response_model=TrainingCycleSchema)
def queue_next_cycle_endpoint(
    payload: QueueNextCycleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """De weekselector: stelt de eerstvolgende cyclus in zonder de actieve,
    lopende cyclus aan te raken. Een tweede aanroep terwijl de actieve cyclus
    nog loopt overschrijft de klaargezette (nog niet gestarte) volgende
    cyclus — geen 400 meer, want van gedachte veranderen over een cyclus die
    nog niet gestart is, is geen foutgeval (zie services.periodization.
    queue_next_cycle's docstring)."""
    today = date.today()
    season, cycle_db_ids = load_season_from_db(current_user.club_id, db)
    cycles_before = len(season.cycles)

    try:
        result = svc_queue_next_cycle(
            season,
            length_weeks=payload.length_weeks,
            target_match_date=payload.target_match_date,
            today=today,
            target_peak_weekly_km=payload.target_peak_weekly_km,
            name=payload.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if len(season.cycles) > cycles_before:
        db_cycle = DbTrainingCycle(
            club_id=current_user.club_id,
            name=result.name,
            length_type=_LENGTH_WEEKS_TO_DB[result.length_weeks],
            start_date=result.start_date,
            end_date=result.end_date(),
            target_match_date=result.target_match_date,
            is_active=False,
            shift_count=result.shift_count,
        )
        db.add(db_cycle)
        db.flush()
    else:
        db_cycle = db.get(DbTrainingCycle, cycle_db_ids[-1])
        db_cycle.name = result.name
        db_cycle.length_type = _LENGTH_WEEKS_TO_DB[result.length_weeks]
        db_cycle.end_date = result.end_date()
        db_cycle.target_match_date = result.target_match_date
        db_cycle.shift_count = result.shift_count
        db.execute(delete(DbTrainingCycleWeek).where(DbTrainingCycleWeek.training_cycle_id == db_cycle.id))
        db.flush()

    for week in result.weeks:
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
    return TrainingCycleSchema.model_validate(result)
