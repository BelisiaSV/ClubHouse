from datetime import date

from pydantic import BaseModel, ConfigDict, Field


# ---- Player ----
class PlayerBase(BaseModel):
    name: str
    position: str | None = None
    mas_score: float = Field(gt=0, description="Maximal Aerobic Speed in m/s")


class PlayerCreate(PlayerBase):
    pass


class PlayerOut(PlayerBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---- Match ----
class MatchBase(BaseModel):
    player_id: int
    match_date: date
    minutes_played: int = Field(ge=0, le=120)
    opponent: str | None = None
    competition: str | None = None


class MatchCreate(MatchBase):
    pass


class MatchOut(MatchBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---- RPE ----
class RPEBase(BaseModel):
    player_id: int
    entry_date: date
    rpe_value: int = Field(ge=0, le=10)
    duration_minutes: int = Field(ge=0)


class RPECreate(RPEBase):
    pass


class RPEOut(RPEBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    load: int


# ---- Cycle ----
class CycleBase(BaseModel):
    player_id: int | None = None
    name: str
    phase: str | None = None
    start_date: date
    end_date: date


class CycleCreate(CycleBase):
    pass


class CycleOut(CycleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---- Compensation training ----
class CompensationRequest(BaseModel):
    playerId: int
    matchMinutes: int = Field(ge=0, le=120, description="Minutes the player actually played in the match")


class CompensationResponse(BaseModel):
    playerId: int
    masScore: float
    matchMinutes: int
    minutesMissed: int
    targetSpeedMs: float = Field(description="Prescribed running speed, 110% of MAS, in m/s")
    intervalWorkSeconds: int
    intervalRestSeconds: int
    repetitions: int
    totalDistanceMeters: float
    totalRunningDurationMinutes: float
    totalSessionDurationMinutes: float


# ---- Wellness / ACWR ----
class WellnessResponse(BaseModel):
    playerId: int
    acuteLoad7d: float
    chronicLoad28d: float
    acwr: float | None
    flag: str  # "green" | "orange" | "red" | "insufficient_data"
    message: str
