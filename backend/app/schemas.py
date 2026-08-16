import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models import ExternalLoadCategory, PlayerPosition, UserRole


# ---- Auth ----
class RegisterRequest(BaseModel):
    club_name: str = Field(min_length=2, max_length=120)
    club_slug: str = Field(min_length=2, max_length=60, pattern=r"^[a-z0-9-]+$")
    coach_full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    club_id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool

    class Config:
        from_attributes = True


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str


# ---- Club (whitelabel branding) ----
class ClubOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    logo_url: str | None
    primary_color: str | None
    secondary_color: str | None
    competition_level: str | None
    # Weekday numbers (0=Monday..6=Sunday) the club trains on by default —
    # the only input app.services.rpe_wellness.is_session_day() has for
    # "training day" (see that module's docstring for why).
    training_weekdays: list[int] | None
    # Module keys the frontend may show nav/UI for — mirrors backend
    # enforcement (app.deps.require_module) but lets the frontend hide
    # things proactively instead of only erroring after a click. Always
    # includes CORE_MODULES regardless of club_modules rows. Computed in
    # app/routers/clubs.py, not a real Club column.
    enabled_modules: list[str] = []

    class Config:
        from_attributes = True


class ClubUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    logo_url: str | None = None
    primary_color: str | None = Field(default=None, max_length=20)
    secondary_color: str | None = Field(default=None, max_length=20)
    competition_level: str | None = Field(default=None, max_length=120)
    training_weekdays: list[int] | None = None

    @field_validator("training_weekdays")
    @classmethod
    def _validate_weekdays(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if any(day < 0 or day > 6 for day in value):
            raise ValueError("training_weekdays moet uit getallen 0 (maandag) t.e.m. 6 (zondag) bestaan")
        return sorted(set(value))


# ---- Players ----
class PlayerCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    email: str | None = None
    phone_number: str | None = None
    jersey_number: int | None = Field(default=None, ge=0, le=99)
    date_of_birth: date | None = None
    position: PlayerPosition | None = None
    dominant_foot: str | None = Field(default=None, pattern="^(left|right|both)$")


class PlayerUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=120)
    last_name: str | None = Field(default=None, min_length=1, max_length=120)
    email: str | None = None
    phone_number: str | None = None
    jersey_number: int | None = Field(default=None, ge=0, le=99)
    date_of_birth: date | None = None
    position: PlayerPosition | None = None
    dominant_foot: str | None = Field(default=None, pattern="^(left|right|both)$")
    is_active: bool | None = None


class PlayerOut(BaseModel):
    id: uuid.UUID
    club_id: uuid.UUID
    first_name: str
    last_name: str
    email: str | None
    phone_number: str | None
    jersey_number: int | None
    date_of_birth: date | None
    position: PlayerPosition | None
    dominant_foot: str | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SquadOverviewPlayerSchema(BaseModel):
    """One row of GET /api/players/squad-overview — a player plus their
    readiness status. 'acwr' is the always-available km-based ACWR (see
    app.services.team_readiness._acwr_km); 'acwr_rpe' is only populated
    when the RPE_WELLNESS module is active AND this player has a recent
    entry. 'geen_data' (rather than defaulting to 'fit') applies only when
    there's truly no basis for either signal — a player with real km data
    but no RPE entry gets a real km-based status, not 'geen_data'."""

    id: uuid.UUID
    first_name: str
    last_name: str
    jersey_number: int | None
    position: PlayerPosition | None
    status: Literal["fit", "reductie", "overbelast", "geen_data"]
    acwr: float | None
    acwr_rpe: float | None = None
    latest_rpe: int | None
    latest_wellness: float | None
    flags: list[str]
    # Raw flag_type values behind `flags`' human-readable detail strings —
    # lets the frontend filter for the exact "needs attention" set (Next
    # Training's overload/poor_recovery/acwr_trending_up/injured tile, which
    # deliberately excludes underload) without re-deriving it from text.
    flag_types: list[str] = []
    # Parallel to flags/flag_types: 'km' or 'rpe' per flag, so the UI can
    # show which signal caused it.
    flag_sources: list[str] = []


class PlayerImportError(BaseModel):
    row: int
    message: str


class PlayerImportResult(BaseModel):
    created: int
    skipped: int
    errors: list[PlayerImportError]


class WeeklyDistanceOut(BaseModel):
    player_id: uuid.UUID
    week_number: int
    match_distance_km: float
    training_distance_km: float
    total_km: float


# ---- MAS compensation ----
class CompensationRequest(BaseModel):
    player_id: uuid.UUID
    minutes_played: float = Field(ge=0, le=90, description="Effectief gespeelde minuten in de wedstrijd")
    intensity_pct: float = Field(default=1.10, gt=0, description="Doelintensiteit t.o.v. MAS (1.10 = 110%)")


class CompensationResponse(BaseModel):
    player_id: uuid.UUID
    player_name: str
    mas_kmh: float
    mas_test_date: str
    minutes_played: float
    intensity_pct: float
    target_speed_kmh: float
    target_speed_ms: float
    total_work_time_min: float
    total_reps: int
    blocks: int
    reps_per_block: int
    distance_per_rep_m: float
    total_distance_m: float
    protocol_description: str


# ---- RPE / wellness ----
class SessionDayOut(BaseModel):
    date: date
    is_session_day: bool
    reason: Literal["match", "training"] | None


class RpeWellnessCreate(BaseModel):
    player_id: uuid.UUID
    entry_date: date
    session_type: str | None = Field(default=None, max_length=60)
    rpe_score: int | None = Field(default=None, ge=1, le=10)
    session_duration_min: int | None = Field(default=None, ge=1)
    sleep_quality: int | None = Field(default=None, ge=1, le=5)
    fatigue_level: int | None = Field(default=None, ge=1, le=5)
    muscle_soreness: int | None = Field(default=None, ge=1, le=5)
    stress_level: int | None = Field(default=None, ge=1, le=5)
    mood: int | None = Field(default=None, ge=1, le=5)
    injury_flag: bool = False
    injury_note: str | None = None
    # Context-only — see RpeWellnessData's model docstring note: never fed
    # into _wellness_composite() or the ACWR calc.
    external_load_category: ExternalLoadCategory | None = None
    extra_activity_today: bool | None = None
    extra_activity_note: str | None = Field(default=None, max_length=280)


class RpeWellnessOut(BaseModel):
    id: uuid.UUID
    player_id: uuid.UUID
    club_id: uuid.UUID
    entry_date: date
    session_type: str | None
    rpe_score: int | None
    session_duration_min: int | None
    session_load: int | None
    sleep_quality: int | None
    fatigue_level: int | None
    muscle_soreness: int | None
    stress_level: int | None
    mood: int | None
    injury_flag: bool
    injury_note: str | None
    external_load_category: ExternalLoadCategory | None
    extra_activity_today: bool | None
    extra_activity_note: str | None
    created_at: datetime

    class Config:
        from_attributes = True
