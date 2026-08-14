from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_module
from app.models import Club
from app.models import Match as DbMatch
from app.models import MatchStatus as DbMatchStatus
from app.models import TrainingSession as DbTrainingSession
from app.models import User
from app.models import WeekFocus as DbWeekFocus
from app.routers._readiness import load_squad_readiness
from app.routers.periodization import load_season_from_db
from app.schemas_dashboards import (
    FlagPlayersRequest,
    NextSessionSchema,
    NextTrainingOverviewSchema,
    PlayerFlagSchema,
    ProposeTrainingAutoRequest,
    ProposeTrainingRequest,
    TrainingProposalSchema,
)
from app.services.periodization import get_active_cycle_and_week
from app.services.platform_admin import ModuleKey
from app.services.rpe_wellness import is_session_day
from app.services.team_readiness import flag_players, propose_next_training, propose_training_week

router = APIRouter(
    prefix="/api/team-readiness",
    tags=["team-readiness"],
    dependencies=[Depends(require_module(ModuleKey.NEXT_TRAINING))],
)

# Flags that mean "this player needs attention right now" for the Next
# Training tile — deliberately excludes "underload" (that's a Squad Overview
# 'reductie' signal, not a load-management concern for the coach today).
ATTENTION_FLAG_TYPES = {"overload", "poor_recovery", "acwr_trending_up", "injured"}

_NL_WEEKDAYS_SHORT = ["ma", "di", "wo", "do", "vr", "za", "zo"]
_NL_MONTHS_SHORT = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


def _format_nl_date_short(d: date) -> str:
    return f"{_NL_WEEKDAYS_SHORT[d.weekday()]} {d.day} {_NL_MONTHS_SHORT[d.month - 1]}"


@router.get("/overview", response_model=NextTrainingOverviewSchema)
def overview(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Data for the four Next Training status tiles:
    - squad_count: every player in the club (same set Squad Overview shows).
    - flagged_count: players carrying at least one ATTENTION_FLAG_TYPES flag,
      using the exact same flag_players() run as Squad Overview (via
      load_squad_readiness) so the two counts never drift apart.
    - sessions_this_week: num_trainings + num_matches of the active cycle's
      current week (see services.periodization.get_active_cycle_and_week) —
      0 if no cycle is active right now.
    - next_session: the next training/match day from today onward (club's
      configured training_weekdays + real Match rows, via
      services.rpe_wellness.is_session_day, same source the RPE/wellness
      day-gate uses) — looks up to 3 weeks ahead, which comfortably covers
      "later this week" or "next week's first training"."""
    squad = load_squad_readiness(current_user.club_id, db)
    flagged_count = sum(1 for sr in squad if any(f.flag_type in ATTENTION_FLAG_TYPES for f in sr.flags))

    today = date.today()
    season, _ = load_season_from_db(current_user.club_id, db)
    active_cycle, active_week = get_active_cycle_and_week(season, today)
    sessions_this_week = (active_week.num_trainings + active_week.num_matches) if active_week else 0

    club = db.get(Club, current_user.club_id)
    match_dates = [
        d.date()
        for d in db.scalars(
            select(DbMatch.match_date).where(
                DbMatch.club_id == current_user.club_id,
                DbMatch.status.in_([DbMatchStatus.SCHEDULED, DbMatchStatus.PLAYED]),
            )
        ).all()
    ]

    next_session = None
    for offset in range(21):
        candidate = today + timedelta(days=offset)
        result = is_session_day(candidate, club.training_weekdays, match_dates)
        if result.is_session_day:
            next_session = NextSessionSchema(
                session_type="match" if result.reason == "match" else "training",
                session_date=candidate,
                label=_format_nl_date_short(candidate),
            )
            break

    return NextTrainingOverviewSchema(
        squad_count=len(squad),
        flagged_count=flagged_count,
        sessions_this_week=sessions_this_week,
        week_focus=active_week.focus if active_week else None,
        next_session=next_session,
    )


@router.post("/flags", response_model=list[PlayerFlagSchema])
def flags(payload: FlagPlayersRequest, current_user: User = Depends(get_current_user)):
    players = [p.to_dataclass() for p in payload.players]
    result = flag_players(players)
    return [PlayerFlagSchema.model_validate(f) for f in result]


@router.post("/propose-training/auto", response_model=TrainingProposalSchema)
def propose_training_auto(
    payload: ProposeTrainingAutoRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """DB-backed convenience wrapper around propose_next_training() for the
    Next Training page: loads the active cycle/week and every player's real
    readiness (via load_squad_readiness — the same shared helper Squad
    Overview and the /overview tiles use) instead of requiring the frontend
    to assemble and send that data itself, the way POST .../propose-training
    (the pure, bring-your-own-data version) does.

    Players with no wellness entries yet are left out of the readiness
    calculation (there's no basis for a PlayerReadiness for them, same
    'geen_data' reasoning as Squad Overview) — they just don't get an
    individual load_adjustment_factor applied."""
    today = date.today()
    season, _ = load_season_from_db(current_user.club_id, db)
    _, active_week = get_active_cycle_and_week(season, today)
    if active_week is None:
        raise HTTPException(status_code=404, detail="Geen actieve cyclus/week gevonden.")

    squad = load_squad_readiness(current_user.club_id, db)
    players = [sr.readiness for sr in squad if sr.readiness is not None]

    proposal = propose_next_training(week=active_week, players=players, km_per_training=payload.km_per_training)

    db_session = DbTrainingSession(
        club_id=current_user.club_id,
        week_focus=DbWeekFocus(proposal.week_focus.value),
        target_duration_min=proposal.adjusted_duration_min,
        target_distance_km=proposal.adjusted_distance_km,
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    return TrainingProposalSchema.model_validate(proposal).model_copy(update={"session_id": db_session.id})


@router.post("/propose-week", response_model=list[TrainingProposalSchema])
def propose_week(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """De volledig automatische Next Training-ketting: de coach hoeft enkel
    het aantal aanwezige spelers per gekozen sessie op te geven (later, aan
    propose_session_composition() — zie app/routers/training_sessions.py),
    niets hier. Genereert ÉÉN voorstel per training van de actieve week
    (propose_training_week, op basis van de echte teamreadiness via
    load_squad_readiness) en persisteert elk meteen als een eigen
    TrainingSession-rij, zodat de coach voor elke sessie afzonderlijk verder
    kan met de oefenvormen."""
    today = date.today()
    season, _ = load_season_from_db(current_user.club_id, db)
    squad = load_squad_readiness(current_user.club_id, db)
    players = [sr.readiness for sr in squad if sr.readiness is not None]

    try:
        proposals = propose_training_week(season, players, today)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    schemas = []
    for proposal in proposals:
        db_session = DbTrainingSession(
            club_id=current_user.club_id,
            week_focus=DbWeekFocus(proposal.week_focus.value),
            target_duration_min=proposal.adjusted_duration_min,
            target_distance_km=proposal.adjusted_distance_km,
        )
        db.add(db_session)
        db.flush()
        schemas.append(TrainingProposalSchema.model_validate(proposal).model_copy(update={"session_id": db_session.id}))
    db.commit()

    return schemas


@router.post("/propose-training", response_model=TrainingProposalSchema)
def propose_training(
    payload: ProposeTrainingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    players = [p.to_dataclass() for p in payload.players]
    proposal = propose_next_training(
        week=payload.week.to_dataclass(),
        players=players,
        km_per_training=payload.km_per_training,
    )

    # Persisted so the coach can act on this exact proposal in follow-up
    # requests (composition-proposal / vorm-target, see
    # app/routers/training_sessions.py) by id instead of re-sending it.
    db_session = DbTrainingSession(
        club_id=current_user.club_id,
        week_focus=DbWeekFocus(proposal.week_focus.value),
        target_duration_min=proposal.adjusted_duration_min,
        target_distance_km=proposal.adjusted_distance_km,
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    return TrainingProposalSchema.model_validate(proposal).model_copy(update={"session_id": db_session.id})
