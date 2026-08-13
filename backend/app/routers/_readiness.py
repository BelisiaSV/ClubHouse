"""Shared DB-touching helper for turning a club's Player + RpeWellnessData
rows into app.services.team_readiness.PlayerReadiness objects — used by both
GET /api/players/squad-overview and GET /api/team-readiness/overview so the
two stay consistent (same flags, same status). Deliberately lives under
routers/, not services/, since it does real database access and the
services layer is meant to stay pure (see app/services/team_readiness.py's
docstring)."""

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Player
from app.models import RpeWellnessData as DbRpeWellnessData
from app.services.team_readiness import PlayerFlag, PlayerReadiness, flag_players


def _normalized_wellness(entry: DbRpeWellnessData) -> float | None:
    """Mirrors team_readiness._wellness_composite's "higher is better"
    normalization (fatigue/soreness/stress inverted via 6-x) — kept
    consistent with it so a displayed number matches the status flag_players()
    actually assigned. Null-safe since these sub-scores are all optional."""
    parts = []
    if entry.sleep_quality is not None:
        parts.append(entry.sleep_quality)
    if entry.fatigue_level is not None:
        parts.append(6 - entry.fatigue_level)
    if entry.muscle_soreness is not None:
        parts.append(6 - entry.muscle_soreness)
    if entry.stress_level is not None:
        parts.append(6 - entry.stress_level)
    if entry.mood is not None:
        parts.append(entry.mood)
    return round(sum(parts) / len(parts), 1) if parts else None


class SquadReadiness:
    """Per-player bundle: the DB row, its derived PlayerReadiness (None if no
    wellness data yet), the latest RpeWellnessData row (for display), and
    this player's flags."""

    def __init__(self, player: Player, readiness: PlayerReadiness | None, latest: DbRpeWellnessData | None):
        self.player = player
        self.readiness = readiness
        self.latest = latest
        self.flags: list[PlayerFlag] = []


def load_squad_readiness(club_id: uuid.UUID, db: Session) -> list[SquadReadiness]:
    """Builds one SquadReadiness per active player in the club, using the
    last 28 days of RpeWellnessData: acute_load_7d (this week's sum),
    chronic_load_28d (28-day sum / 4), and weekly_acute_load_history (the
    last 3 non-overlapping weekly sums, oldest first) for _acwr_trending_up().
    Players with no wellness entries yet get readiness=None (see
    app.services.rpe_wellness and squad_overview's docstring for why that's
    deliberate — no data means no basis for a status, not an assumed 'fit')."""
    players = db.scalars(
        select(Player).where(Player.club_id == club_id).order_by(Player.jersey_number.nulls_last())
    ).all()
    if not players:
        return []

    today = date.today()
    cutoff_28d = today - timedelta(days=28)
    week_bounds = [today - timedelta(days=7 * (i + 1)) for i in range(4)]  # [-7,-14,-21,-28] from today

    entries = db.scalars(
        select(DbRpeWellnessData)
        .where(DbRpeWellnessData.club_id == club_id, DbRpeWellnessData.entry_date >= cutoff_28d)
        .order_by(DbRpeWellnessData.player_id, DbRpeWellnessData.entry_date.desc())
    ).all()

    entries_by_player: dict[uuid.UUID, list[DbRpeWellnessData]] = {}
    for entry in entries:
        entries_by_player.setdefault(entry.player_id, []).append(entry)

    results: list[SquadReadiness] = []
    readiness_by_name: dict[str, PlayerReadiness] = {}
    for player in players:
        player_entries = entries_by_player.get(player.id, [])
        if not player_entries:
            results.append(SquadReadiness(player, None, None))
            continue

        latest = player_entries[0]  # already ordered newest-first
        name = f"{player.first_name} {player.last_name}"

        # Weekly buckets, oldest first: [-28,-21), [-21,-14), [-14,-7), [-7,today].
        weekly_loads = []
        for i in range(3, -1, -1):
            window_start = week_bounds[i]
            window_end = week_bounds[i - 1] if i > 0 else today + timedelta(days=1)
            weekly_loads.append(
                sum(e.session_load or 0 for e in player_entries if window_start <= e.entry_date < window_end)
            )

        readiness = PlayerReadiness(
            player_name=name,
            acute_load_7d=weekly_loads[-1],
            chronic_load_28d=sum(weekly_loads) / 4,
            sleep_quality=latest.sleep_quality or 3,
            fatigue_level=latest.fatigue_level or 3,
            muscle_soreness=latest.muscle_soreness or 3,
            stress_level=latest.stress_level or 3,
            mood=latest.mood or 3,
            injury_flag=latest.injury_flag,
            # Last 3 weekly buckets, oldest first, CURRENT WEEK LAST — matches
            # _acwr_trending_up()'s expected shape (it reads history[-1] as
            # "now", not a lagging prior week).
            weekly_acute_load_history=weekly_loads[-3:],
        )
        readiness_by_name[name] = readiness
        results.append(SquadReadiness(player, readiness, latest))

    flags_by_name: dict[str, list[PlayerFlag]] = {}
    for flag in flag_players(list(readiness_by_name.values())):
        flags_by_name.setdefault(flag.player_name, []).append(flag)

    for sr in results:
        if sr.readiness is not None:
            sr.flags = flags_by_name.get(sr.readiness.player_name, [])

    return results
