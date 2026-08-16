"""Shared DB-touching helper for turning a club's Player + distance/RPE rows
into app.services.team_readiness.PlayerReadiness objects — used by both
GET /api/players/squad-overview and GET /api/team-readiness/overview so the
two stay consistent (same flags, same status). Deliberately lives under
routers/, not services/, since it does real database access and the
services layer is meant to stay pure (see app/services/team_readiness.py's
docstring).

KM-BASISLAAG: acute_km_7d/chronic_km_28d/weekly_acute_km_history are built
from player_weekly_distance_log (match distance, via each row's Match date)
and player_training_distance_log (training distance, already carries its
own session_date) — ALWAYS computed, for every active player, regardless of
whether they have any RPE/wellness entries. A player with genuinely zero
logged km still gets a PlayerReadiness (chronic_km_28d=0 -> _acwr_km()
returns None -> no km flag raised, exactly the existing "no basis yet"
semantics) instead of being excluded entirely — this is the fix for the old
behavior where readiness=None whenever a player had no wellness entries,
which meant a club with the RPE module off could never flag or size
training for anyone.

RPE-LAAG: only fetched/populated when rpe_module_active=True, matching
app.services.platform_admin.ModuleKey.RPE_WELLNESS being enabled for the
club — see app/routers/team_readiness.py for where that boolean comes from."""

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Match as DbMatch
from app.models import Player
from app.models import PlayerTrainingDistanceLog as DbPlayerTrainingDistanceLog
from app.models import PlayerWeeklyDistanceLog as DbPlayerWeeklyDistanceLog
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
    """Per-player bundle: the DB row, its derived PlayerReadiness (never
    None anymore — a player with zero data still gets one, see module
    docstring), the latest RpeWellnessData row if any (for display), and
    this player's flags."""

    def __init__(self, player: Player, readiness: PlayerReadiness, latest: DbRpeWellnessData | None):
        self.player = player
        self.readiness = readiness
        self.latest = latest
        self.flags: list[PlayerFlag] = []


def _weekly_buckets(entries_with_dates: list[tuple[date, float]], today: date, week_bounds: list[date]) -> list[float]:
    """entries_with_dates: [(date, km_or_load), ...]. Returns 4 buckets,
    oldest first: [-28,-21), [-21,-14), [-14,-7), [-7,today]."""
    buckets = []
    for i in range(3, -1, -1):
        window_start = week_bounds[i]
        window_end = week_bounds[i - 1] if i > 0 else today + timedelta(days=1)
        buckets.append(round(sum(v for d, v in entries_with_dates if window_start <= d < window_end), 2))
    return buckets


def load_squad_readiness(club_id: uuid.UUID, db: Session, rpe_module_active: bool = False) -> list[SquadReadiness]:
    """Builds one SquadReadiness per active player in the club.

    Km-basislaag (altijd): acute_km_7d (deze week se som), chronic_km_28d
    (28-dagen-som / 4), weekly_acute_km_history (laatste 3 wekelijkse
    sommen, oudste eerst) — opgebouwd uit match- én trainingsafstand samen.

    RPE-laag (enkel als rpe_module_active): dezelfde opbouw maar op
    RpeWellnessData.session_load, plus de wellness-subscores van de meest
    recente invoer."""
    players = db.scalars(
        select(Player).where(Player.club_id == club_id).order_by(Player.jersey_number.nulls_last())
    ).all()
    if not players:
        return []

    today = date.today()
    cutoff_28d = today - timedelta(days=28)
    week_bounds = [today - timedelta(days=7 * (i + 1)) for i in range(4)]  # [-7,-14,-21,-28] from today

    # --- Km-basislaag: match-afstand (via Match.match_date) + training-afstand ---
    match_rows = db.execute(
        select(
            DbPlayerWeeklyDistanceLog.player_id, DbMatch.match_date, DbPlayerWeeklyDistanceLog.match_distance_km
        ).join(DbMatch, DbMatch.id == DbPlayerWeeklyDistanceLog.match_id).where(
            DbPlayerWeeklyDistanceLog.club_id == club_id, DbMatch.match_date >= cutoff_28d
        )
    ).all()
    training_rows = db.execute(
        select(
            DbPlayerTrainingDistanceLog.player_id,
            DbPlayerTrainingDistanceLog.session_date,
            DbPlayerTrainingDistanceLog.training_distance_km,
        ).where(
            DbPlayerTrainingDistanceLog.club_id == club_id, DbPlayerTrainingDistanceLog.session_date >= cutoff_28d
        )
    ).all()

    km_by_player: dict[uuid.UUID, list[tuple[date, float]]] = {}
    for player_id, match_date, km in match_rows:
        km_by_player.setdefault(player_id, []).append((match_date.date(), float(km)))
    for player_id, session_date, km in training_rows:
        km_by_player.setdefault(player_id, []).append((session_date, float(km)))

    # --- RPE-laag: enkel opgehaald als de module actief is ---
    entries_by_player: dict[uuid.UUID, list[DbRpeWellnessData]] = {}
    if rpe_module_active:
        entries = db.scalars(
            select(DbRpeWellnessData)
            .where(DbRpeWellnessData.club_id == club_id, DbRpeWellnessData.entry_date >= cutoff_28d)
            .order_by(DbRpeWellnessData.player_id, DbRpeWellnessData.entry_date.desc())
        ).all()
        for entry in entries:
            entries_by_player.setdefault(entry.player_id, []).append(entry)

    results: list[SquadReadiness] = []
    readiness_by_name: dict[str, PlayerReadiness] = {}
    for player in players:
        name = f"{player.first_name} {player.last_name}"
        player_entries = entries_by_player.get(player.id, [])
        latest = player_entries[0] if player_entries else None  # already ordered newest-first

        weekly_km = _weekly_buckets(km_by_player.get(player.id, []), today, week_bounds)

        readiness_kwargs = dict(
            player_name=name,
            acute_km_7d=weekly_km[-1],
            chronic_km_28d=round(sum(weekly_km) / 4, 2),
            # Last 3 weekly buckets, oldest first, CURRENT WEEK LAST — matches
            # _acwr_trending_up()'s expected shape (it reads history[-1] as
            # "now", not a lagging prior week).
            weekly_acute_km_history=weekly_km[-3:],
            injury_flag=latest.injury_flag if latest else False,
        )

        if latest is not None:
            weekly_loads = _weekly_buckets(
                [(e.entry_date, e.session_load or 0) for e in player_entries], today, week_bounds
            )
            readiness_kwargs.update(
                acute_load_7d=weekly_loads[-1],
                chronic_load_28d=round(sum(weekly_loads) / 4, 2),
                sleep_quality=latest.sleep_quality,
                fatigue_level=latest.fatigue_level,
                muscle_soreness=latest.muscle_soreness,
                stress_level=latest.stress_level,
                mood=latest.mood,
            )

        readiness = PlayerReadiness(**readiness_kwargs)
        readiness_by_name[name] = readiness
        results.append(SquadReadiness(player, readiness, latest))

    flags_by_name: dict[str, list[PlayerFlag]] = {}
    for flag in flag_players(list(readiness_by_name.values()), rpe_module_active=rpe_module_active):
        flags_by_name.setdefault(flag.player_name, []).append(flag)

    for sr in results:
        sr.flags = flags_by_name.get(sr.readiness.player_name, [])

    return results
