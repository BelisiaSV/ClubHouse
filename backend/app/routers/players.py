from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RPE, Match, Player
from app.schemas import MatchCreate, MatchOut, PlayerCreate, PlayerOut, RPECreate, RPEOut

router = APIRouter(prefix="/api", tags=["players"])


@router.post("/players", response_model=PlayerOut, status_code=201)
def create_player(payload: PlayerCreate, db: Session = Depends(get_db)):
    player = Player(**payload.model_dump())
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


@router.get("/players", response_model=list[PlayerOut])
def list_players(db: Session = Depends(get_db)):
    return db.scalars(select(Player)).all()


@router.get("/players/{player_id}", response_model=PlayerOut)
def get_player(player_id: int, db: Session = Depends(get_db)):
    player = db.get(Player, player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


@router.post("/matches", response_model=MatchOut, status_code=201)
def create_match(payload: MatchCreate, db: Session = Depends(get_db)):
    if db.get(Player, payload.player_id) is None:
        raise HTTPException(status_code=404, detail="Player not found")
    match = Match(**payload.model_dump())
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


@router.post("/rpe", response_model=RPEOut, status_code=201)
def create_rpe(payload: RPECreate, db: Session = Depends(get_db)):
    if db.get(Player, payload.player_id) is None:
        raise HTTPException(status_code=404, detail="Player not found")
    entry = RPE(**payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/rpe/{player_id}", response_model=list[RPEOut])
def list_rpe(player_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(RPE).where(RPE.player_id == player_id)).all()
