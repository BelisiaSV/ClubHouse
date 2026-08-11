import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import TrainingSession as DbTrainingSession
from app.models import User
from app.schemas_dashboards import (
    DryRunTopupRequest,
    DryRunTopUpSchema,
    PlayerFlagSchema,
    RecalculateCompositionRequest,
    RecalculateCompositionResponse,
    SessionCompositionProposalSchema,
    SessionCompositionRequest,
    VormTargetRequest,
    VormTargetSchema,
)
from app.services.periodization import WeekFocus as ServiceWeekFocus
from app.services.session_composition import (
    VormTarget,
    calculate_vorm_target,
    propose_optional_dry_running_topup,
    propose_session_composition,
    summarize_composition,
)
from app.services.team_readiness import PlayerFlag

router = APIRouter(prefix="/api/training-sessions", tags=["training-sessions"])


def _get_session_or_404(session_id: uuid.UUID, current_user: User, db: Session) -> DbTrainingSession:
    session = db.get(DbTrainingSession, session_id)
    if session is None or session.club_id != current_user.club_id:
        raise HTTPException(status_code=404, detail="Training session not found")
    return session


def _to_player_flags(flags: list[PlayerFlagSchema] | None) -> list[PlayerFlag] | None:
    return [PlayerFlag(**f.model_dump()) for f in flags] if flags else None


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
    selecteert en een duur ingeeft. session_id dient enkel om de aanroep
    tenant-scoped te houden (404 bij een sessie van een andere club) — de
    berekening zelf gebruikt alleen vorm/duration_min/num_players uit de
    request body, niet de opgeslagen week_focus/doelen van de sessie."""
    _get_session_or_404(session_id, current_user, db)

    if payload.num_players <= 0:
        raise HTTPException(status_code=400, detail="Aantal spelers moet groter zijn dan 0.")

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
    sessie (de coach kan hier bewust een ander doel tegen afzetten)."""
    _get_session_or_404(session_id, current_user, db)

    blocks = [VormTarget(**b.model_dump()) for b in payload.blocks]
    summary = summarize_composition(
        blocks, payload.target_distance_km, player_flags=_to_player_flags(payload.player_flags)
    )
    return RecalculateCompositionResponse(**summary)


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
