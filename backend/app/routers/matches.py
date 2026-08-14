import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_module
from app.models import MasTest, Match, MatchMinutes, Player, PlayerWeeklyDistanceLog, User
from app.models import TrainingCycle as DbTrainingCycle
from app.models import TrainingCycleWeek as DbTrainingCycleWeek
from app.schemas_matches import (
    DEFAULT_MINUTES_BY_STATUS,
    MatchCreate,
    MatchOut,
    MatchPlayerRow,
    MatchPlayerUpdate,
)
from app.routers.periodization import realign_season_to_matches
from app.services.platform_admin import ModuleKey
from app.services.volume_planning import PlayerPosition as ServicePlayerPosition
from app.services.volume_planning import populate_match_distance_for_week

router = APIRouter(
    prefix="/api/matches", tags=["matches"], dependencies=[Depends(require_module(ModuleKey.KALENDER))]
)


def _get_club_match(match_id: uuid.UUID, current_user: User, db: Session) -> Match:
    match = db.get(Match, match_id)
    if match is None or match.club_id != current_user.club_id:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


def _sync_match_distance_log(match: Match, player: Player, minutes_played: int, db: Session) -> None:
    """Auto-populates player_weekly_distance_log for this (match, player) via
    services.volume_planning.populate_match_distance_for_week() — the
    background step from calculate_player_match_distance() that runs whenever
    the coach saves a player's match minutes, no separate action needed.

    Silently does nothing if the club has no active cycle, no cycle week
    covers the match date, or the player has no position set: distance
    logging is a side effect of saving minutes, never a precondition for it.
    """
    if player.position is None:
        return

    active_cycle = db.scalar(
        select(DbTrainingCycle).where(
            DbTrainingCycle.club_id == match.club_id, DbTrainingCycle.is_active.is_(True)
        )
    )
    if active_cycle is None:
        return

    match_day = match.match_date.date()
    week_row = db.scalar(
        select(DbTrainingCycleWeek).where(
            DbTrainingCycleWeek.training_cycle_id == active_cycle.id,
            DbTrainingCycleWeek.week_start_date <= match_day,
            DbTrainingCycleWeek.week_start_date > match_day - timedelta(days=7),
        )
    )
    if week_row is None:
        return

    logs = populate_match_distance_for_week(
        match_appearances=[
            {
                "player_name": f"{player.first_name} {player.last_name}",
                "position": ServicePlayerPosition(player.position.value),
                "minutes_played": minutes_played,
            }
        ],
        week_number=week_row.week_number,
    )
    # populate_match_distance_for_week skips 0-minute appearances entirely
    # (no log row), but this is a stateful upsert, not a one-off report: if a
    # previous save already logged a nonzero distance and the coach has now
    # corrected the minutes down to 0, that stale distance must be zeroed out
    # too, not left stranded in the weekly total.
    match_distance_km = logs[0].match_distance_km if logs else 0.0

    row = db.scalar(
        select(PlayerWeeklyDistanceLog).where(
            PlayerWeeklyDistanceLog.match_id == match.id, PlayerWeeklyDistanceLog.player_id == player.id
        )
    )
    if row is None:
        db.add(
            PlayerWeeklyDistanceLog(
                club_id=match.club_id,
                player_id=player.id,
                match_id=match.id,
                training_cycle_id=active_cycle.id,
                week_number=week_row.week_number,
                match_distance_km=match_distance_km,
            )
        )
    else:
        row.training_cycle_id = active_cycle.id
        row.week_number = week_row.week_number
        row.match_distance_km = match_distance_km


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

    # Auto-aligns the realization week of every cycle to the nearest real
    # match instead of the coach entering a target match date by hand — see
    # app/routers/periodization.py's realign_season_to_matches docstring.
    realign_season_to_matches(current_user.club_id, db)

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
    match = _get_club_match(match_id, current_user, db)

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

    # Background step, per calculate_player_match_distance() /
    # populate_match_distance_for_week(): auto-fills this player's estimated
    # match distance for the cycle week the match falls in. No separate coach
    # action — it rides along with the minutes save and never blocks it.
    _sync_match_distance_log(match, player, minutes_played, db)

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
