import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import PlayerPosition, UserRole


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

    class Config:
        from_attributes = True


class ClubUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    logo_url: str | None = None
    primary_color: str | None = Field(default=None, max_length=20)
    secondary_color: str | None = Field(default=None, max_length=20)
    competition_level: str | None = Field(default=None, max_length=120)


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
