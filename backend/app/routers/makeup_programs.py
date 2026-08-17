from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_module
from app.models import MasTest, Match, MatchMinutes, Player
from app.models import User
from app.routers.periodization import load_season_from_db
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
    generate_makeup_schedules,
    generate_program_for_missed_minutes,
    generate_program_for_missed_training,
    qualifies_for_match_makeup_by_km,
)
from app.services.periodization import get_active_cycle_and_week
from app.services.platform_admin import ModuleKey
from app.services.volume_planning import PlayerPosition as ServicePlayerPosition

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

    # Dynamisch opzoeken (get_active_cycle_and_week), NOOIT de statische
    # TrainingCycle.is_active-kolom: die wordt enkel gezet op de allereerste
    # cyclus van een club (bij start_new_season()) en nooit meer bijgewerkt
    # zodra een volgende cyclus wordt klaargezet of aangepast — een club op
    # z'n tweede of latere cyclus vond hier dus altijd 0 rijen.
    today = date.today()
    season, _ = load_season_from_db(current_user.club_id, db)
    active_cycle, active_week = get_active_cycle_and_week(season, today)
    if active_cycle is None or active_week is None:
        if not season.cycles:
            detail = (
                "Geen actieve trainingscyclus gevonden: er bestaat nog geen "
                "enkele trainingscyclus voor deze club. Maak eerst een cyclus "
                "aan via Periodisering."
            )
        else:
            bestaande = "; ".join(
                f"'{c.name}' ({c.start_date.isoformat()} t/m {c.end_date().isoformat()})"
                for c in season.cycles
            )
            detail = (
                f"Geen actieve trainingscyclus gevonden voor vandaag ({today.isoformat()}). "
                f"Cycli gevonden voor deze club: {bestaande}. Vandaag valt buiten al deze "
                "periodes — pas de startdatum aan via Periodisering of maak een nieuwe cyclus aan."
            )
        raise HTTPException(status_code=400, detail=detail)

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

        if player.position is None:
            # Zonder positie kan de km-gebaseerde inhaaldrempel
            # (qualifies_for_match_makeup_by_km) niet bepaald worden — deze
            # speler wordt overgeslagen i.p.v. de hele batch te laten falen.
            skipped.append(
                SkippedCandidate(
                    player_name=f"{player.first_name} {player.last_name}",
                    reason="Geen positie ingesteld",
                )
            )
            continue
        position = ServicePlayerPosition(player.position.value)

        if not qualifies_for_match_makeup_by_km(position, minutes_played):
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
                "position": position,
                "opponent_label": match.opponent,
            }
        )

    try:
        programs = generate_makeup_schedules(candidates, active_week)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return GenerateForMatchResponse(
        context_label=f"Wedstrijd vs {match.opponent} — cyclusweek {active_week.week_number} ({active_week.focus.value})",
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
