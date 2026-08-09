import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import MasTest, Match, MatchMinutes, Player, User
from app.schemas_matches import (
    DEFAULT_MINUTES_BY_STATUS,
    MatchCreate,
    MatchOut,
    MatchPlayerRow,
    MatchPlayerUpdate,
)

router = APIRouter(prefix="/api/matches", tags=["matches"])


def _get_club_match(match_id: uuid.UUID, current_user: User, db: Session) -> Match:
    match = db.get(Match, match_id)
    if match is None or match.club_id != current_user.club_id:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


@router.get("", response_model=list[MatchOut])
def list_matches(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Match).where(Match.club_id == current_user.club_id).order_by(Match.match_date.desc())
    ).all()


@router.post("", response_model=MatchOut, status_code=201)
def create_match(
    payload: MatchCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    match = Match(club_id=current_user.club_id, **payload.model_dump())
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


@router.get("/{match_id}/players", response_model=list[MatchPlayerRow])
def get_match_players(
    match_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _get_club_match(match_id, current_user, db)

    players = db.scalars(
        select(Player)
        .where(Player.club_id == current_user.club_id, Player.is_active.is_(True))
        .order_by(Player.jersey_number.nulls_last())
    ).all()

    existing_rows = {
        mm.player_id: mm
        for mm in db.scalars(select(MatchMinutes).where(MatchMinutes.match_id == match_id)).all()
    }

    rows = []
    for player in players:
        latest_mas = db.scalar(
            select(MasTest)
            .where(MasTest.player_id == player.id)
            .order_by(MasTest.test_date.desc())
            .limit(1)
        )
        existing = existing_rows.get(player.id)
        rows.append(
            MatchPlayerRow(
                player_id=player.id,
                first_name=player.first_name,
                last_name=player.last_name,
                jersey_number=player.jersey_number,
                mas_kmh=float(latest_mas.mas_kmh) if latest_mas else None,
                selection_status=existing.selection_status if existing else "basis",
                minutes_played=existing.minutes_played if existing else DEFAULT_MINUTES_BY_STATUS["basis"],
            )
        )
    return rows


@router.patch("/{match_id}/players/{player_id}", response_model=MatchPlayerRow)
def update_match_player(
    match_id: uuid.UUID,
    player_id: uuid.UUID,
    payload: MatchPlayerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_club_match(match_id, current_user, db)

    player = db.get(Player, player_id)
    if player is None or player.club_id != current_user.club_id:
        raise HTTPException(status_code=404, detail="Player not found")

    minutes_played = payload.minutes_played
    if minutes_played is None:
        minutes_played = DEFAULT_MINUTES_BY_STATUS[payload.selection_status]

    row = db.scalar(
        select(MatchMinutes).where(MatchMinutes.match_id == match_id, MatchMinutes.player_id == player_id)
    )
    if row is None:
        row = MatchMinutes(
            match_id=match_id,
            player_id=player_id,
            club_id=current_user.club_id,
            selection_status=payload.selection_status,
            minutes_played=minutes_played,
            started_match=payload.selection_status == "basis",
        )
        db.add(row)
    else:
        row.selection_status = payload.selection_status
        row.minutes_played = minutes_played
        row.started_match = payload.selection_status == "basis"

    db.commit()

    latest_mas = db.scalar(
        select(MasTest).where(MasTest.player_id == player_id).order_by(MasTest.test_date.desc()).limit(1)
    )
    return MatchPlayerRow(
        player_id=player.id,
        first_name=player.first_name,
        last_name=player.last_name,
        jersey_number=player.jersey_number,
        mas_kmh=float(latest_mas.mas_kmh) if latest_mas else None,
        selection_status=row.selection_status,
        minutes_played=row.minutes_played,
    )
