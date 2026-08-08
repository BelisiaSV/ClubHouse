import uuid

from pydantic import BaseModel, Field


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
