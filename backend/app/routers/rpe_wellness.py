from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_module
from app.models import Club, Match, Player, User
from app.models import RpeWellnessData as DbRpeWellnessData
from app.schemas import RpeWellnessCreate, RpeWellnessOut, SessionDayOut
from app.services.platform_admin import ModuleKey
from app.services.rpe_wellness import is_session_day

router = APIRouter(
    prefix="/api/rpe-wellness", tags=["rpe-wellness"], dependencies=[Depends(require_module(ModuleKey.SQUAD_OVERVIEW))]
)


@router.get("/should-prompt", response_model=SessionDayOut)
def should_prompt(
    target_date: date = Query(default_factory=date.today, alias="date"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Whether the RPE/wellness form should be shown for `date` (defaults to
    today) — only on days with a scheduled training or match, per the
    questionnaire's "enquêtemoeheid" note. Training days come from
    Club.training_weekdays (unset means no recurring schedule configured
    yet, so only match days count); match days from any Match on that date,
    scheduled or already played."""
    club = db.get(Club, current_user.club_id)
    match_dates = db.scalars(
        select(Match.match_date).where(Match.club_id == current_user.club_id)
    ).all()
    result = is_session_day(target_date, club.training_weekdays, [d.date() for d in match_dates])
    return SessionDayOut(date=target_date, is_session_day=result.is_session_day, reason=result.reason)


@router.post("", response_model=RpeWellnessOut, status_code=201)
def record_rpe_wellness(
    payload: RpeWellnessCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Not restricted to session days server-side — should-prompt only
    gates when the UI *offers* the form, a coach backfilling a missed entry
    is still a legitimate write."""
    player = db.get(Player, payload.player_id)
    if player is None or player.club_id != current_user.club_id:
        raise HTTPException(status_code=404, detail="Player not found")

    entry = DbRpeWellnessData(club_id=current_user.club_id, **payload.model_dump())
    db.add(entry)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Er bestaat al een invoer voor deze speler, datum en sessietype.",
        ) from exc
    db.refresh(entry)
    return entry
