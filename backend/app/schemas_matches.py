"""Pydantic schemas for app/routers/matches.py — the match selector and
per-player match-minutes editor behind the MAS compensation panel."""

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import PlayerPosition

SelectionStatus = Literal["basis", "bank", "niet_geselecteerd"]

DEFAULT_MINUTES_BY_STATUS: dict[str, int] = {
    "basis": 90,
    "bank": 0,
    "niet_geselecteerd": 0,
}


class MatchCreate(BaseModel):
    opponent: str = Field(min_length=1, max_length=120)
    match_date: datetime
    is_home: bool
    competition: str | None = None


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    opponent: str
    match_date: datetime
    is_home: bool
    competition: str | None
    status: str


class MatchPlayerRow(BaseModel):
    player_id: uuid.UUID
    first_name: str
    last_name: str
    jersey_number: int | None
    mas_kmh: float | None
    selection_status: SelectionStatus
    minutes_played: int
    # De positie op het moment van deze wedstrijd (match_minutes.position_played)
    # indien al ingegeven, anders de speler's huidige profielpositie — nodig
    # voor de km-gebaseerde inhaaldrempel (qualifies_for_match_makeup_by_km).
    position: Optional[PlayerPosition] = None


class MatchPlayerUpdate(BaseModel):
    selection_status: SelectionStatus
    minutes_played: int | None = Field(default=None, ge=0, le=90)
    # Al beschikbaar in de players/squad-data — de Wedstrijden-tab stuurt dit
    # gewoon mee bij het opslaan i.p.v. dat de server het apart moet opzoeken,
    # en het wordt vastgelegd op match_minutes.position_played (een snapshot
    # van de positie TIJDENS deze wedstrijd, onafhankelijk van latere
    # positiewijzigingen op het spelersprofiel).
    position: Optional[PlayerPosition] = None
