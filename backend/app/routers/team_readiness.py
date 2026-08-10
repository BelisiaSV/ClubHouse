from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import TrainingSession as DbTrainingSession
from app.models import User
from app.models import WeekFocus as DbWeekFocus
from app.schemas_dashboards import (
    FlagPlayersRequest,
    PlayerFlagSchema,
    ProposeTrainingRequest,
    TrainingProposalSchema,
)
from app.services.team_readiness import flag_players, propose_next_training

router = APIRouter(prefix="/api/team-readiness", tags=["team-readiness"])


@router.post("/flags", response_model=list[PlayerFlagSchema])
def flags(payload: FlagPlayersRequest, current_user: User = Depends(get_current_user)):
    players = [p.to_dataclass() for p in payload.players]
    result = flag_players(players)
    return [PlayerFlagSchema.model_validate(f) for f in result]


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
