from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_module
from app.models import MasTest, Match, MatchMinutes, Player
from app.models import TrainingCycle as DbTrainingCycle
from app.models import TrainingCycleWeek as DbTrainingCycleWeek
from app.models import User
from app.schemas_dashboards import (
    GenerateForMatchRequest,
    GenerateForMatchResponse,
    GenerateMakeupSchedulesRequest,
    GeneratedRunningProgramSchema,
    MissedMinutesRequest,
    MissedTrainingRequest,
    SkippedCandidate,
)
from app.schemas_matches import DEFAULT_MINUTES_BY_STATUS
from app.services.makeup_programs import (
    MINUTES_THRESHOLD_FOR_MATCH_MAKEUP,
    generate_makeup_schedules,
    generate_program_for_missed_minutes,
    generate_program_for_missed_training,
)
from app.services.periodization import CycleWeek as ServiceCycleWeek
from app.services.periodization import WeekFocus as ServiceWeekFocus
from app.services.platform_admin import ModuleKey

router = APIRouter(
    prefix="/api/makeup-programs",
    tags=["makeup-programs"],
    dependencies=[Depends(require_module(ModuleKey.MAS_COMPENSATIE))],
)


@router.post("/generate", response_model=list[GeneratedRunningProgramSchema])
def generate(payload: GenerateMakeupSchedulesRequest, current_user: User = Depends(get_current_user)):
    """De 'Maak schema's'-knop: neemt een lijst kandidaten (wedstrijdminuten of
    trainingsafwezigheid) en genereert voor elk het passende inhaalprogramma."""
    candidates = [c.model_dump() for c in payload.candidates]
    try:
        programs = generate_makeup_schedules(candidates, payload.week.to_dataclass())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [GeneratedRunningProgramSchema.model_validate(p) for p in programs]


@router.post("/generate-for-match", response_model=GenerateForMatchResponse)
def generate_for_match(
    payload: GenerateForMatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """De 'Maak schema's'-knop op het MAS-compensatiepaneel: neemt enkel een
    match_id. De actieve cyclus/week wordt hier server-side opgezocht — de
    frontend geeft geen cyclus/week mee."""
    match = db.get(Match, payload.match_id)
    if match is None or match.club_id != current_user.club_id:
        raise HTTPException(status_code=404, detail="Match not found")

    active_cycle = db.scalar(
        select(DbTrainingCycle)
        .where(DbTrainingCycle.club_id == current_user.club_id, DbTrainingCycle.is_active.is_(True))
        .order_by(DbTrainingCycle.created_at.desc())
    )
    if active_cycle is None:
        raise HTTPException(
            status_code=400,
            detail="Geen actieve trainingscyclus gevonden. Maak eerst een cyclus aan via Periodisering.",
        )

    today = date.today()
    week_row = db.scalar(
        select(DbTrainingCycleWeek).where(
            DbTrainingCycleWeek.training_cycle_id == active_cycle.id,
            DbTrainingCycleWeek.week_start_date <= today,
            DbTrainingCycleWeek.week_start_date > today - timedelta(days=7),
        )
    )
    if week_row is None:
        raise HTTPException(
            status_code=400,
            detail="Geen cyclusweek gevonden voor vandaag binnen de actieve cyclus.",
        )

    service_week = ServiceCycleWeek(
        week_number=week_row.week_number,
        week_start_date=week_row.week_start_date,
        focus=ServiceWeekFocus(week_row.focus.value),
        planned_load_pct=float(week_row.planned_load_pct or 0),
    )

    players = db.scalars(
        select(Player).where(Player.club_id == current_user.club_id, Player.is_active.is_(True))
    ).all()
    minutes_rows = {
        mm.player_id: mm
        for mm in db.scalars(select(MatchMinutes).where(MatchMinutes.match_id == match.id)).all()
    }

    candidates = []
    skipped: list[SkippedCandidate] = []
    for player in players:
        existing = minutes_rows.get(player.id)
        minutes_played = existing.minutes_played if existing else DEFAULT_MINUTES_BY_STATUS["basis"]
        if minutes_played >= MINUTES_THRESHOLD_FOR_MATCH_MAKEUP:
            continue

        latest_mas = db.scalar(
            select(MasTest).where(MasTest.player_id == player.id).order_by(MasTest.test_date.desc()).limit(1)
        )
        if latest_mas is None:
            skipped.append(
                SkippedCandidate(
                    player_name=f"{player.first_name} {player.last_name}",
                    reason="Geen MAS-test beschikbaar",
                )
            )
            continue

        candidates.append(
            {
                "player_name": f"{player.first_name} {player.last_name}",
                "mas_kmh": float(latest_mas.mas_kmh),
                "reason": "match_minutes",
                "minutes_played": minutes_played,
                "opponent_label": match.opponent,
            }
        )

    try:
        programs = generate_makeup_schedules(candidates, service_week)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return GenerateForMatchResponse(
        context_label=f"Wedstrijd vs {match.opponent} — cyclusweek {week_row.week_number} ({service_week.focus.value})",
        programs=[GeneratedRunningProgramSchema.model_validate(p) for p in programs],
        skipped=skipped,
    )


@router.post("/missed-minutes", response_model=GeneratedRunningProgramSchema)
def missed_minutes(payload: MissedMinutesRequest, current_user: User = Depends(get_current_user)):
    try:
        program = generate_program_for_missed_minutes(
            player_name=payload.player_name,
            mas_kmh=payload.mas_kmh,
            minutes_played=payload.minutes_played,
            week_focus=payload.week_focus,
            opponent_label=payload.opponent_label,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GeneratedRunningProgramSchema.model_validate(program)


@router.post("/missed-training", response_model=GeneratedRunningProgramSchema)
def missed_training(payload: MissedTrainingRequest, current_user: User = Depends(get_current_user)):
    try:
        program = generate_program_for_missed_training(
            player_name=payload.player_name,
            mas_kmh=payload.mas_kmh,
            week=payload.week.to_dataclass(),
            training_date_label=payload.training_date_label,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GeneratedRunningProgramSchema.model_validate(program)
