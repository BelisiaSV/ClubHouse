"""Pydantic request/response schemas for the periodization/MAS dashboard
routers (app/routers/{periodization,mas_testing,makeup_programs,
team_readiness,volume_planning}.py).

Kept separate from app/schemas.py (which covers auth/club/player/mas-
compensation) so each concern's schema surface stays a manageable size,
mirroring the split of app/services/football_periodization_services.py
into one module per dashboard panel.

These services are pure/DB-free (see app/services/periodization.py docstring),
so every schema here is a plain input/output contract — nothing is persisted.
Each "Schema" class mirrors a service dataclass 1:1 and can convert to/from it.
"""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.services.periodization import CycleWeek, TrainingCycle, WeekFocus
from app.services.team_readiness import PlayerReadiness


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

    name: str
    length_weeks: int
    start_date: date
    target_match_date: date
    target_peak_weekly_km: float = 25.0
    weeks: list[CycleWeekSchema] = Field(default_factory=list)
    shift_count: int = 0

    def to_dataclass(self) -> TrainingCycle:
        return TrainingCycle(
            name=self.name,
            length_weeks=self.length_weeks,
            start_date=self.start_date,
            target_match_date=self.target_match_date,
            target_peak_weekly_km=self.target_peak_weekly_km,
            weeks=[w.to_dataclass() for w in self.weeks],
            shift_count=self.shift_count,
        )


# ---- periodization.py router ----
class BuildCycleRequest(BaseModel):
    name: str
    length_weeks: Literal[4, 6, 8]
    start_date: date
    target_match_date: date
    target_peak_weekly_km: float = 25.0


class RescheduleCycleRequest(BaseModel):
    cycle: TrainingCycleSchema
    cancelled_match_date: date
    new_match_date: date
    reason: str = "winterweer"


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


# ---- makeup_programs.py router ----
class MakeupCandidate(BaseModel):
    player_name: str
    mas_kmh: float = Field(gt=0)
    reason: Literal["match_minutes", "training_absence"]
    minutes_played: Optional[int] = Field(default=None, ge=0, le=90)
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


# ---- team_readiness.py router ----
class PlayerReadinessSchema(BaseModel):
    player_name: str
    acute_load_7d: float = Field(ge=0)
    chronic_load_28d: float = Field(ge=0)
    sleep_quality: int = Field(ge=1, le=5)
    fatigue_level: int = Field(ge=1, le=5)
    muscle_soreness: int = Field(ge=1, le=5)
    stress_level: int = Field(ge=1, le=5)
    mood: int = Field(ge=1, le=5)
    injury_flag: bool = False

    def to_dataclass(self) -> PlayerReadiness:
        return PlayerReadiness(**self.model_dump())


class PlayerFlagSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_name: str
    flag_type: str
    detail: str
    recommendation: str


class FlagPlayersRequest(BaseModel):
    players: list[PlayerReadinessSchema]


class ProposeTrainingRequest(BaseModel):
    week: CycleWeekSchema
    players: list[PlayerReadinessSchema]
    km_per_training: float = Field(ge=0)


class TrainingProposalSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    player_flags: list[PlayerFlagSchema]


# ---- volume_planning.py router ----
class GenerateKmPlanRequest(BaseModel):
    cycle: TrainingCycleSchema
    avg_match_distance_km: float = 10.5
    min_recovery_km_per_training: float = 3.0


class WeeklyKmPlanSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    week_number: int
    focus: WeekFocus
    weekly_target_km: float
    match_distance_km: float
    training_distance_km: float
    km_per_training: float
    note: str
