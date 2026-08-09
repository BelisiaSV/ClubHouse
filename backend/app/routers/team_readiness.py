from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.models import User
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
def propose_training(payload: ProposeTrainingRequest, current_user: User = Depends(get_current_user)):
    players = [p.to_dataclass() for p in payload.players]
    proposal = propose_next_training(
        week=payload.week.to_dataclass(),
        players=players,
        km_per_training=payload.km_per_training,
    )
    return TrainingProposalSchema.model_validate(proposal)
