"""Pydantic request/response schemas for the periodization/MAS dashboard
routers (app/routers/{periodization,mas_testing,makeup_programs,
team_readiness,volume_planning}.py).

Kept separate from app/schemas.py (which covers auth/club/player/mas-
compensation) so each concern's schema surface stays a manageable size,
mirroring the split of app/services/football_periodization_services.py
into one module per dashboard panel.

These services are pure/DB-free (see app/services/periodization.py docstring):
every schema here is a plain input/output contract mirroring a service
dataclass 1:1, convertible to/from it via to_dataclass()/from_attributes.
Two router endpoints add a DB-backed layer on top without changing that:
POST /api/periodization/cycles persists its result as the club's active
cycle, and POST /api/makeup-programs/generate-for-match looks that cycle
back up server-side instead of taking it from the request body.
"""

import uuid
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.services.periodization import CycleWeek, TrainingCycle, WeekFocus
from app.services.team_readiness import PlayerReadiness
from app.services.volume_planning import PlayerPosition


# ---- Shared: CycleWeek / TrainingCycle ----
class CycleWeekSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    week_number: int
    week_start_date: date
    focus: WeekFocus
    planned_load_pct: float
    num_matches: int = 0
    num_trainings: int = 2

    def to_dataclass(self) -> CycleWeek:
        return CycleWeek(**self.model_dump())


class TrainingCycleSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Set only by DB-backed endpoints (GET/PATCH .../cycles/*) so the
    # frontend can reference a specific persisted cycle by id; None on the
    # bare pure-calculator responses (build/reschedule), which never had an
    # id to begin with.
    id: Optional[uuid.UUID] = None
    name: str
    length_weeks: int
    start_date: date
    # Optional: often not yet known when a cycle is chosen — set automatically
    # by align_cycle_to_nearest_match() once real matches exist in the
    # calendar, never entered by hand (see services/periodization.py).
    target_match_date: Optional[date] = None
    target_peak_weekly_km: float = 23.0
    weeks: list[CycleWeekSchema] = Field(default_factory=list)
    shift_count: int = 0
    # True only for the club's very first cycle ever (season.cycles[0]) —
    # see app.models.TrainingCycle.is_season_start's docstring.
    is_season_start: bool = False

    def to_dataclass(self) -> TrainingCycle:
        return TrainingCycle(
            name=self.name,
            length_weeks=self.length_weeks,
            start_date=self.start_date,
            target_match_date=self.target_match_date,
            target_peak_weekly_km=self.target_peak_weekly_km,
            weeks=[w.to_dataclass() for w in self.weeks],
            shift_count=self.shift_count,
            is_season_start=self.is_season_start,
        )


# ---- periodization.py router ----
class BuildCycleRequest(BaseModel):
    name: str
    length_weeks: Literal[4, 6, 8]
    start_date: date
    # Not part of the cycle-choosing flow anymore — left optional purely so
    # the endpoint stays usable programmatically; the frontend never sends
    # this. See align_cycle_to_nearest_match().
    target_match_date: Optional[date] = None
    target_peak_weekly_km: float = 23.0


class RescheduleCycleRequest(BaseModel):
    cycle: TrainingCycleSchema
    cancelled_match_date: date
    new_match_date: date
    reason: str = "winterweer"


class QueueNextCycleRequest(BaseModel):
    length_weeks: Literal[4, 6, 8]
    target_match_date: Optional[date] = None
    target_peak_weekly_km: float = 23.0
    name: Optional[str] = None


class CurrentCyclesResponse(BaseModel):
    active: Optional[TrainingCycleSchema] = None
    queued: Optional[TrainingCycleSchema] = None
    # True iff the active cycle is also the season's last cycle (nothing
    # queued after it yet) — the frontend only allows editing start_date/
    # length_weeks while this holds, matching edit_active_cycle()'s guard.
    can_edit_active_cycle: bool = False


class PatchActiveCycleRequest(BaseModel):
    # name/target_peak_weekly_km are always safe, in-place edits.
    # start_date/length_weeks are structural (rebuild every week via
    # services.periodization.edit_active_cycle) and only accepted while
    # can_edit_active_cycle holds — see that function's docstring for why.
    # target_match_date is never client-settable anymore: it's derived
    # automatically by align_cycle_to_nearest_match() whenever a match is
    # added (see app/routers/matches.py).
    name: Optional[str] = None
    start_date: Optional[date] = None
    length_weeks: Optional[Literal[4, 6, 8]] = None
    target_peak_weekly_km: Optional[float] = None


# ---- Week-km-overview per position (GET .../training-cycles/{id}/km-overview) ----
class PositionWeeklyKmSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position: PlayerPosition
    training_km: float
    match_km: float
    total_km: float


class WeeklyKmOverviewSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    week_number: int
    focus: WeekFocus
    team_weekly_target_km: float
    team_training_km: float
    team_match_km: float
    by_position: list[PositionWeeklyKmSchema]


# ---- Season start / next-cycle split (POST /seasons, POST /seasons/{id}/next-cycle) ----
class StartSeasonRequest(BaseModel):
    name: str
    start_date: date
    length_weeks: Literal[4, 6, 8]
    # Not part of this flow — the coach only picks a start date; the target
    # match is determined automatically later, see align_cycle_to_nearest_match().
    target_match_date: Optional[date] = None
    target_peak_weekly_km: float = 23.0


class StartSeasonResponse(BaseModel):
    # There's no persisted "seasons" table (a club's season is still just
    # "all of its training_cycles rows", per load_season_from_db) — season_id
    # is the club's own id, so it stays a stable, self-consistent handle for
    # POST /seasons/{season_id}/next-cycle without a schema migration to add
    # real multi-season history, which nothing else in the API supports yet.
    season_id: uuid.UUID
    cycle: TrainingCycleSchema


class NextCycleRequest(BaseModel):
    length_weeks: Literal[4, 6, 8]
    target_match_date: Optional[date] = None
    target_peak_weekly_km: float = 23.0
    name: Optional[str] = None
    # Present only so the endpoint can explicitly reject it with a 400
    # instead of silently ignoring it — queue_next_cycle() always derives
    # the date server-side (end of the active cycle), never from the client.
    start_date: Optional[date] = None


# ---- mas_testing.py router ----
class PlanNextMasTestRequest(BaseModel):
    player_name: str
    last_test_date: Optional[date] = None
    cycle: TrainingCycleSchema
    today: date
    due_soon_window_days: int = 7


class TestPlanningResultSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_name: str
    last_test_date: Optional[date]
    weeks_since_last_test: Optional[float]
    next_required_test_date: date
    reason: str
    status: str


class TrainingZoneSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    pct_mas_low: float
    pct_mas_high: float
    speed_low_kmh: float
    speed_high_kmh: float
    typical_use: str


class MASTestProtocolSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    name: str
    description: str
    equipment: list[str]
    how_to_administer: str
    result_label: str
    correction_factor: float


class RecordMasTestRequest(BaseModel):
    player_id: uuid.UUID
    protocol_key: str
    raw_result_kmh: float = Field(gt=0)
    test_date: date


class CalendarEventSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    event_date: date
    label: str
    is_projected: bool
    player_ids: list[uuid.UUID] = Field(default_factory=list)


class RecordMasTestResponse(BaseModel):
    player_id: uuid.UUID
    mas_kmh: float
    protocol_name: str
    test_date: date
    calendar_events_synced: int


class CurrentMasResultSchema(BaseModel):
    player_id: uuid.UUID
    player_name: str
    mas_kmh: float
    test_date: date


class MasTestBatchEntry(BaseModel):
    player_id: uuid.UUID
    # None/blank = the coach hasn't filled this player's result in yet —
    # skipped, not an error (see record_mas_test_batch's docstring).
    raw_result_kmh: Optional[float] = None


class RecordMasTestBatchRequest(BaseModel):
    protocol_key: str
    test_date: date
    results: list[MasTestBatchEntry]


class RecordMasTestBatchResponse(BaseModel):
    saved_player_ids: list[uuid.UUID]
    skipped_player_ids: list[uuid.UUID]
    calendar_events_synced: int


# ---- looptypegroepen (running groups) ----
class RunningGroupMemberSchema(BaseModel):
    player_id: uuid.UUID
    player_name: str
    mas_kmh: float


class RunningGroupSchema(BaseModel):
    label: str
    players: list[RunningGroupMemberSchema]
    prescriptie_mas_kmh: float
    avg_mas_kmh: float
    min_mas_kmh: float
    max_mas_kmh: float
    # Interval-doelen VOOR DE GROEP (op basis van prescriptie_mas_kmh, het
    # veiligheidsanker) i.p.v. per individuele speler.
    training_zones: list[TrainingZoneSchema]


class SkippedRunningGroupPlayer(BaseModel):
    player_id: uuid.UUID
    player_name: str
    reason: str


class SuggestRunningGroupsRequest(BaseModel):
    num_groups: int = Field(default=3, ge=2, le=4)


class SuggestRunningGroupsResponse(BaseModel):
    groups: list[RunningGroupSchema]
    skipped: list[SkippedRunningGroupPlayer] = Field(default_factory=list)
    # Gevuld wanneer assign_running_groups() automatisch heeft teruggeschaald
    # naar minder groepen dan gevraagd (te weinig spreiding in de kern) — dit
    # is relevante info voor de coach, geen foutmelding om te verbergen.
    note: str = ""


class ConfirmRunningGroupSchema(BaseModel):
    label: str
    player_ids: list[uuid.UUID]


class ConfirmRunningGroupsRequest(BaseModel):
    groups: list[ConfirmRunningGroupSchema]


# ---- makeup_programs.py router ----
class MakeupCandidate(BaseModel):
    player_name: str
    mas_kmh: float = Field(gt=0)
    reason: Literal["match_minutes", "training_absence"]
    minutes_played: Optional[int] = Field(default=None, ge=0, le=90)
    # Verplicht bij reason == 'match_minutes' — nodig voor de km-gebaseerde
    # inhaaldrempel (qualifies_for_match_makeup_by_km). generate_makeup_schedules()
    # geeft zelf een duidelijke ValueError als dit ontbreekt.
    position: Optional[PlayerPosition] = None
    opponent_label: str = ""
    training_date_label: str = ""


class GenerateMakeupSchedulesRequest(BaseModel):
    candidates: list[MakeupCandidate]
    week: CycleWeekSchema


class MissedMinutesRequest(BaseModel):
    player_name: str
    mas_kmh: float = Field(gt=0)
    minutes_played: int = Field(ge=0, le=90)
    week_focus: WeekFocus
    opponent_label: str = ""


class MissedTrainingRequest(BaseModel):
    player_name: str
    mas_kmh: float = Field(gt=0)
    week: CycleWeekSchema
    training_date_label: str = ""


class GeneratedRunningProgramSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_name: str
    reason: str
    trigger_detail: str
    week_focus: WeekFocus
    mas_kmh: float
    session_type: str
    intensity_pct_mas: float
    target_speed_kmh: float
    structure_description: str
    total_duration_min: float
    total_distance_m: float


class GenerateForMatchRequest(BaseModel):
    match_id: uuid.UUID


class SkippedCandidate(BaseModel):
    player_name: str
    reason: str


class GenerateForMatchResponse(BaseModel):
    context_label: str
    programs: list[GeneratedRunningProgramSchema]
    skipped: list[SkippedCandidate]


# ---- team_readiness.py router ----
class PlayerReadinessSchema(BaseModel):
    player_name: str
    # Km-gebaseerde basislaag — altijd beschikbaar, geen RPE-invoer nodig.
    acute_km_7d: float = Field(ge=0, default=0.0)
    chronic_km_28d: float = Field(ge=0, default=0.0)
    injury_flag: bool = False
    weekly_acute_km_history: list[float] = Field(default_factory=list)

    # RPE/wellness-laag — volledig optioneel, telt enkel mee als de
    # RPE_WELLNESS-module actief is voor deze club (zie app.services.
    # team_readiness's docstring).
    acute_load_7d: Optional[float] = Field(default=None, ge=0)
    chronic_load_28d: Optional[float] = Field(default=None, ge=0)
    sleep_quality: Optional[int] = Field(default=None, ge=1, le=5)
    fatigue_level: Optional[int] = Field(default=None, ge=1, le=5)
    muscle_soreness: Optional[int] = Field(default=None, ge=1, le=5)
    stress_level: Optional[int] = Field(default=None, ge=1, le=5)
    mood: Optional[int] = Field(default=None, ge=1, le=5)

    def to_dataclass(self) -> PlayerReadiness:
        return PlayerReadiness(**self.model_dump())


class PlayerFlagSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_name: str
    flag_type: str
    detail: str
    recommendation: str
    source: str = "km"


class FlagPlayersRequest(BaseModel):
    players: list[PlayerReadinessSchema]


class ProposeTrainingRequest(BaseModel):
    week: CycleWeekSchema
    players: list[PlayerReadinessSchema]
    km_per_training: float = Field(ge=0)


class ProposeTrainingAutoRequest(BaseModel):
    # Everything else (week, players) is loaded server-side from the active
    # cycle/week + load_squad_readiness — see POST .../propose-training/auto.
    km_per_training: float = Field(ge=0)


class NextSessionSchema(BaseModel):
    session_type: Literal["training", "match"]
    session_date: date
    label: str  # e.g. "di 4 aug" — see app/routers/team_readiness.py's _format_nl_date_short


class NextTrainingOverviewSchema(BaseModel):
    # For the four Next Training status tiles (see app/routers/team_readiness.py's
    # /overview docstring for exactly what each count/field means).
    squad_count: int
    flagged_count: int
    sessions_this_week: int
    week_focus: Optional[WeekFocus] = None
    next_session: Optional[NextSessionSchema] = None


class PlayerMinutesAdviceSchema(BaseModel):
    player_id: uuid.UUID
    player_name: str
    max_minutes: int
    base_max_minutes: int
    # Empty when no reduction applies (player isn't flagged as undertrained).
    note: str = ""


class MinutesAdviceResponse(BaseModel):
    # False whenever the active cycle isn't the season-start cycle (see
    # app.models.TrainingCycle.is_season_start) — the frontend hides the
    # widget entirely in that case rather than showing an empty list.
    applicable: bool
    week_number: Optional[int] = None
    cycle_length_weeks: Optional[int] = None
    players: list[PlayerMinutesAdviceSchema] = Field(default_factory=list)


class TrainingProposalSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Set after persisting the proposal as a TrainingSession row (see
    # app/routers/team_readiness.py) — None on the bare dataclass, filled in
    # via model_copy(update=...) once the DB row exists. This is "the
    # already-existing session" app/routers/training_sessions.py's
    # composition-proposal/vorm-target endpoints act on by id.
    session_id: Optional[uuid.UUID] = None
    week_focus: WeekFocus
    suggested_session_type: str
    intensity_pct_mas_low: float
    intensity_pct_mas_high: float
    base_duration_min: int
    adjusted_duration_min: int
    base_distance_km: float
    adjusted_distance_km: float
    team_readiness_factor: float
    adjustment_note: str
    session_index: int = 1
    player_flags: list[PlayerFlagSchema]
    distance_by_position: dict[PlayerPosition, float] = Field(default_factory=dict)


# ---- volume_planning.py router ----
class GenerateKmPlanRequest(BaseModel):
    cycle: TrainingCycleSchema
    avg_match_distance_km: float = 10.5
    min_recovery_km_per_training: float = 3.0


# ---- training_sessions.py router (oefenvormen) ----
class SessionCompositionRequest(BaseModel):
    num_players: int
    team_avg_mas_kmh: Optional[float] = None
    player_flags: Optional[list[PlayerFlagSchema]] = None


class DryRunTopUpSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    reps: int
    distance_per_rep_m: int
    time_per_rep_s: float
    rest_s: float
    intensity_pct_mas: float
    total_distance_m: float
    instruction: str


class OefenvormLibraryEntrySchema(BaseModel):
    vorm: str
    label: str
    # False = continue vorm (coach stelt duration_min in), True = partijvorm
    # met vaste bloktijd (coach stelt enkel num_bouts in) — bepaalt welk
    # veld de frontend's "blok toevoegen"/reps-editor moet tonen.
    is_bout_vorm: bool
    bout_duration_min: Optional[float] = None


class VormTargetSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vorm: str
    label: str
    duration_min: float
    distance_km: float
    intensity_pct_mas_low: float
    intensity_pct_mas_high: float
    num_bouts: Optional[int] = None
    bout_duration_min: Optional[float] = None
    rest_between_bouts_min: Optional[float] = None
    total_clock_time_min: float
    format_hint: str
    notes: str


class SessionCompositionProposalSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    week_focus: WeekFocus
    num_players: int
    target_duration_min: float
    target_distance_km: float
    blocks: list[VormTargetSchema]
    total_work_duration_min: float
    total_clock_time_min: float
    total_distance_km: float
    deviation_note: str
    optional_dry_run_topup: Optional[DryRunTopUpSchema] = None


class VormTargetRequest(BaseModel):
    # vorm is a plain str (not the OefenvormType enum) and none of these
    # fields carry Pydantic-level bounds/requiredness, on purpose: which of
    # duration_min/num_bouts is required (and which is forbidden) depends on
    # whether vorm is a bout-vorm (SSG/MSG/LSG/transitie, num_bouts only —
    # the bout length itself is fixed per vorm and never coach-settable) or
    # a continuous one (duration_min only) — app/routers/training_sessions.py
    # enforces that split and returns a clear 400 on a mismatch, instead of
    # a generic 422 from FastAPI's own request validation.
    vorm: str
    duration_min: Optional[float] = None
    num_bouts: Optional[int] = None
    num_players: int


class RecalculateCompositionRequest(BaseModel):
    # The (possibly coach-edited) block list plus the session's km goal —
    # summarize_composition() re-sums both from scratch, it doesn't look
    # either up from the stored TrainingSession row.
    blocks: list[VormTargetSchema]
    target_distance_km: float
    player_flags: Optional[list[PlayerFlagSchema]] = None
    # Vormen the coach set to 0' (skip entirely) — removed from blocks via
    # remove_skipped_blocks() before summing, never sent through as a
    # 0-duration block (calculate_vorm_target/_by_reps reject that on purpose).
    skip_vormen: Optional[list[str]] = None


class RecalculateCompositionResponse(BaseModel):
    total_work_duration_min: float
    total_clock_time_min: float
    total_distance_km: float
    deviation_pct: float
    deviation_note: str


class DryRunTopupRequest(BaseModel):
    remaining_distance_km: float
    team_avg_mas_kmh: float


# ---- training_sessions.py router: finalize / recent / detail ----
class FinalizeSessionRequest(BaseModel):
    session_date: date
    # The final block list — already excludes any skipped vormen (the
    # frontend applies remove_skipped_blocks()'s result before finalizing,
    # same as it does before displaying the recalculated totals).
    blocks: list[VormTargetSchema]
    # Kept separately (not re-derived from `blocks`) purely for display in
    # the session detail view — "these vormen were proposed but the coach
    # chose to skip them", not just "these vormen aren't here".
    skip_vormen: Optional[list[str]] = None


class RecentSessionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_date: date
    # "Sessie" column: the day name, or "Wedstrijd" if session_date falls on
    # a real Match row for this club.
    session_label: str
    # "Type" column: short summary of the vormen actually applied, e.g.
    # "Balbezit + MSG".
    type_summary: str
    # "Belasting" column: total km of the finalized composition.
    total_distance_km: float
    # "RPE" column: team average of all RpeWellnessData.rpe_score entries
    # logged for this session_date — None if nobody filled one in yet.
    team_avg_rpe: Optional[float] = None


class TrainingSessionDetailSchema(BaseModel):
    id: uuid.UUID
    week_focus: WeekFocus
    session_date: Optional[date] = None
    target_duration_min: float
    target_distance_km: float
    blocks: list[VormTargetSchema] = Field(default_factory=list)
    skipped_vormen: list[str] = Field(default_factory=list)
    total_distance_km: float
    total_work_duration_min: float
    finalized_at: Optional[datetime] = None


class WeeklyKmPlanSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    week_number: int
    focus: WeekFocus
    weekly_target_km: float
    match_distance_km: float
    training_distance_km: float
    km_per_training: float
    note: str


# ---- dashboard_widgets.py router: personal dashboard layout ----
class DashboardWidgetSchema(BaseModel):
    key: str
    label: str
    description: str
    requires_module: Optional[str] = None
    default_enabled: bool


class DashboardPreferencesSchema(BaseModel):
    # Ordered — array order IS the layout order.
    enabled_widgets: list[str]


class ToggleDashboardWidgetRequest(BaseModel):
    widget_key: str
    enabled: bool
    position: Optional[int] = None


class ReorderDashboardWidgetsRequest(BaseModel):
    new_order: list[str]
