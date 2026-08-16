import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_module
from app.models import Match as DbMatch
from app.models import Player as DbPlayer
from app.models import PlayerTrainingDistanceLog as DbPlayerTrainingDistanceLog
from app.models import RpeWellnessData as DbRpeWellnessData
from app.models import TrainingSession as DbTrainingSession
from app.models import User
from app.schemas_dashboards import (
    DryRunTopupRequest,
    DryRunTopUpSchema,
    FinalizeSessionRequest,
    OefenvormLibraryEntrySchema,
    PlayerFlagSchema,
    RecalculateCompositionRequest,
    RecalculateCompositionResponse,
    RecentSessionSchema,
    SessionCompositionProposalSchema,
    SessionCompositionRequest,
    TrainingSessionDetailSchema,
    VormTargetRequest,
    VormTargetSchema,
)
from app.services.periodization import WeekFocus as ServiceWeekFocus
from app.services.platform_admin import ModuleKey
from app.services.session_composition import (
    OEFENVORM_LIBRARY,
    VormTarget,
    calculate_vorm_target,
    calculate_vorm_target_by_reps,
    propose_optional_dry_running_topup,
    propose_session_composition,
    remove_skipped_blocks,
    summarize_composition,
)
from app.services.team_readiness import PlayerFlag
from app.services.volume_planning import PlayerPosition as ServicePlayerPosition
from app.services.volume_planning import split_training_distance_across_squad

router = APIRouter(
    prefix="/api/training-sessions",
    tags=["training-sessions"],
    dependencies=[Depends(require_module(ModuleKey.NEXT_TRAINING))],
)


def _get_session_or_404(session_id: uuid.UUID, current_user: User, db: Session) -> DbTrainingSession:
    session = db.get(DbTrainingSession, session_id)
    if session is None or session.club_id != current_user.club_id:
        raise HTTPException(status_code=404, detail="Training session not found")
    return session


_NL_WEEKDAYS_FULL = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"]

# Short display labels for the "Recente sessies" Type column (e.g. "Balbezit
# + MSG") — OEFENVORM_LIBRARY's own labels are the full descriptive ones
# (e.g. "Medium-sided game (6v6-7v7)"), too long for a table cell.
SHORT_VORM_LABELS = {
    "pas_en_trap": "Pass & trap", "balbezit": "Balbezit", "transitie": "Transitie",
    "ssg": "SSG", "msg": "MSG", "lsg": "LSG", "afwerking": "Afwerking", "patroon": "Patroon",
}


def _session_label(session_date: date, match_dates: set) -> str:
    if session_date in match_dates:
        return "Wedstrijd"
    return _NL_WEEKDAYS_FULL[session_date.weekday()]


def _type_summary(blocks: list) -> str:
    labels = dict.fromkeys(SHORT_VORM_LABELS.get(b.get("vorm"), b.get("vorm", "?")) for b in blocks)
    return " + ".join(labels) if labels else "—"


def _to_detail_schema(session: DbTrainingSession) -> TrainingSessionDetailSchema:
    blocks = session.blocks or []
    return TrainingSessionDetailSchema(
        id=session.id,
        week_focus=ServiceWeekFocus(session.week_focus.value),
        session_date=session.session_date,
        target_duration_min=float(session.target_duration_min),
        target_distance_km=float(session.target_distance_km),
        blocks=blocks,
        skipped_vormen=session.skipped_vormen or [],
        total_distance_km=round(sum(b.get("distance_km", 0) for b in blocks), 2),
        total_work_duration_min=round(sum(b.get("duration_min", 0) for b in blocks), 1),
        finalized_at=session.finalized_at,
    )


def _to_player_flags(flags: list[PlayerFlagSchema] | None) -> list[PlayerFlag] | None:
    return [PlayerFlag(**f.model_dump()) for f in flags] if flags else None


def _sync_player_training_distance_log(session: DbTrainingSession, club_id: uuid.UUID, db: Session) -> None:
    """Splits a just-finalized session's team-total distance across the
    active squad (services.volume_planning.split_training_distance_across_squad)
    and upserts one player_training_distance_log row per player — see that
    table's docstring for why this is a position-weighted estimate rather
    than real per-player attendance/GPS data. Delete-then-recreate rather
    than a true upsert since finalize_session can in principle be called
    again on the same session (re-finalizing), and the squad or blocks may
    have changed since the first call."""
    db.execute(
        delete(DbPlayerTrainingDistanceLog).where(
            DbPlayerTrainingDistanceLog.training_session_id == session.id
        )
    )
    if session.session_date is None:
        return

    team_total_distance_km = round(sum(b.get("distance_km", 0) for b in (session.blocks or [])), 2)
    if team_total_distance_km <= 0:
        return

    players = db.scalars(
        select(DbPlayer).where(DbPlayer.club_id == club_id, DbPlayer.is_active.is_(True))
    ).all()
    if not players:
        return

    shares = split_training_distance_across_squad(
        team_total_distance_km,
        [
            {
                "player_name": p.id,
                "position": ServicePlayerPosition(p.position.value) if p.position else None,
            }
            for p in players
        ],
    )
    for player in players:
        db.add(
            DbPlayerTrainingDistanceLog(
                club_id=club_id,
                player_id=player.id,
                training_session_id=session.id,
                session_date=session.session_date,
                training_distance_km=shares.get(player.id, 0.0),
            )
        )


def _composition_proposal(
    session: DbTrainingSession,
    num_players: int,
    team_avg_mas_kmh: float | None,
    player_flags: list[PlayerFlagSchema] | None,
) -> SessionCompositionProposalSchema:
    try:
        result = propose_session_composition(
            week_focus=ServiceWeekFocus(session.week_focus.value),
            num_players=num_players,
            target_duration_min=float(session.target_duration_min),
            target_distance_km=float(session.target_distance_km),
            team_avg_mas_kmh=team_avg_mas_kmh,
            player_flags=_to_player_flags(player_flags),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SessionCompositionProposalSchema.model_validate(result)


@router.get("/vormen", response_model=list[OefenvormLibraryEntrySchema])
def list_vormen(current_user: User = Depends(get_current_user)):
    """De volledige oefenvormenbibliotheek (OEFENVORM_LIBRARY), voor de
    'blok toevoegen'-picker op Next Training: welke vormen bestaan er, en is
    het een partijvorm (enkel num_bouts instelbaar) of een continue vorm
    (enkel duration_min instelbaar) — single source of truth blijft de
    backend, niet hardcoded in de frontend."""
    return [
        OefenvormLibraryEntrySchema(
            vorm=vorm.value,
            label=profile.label,
            is_bout_vorm=profile.bout_duration_min is not None,
            bout_duration_min=profile.bout_duration_min,
        )
        for vorm, profile in OEFENVORM_LIBRARY.items()
    ]


@router.get("/{session_id}/composition-proposal", response_model=SessionCompositionProposalSchema)
def composition_proposal_get(
    session_id: uuid.UUID,
    num_players: int = Query(...),
    team_avg_mas_kmh: float | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """player_flags isn't accepted here — a list of objects doesn't fit a
    query string cleanly, and POST's JSON body is where structured input
    like that belongs. GET stays for the simple num_players (+ optional
    team_avg_mas_kmh) case."""
    session = _get_session_or_404(session_id, current_user, db)
    return _composition_proposal(session, num_players, team_avg_mas_kmh, None)


@router.post("/{session_id}/composition-proposal", response_model=SessionCompositionProposalSchema)
def composition_proposal_post(
    session_id: uuid.UUID,
    payload: SessionCompositionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(session_id, current_user, db)
    return _composition_proposal(session, payload.num_players, payload.team_avg_mas_kmh, payload.player_flags)


@router.post("/{session_id}/vorm-target", response_model=VormTargetSchema)
def vorm_target(
    session_id: uuid.UUID,
    payload: VormTargetRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Wordt aangeroepen telkens de coach een vorm uit het keuzemenu
    selecteert. Partijvormen (SSG/MSG/LSG/transitie) zijn voortaan enkel
    aanpasbaar via num_bouts — de bloktijd zelf ligt wetenschappelijk vast
    en is nooit instelbaar (calculate_vorm_target_by_reps); continue vormen
    blijven ongewijzigd via duration_min lopen (calculate_vorm_target).
    session_id dient enkel om de aanroep tenant-scoped te houden — de
    berekening zelf gebruikt alleen de request body."""
    _get_session_or_404(session_id, current_user, db)

    profile = OEFENVORM_LIBRARY.get(payload.vorm)
    if profile is None:
        raise HTTPException(status_code=400, detail=f"Onbekende oefenvorm: {payload.vorm}")

    is_bout_vorm = profile.bout_duration_min is not None

    if is_bout_vorm:
        if payload.duration_min is not None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{profile.label} is een partijvorm — de bloktijd ligt vast, "
                    f"geef num_bouts op i.p.v. duration_min."
                ),
            )
        if payload.num_bouts is None:
            raise HTTPException(status_code=400, detail="num_bouts is verplicht voor deze partijvorm.")
        try:
            result = calculate_vorm_target_by_reps(payload.vorm, payload.num_bouts, payload.num_players)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        if payload.num_bouts is not None:
            raise HTTPException(
                status_code=400,
                detail=f"{profile.label} is een continue vorm zonder bout-structuur — geef duration_min op i.p.v. num_bouts.",
            )
        if payload.duration_min is None:
            raise HTTPException(status_code=400, detail="duration_min is verplicht voor deze vorm.")
        try:
            result = calculate_vorm_target(payload.vorm, payload.duration_min, payload.num_players)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return VormTargetSchema.model_validate(result)


@router.post("/{session_id}/recalculate", response_model=RecalculateCompositionResponse)
def recalculate(
    session_id: uuid.UUID,
    payload: RecalculateCompositionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Telt een (mogelijk door de coach handmatig aangepaste) blokkenlijst
    opnieuw op tegen het meegegeven sessiedoel. session_id dient enkel om de
    aanroep tenant-scoped te houden — net als vorm-target gebruikt de
    berekening zelf alleen de request body, niet de opgeslagen doelen van de
    sessie (de coach kan hier bewust een ander doel tegen afzetten).

    skip_vormen: vormen die de coach op 0' zette om ze over te slaan — worden
    via remove_skipped_blocks() UIT de blokkenlijst gehaald vóór het optellen,
    nooit als een 0-waarde blok doorgegeven."""
    _get_session_or_404(session_id, current_user, db)

    blocks = [VormTarget(**b.model_dump()) for b in payload.blocks]
    blocks = remove_skipped_blocks(blocks, payload.skip_vormen)
    summary = summarize_composition(
        blocks, payload.target_distance_km, player_flags=_to_player_flags(payload.player_flags)
    )
    return RecalculateCompositionResponse(**summary)


@router.post("/{session_id}/finalize", response_model=TrainingSessionDetailSchema)
def finalize_session(
    session_id: uuid.UUID,
    payload: FinalizeSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Persisteert de definitieve sessie-invulling — de (reeds skip-
    gefilterde) blokkenlijst plus welke vormen de coach oversloeg — zodat
    GET /recent en GET /{session_id} exact tonen wat er toen effectief
    ingevuld werd, niet het oorspronkelijke voorstel."""
    session = _get_session_or_404(session_id, current_user, db)
    session.session_date = payload.session_date
    session.blocks = [b.model_dump() for b in payload.blocks]
    session.skipped_vormen = payload.skip_vormen or []
    session.finalized_at = datetime.now(timezone.utc)
    db.flush()
    _sync_player_training_distance_log(session, current_user.club_id, db)
    db.commit()
    db.refresh(session)
    return _to_detail_schema(session)


@router.get("/recent", response_model=list[RecentSessionSchema])
def recent_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Voor de 'Recente sessies'-tabel: enkel GEFINALISEERDE sessies (waar de
    coach effectief 'Sessie afronden' heeft geklikt), meest recente eerst."""
    sessions = db.scalars(
        select(DbTrainingSession)
        .where(DbTrainingSession.club_id == current_user.club_id, DbTrainingSession.finalized_at.isnot(None))
        .order_by(DbTrainingSession.session_date.desc())
        .limit(limit)
    ).all()
    if not sessions:
        return []

    session_dates = [s.session_date for s in sessions]
    match_dates = {
        d.date()
        for d in db.scalars(select(DbMatch.match_date).where(DbMatch.club_id == current_user.club_id)).all()
    }
    rpe_rows = db.execute(
        select(DbRpeWellnessData.entry_date, DbRpeWellnessData.rpe_score).where(
            DbRpeWellnessData.club_id == current_user.club_id,
            DbRpeWellnessData.entry_date.in_(session_dates),
            DbRpeWellnessData.rpe_score.isnot(None),
        )
    ).all()
    rpe_by_date: dict = {}
    for entry_date, rpe_score in rpe_rows:
        rpe_by_date.setdefault(entry_date, []).append(rpe_score)

    result = []
    for s in sessions:
        blocks = s.blocks or []
        scores = rpe_by_date.get(s.session_date)
        result.append(
            RecentSessionSchema(
                id=s.id,
                session_date=s.session_date,
                session_label=_session_label(s.session_date, match_dates),
                type_summary=_type_summary(blocks),
                total_distance_km=round(sum(b.get("distance_km", 0) for b in blocks), 2),
                team_avg_rpe=round(sum(scores) / len(scores), 1) if scores else None,
            )
        )
    return result


@router.get("/{session_id}", response_model=TrainingSessionDetailSchema)
def get_session_detail(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Volledige, opgeslagen invulling van één sessie — voor de rij-klik
    detailweergave vanuit 'Recente sessies': exact welke vormen met welke
    duur/bouts/afstand gebruikt werden, en welke vormen bewust op 0' gezet
    (overgeslagen) werden."""
    session = _get_session_or_404(session_id, current_user, db)
    return _to_detail_schema(session)


@router.delete("/{session_id}", status_code=204)
def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verwijdert een sessie volledig — zowel een afgeronde ('Recente
    sessies') als een nog niet-gefinaliseerde voorstel-rij. Niets anders
    verwijst naar training_sessions.id via een foreign key (RPE/wellness
    koppelt enkel los op datum, zie recent_sessions hierboven), dus dit is
    een simpele, veilige delete zonder cascaderende gevolgen elders."""
    session = _get_session_or_404(session_id, current_user, db)
    db.delete(session)
    db.commit()


@router.post("/dry-run-topup", response_model=DryRunTopUpSchema)
def dry_run_topup(payload: DryRunTopupRequest, current_user: User = Depends(get_current_user)):
    """Los endpoint (niet aan een session_id gekoppeld — propose_optional_
    dry_running_topup() is een pure functie van remaining_distance_km +
    team_avg_mas_kmh) voor als de coach achteraf alsnog een aanvulling wil,
    los van de automatische aanvulling die composition-proposal al kan
    teruggeven in optional_dry_run_topup."""
    try:
        result = propose_optional_dry_running_topup(payload.remaining_distance_km, payload.team_avg_mas_kmh)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DryRunTopUpSchema.model_validate(result)
