import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import TrainingSession as DbTrainingSession
from app.models import User
from app.schemas_dashboards import (
    SessionCompositionProposalSchema,
    SessionCompositionRequest,
    VormTargetRequest,
    VormTargetSchema,
)
from app.services.periodization import WeekFocus as ServiceWeekFocus
from app.services.session_composition import calculate_vorm_target, propose_session_composition

router = APIRouter(prefix="/api/training-sessions", tags=["training-sessions"])


def _get_session_or_404(session_id: uuid.UUID, current_user: User, db: Session) -> DbTrainingSession:
    session = db.get(DbTrainingSession, session_id)
    if session is None or session.club_id != current_user.club_id:
        raise HTTPException(status_code=404, detail="Training session not found")
    return session


def _composition_proposal(session: DbTrainingSession, num_players: int) -> SessionCompositionProposalSchema:
    try:
        result = propose_session_composition(
            week_focus=ServiceWeekFocus(session.week_focus.value),
            num_players=num_players,
            target_duration_min=float(session.target_duration_min),
            target_distance_km=float(session.target_distance_km),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SessionCompositionProposalSchema.model_validate(result)


@router.get("/{session_id}/composition-proposal", response_model=SessionCompositionProposalSchema)
def composition_proposal_get(
    session_id: uuid.UUID,
    num_players: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(session_id, current_user, db)
    return _composition_proposal(session, num_players)


@router.post("/{session_id}/composition-proposal", response_model=SessionCompositionProposalSchema)
def composition_proposal_post(
    session_id: uuid.UUID,
    payload: SessionCompositionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(session_id, current_user, db)
    return _composition_proposal(session, payload.num_players)


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
