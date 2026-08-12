"""Pydantic schemas for app/routers/admin.py — the platform-admin API
(Jordy only, see app/services/platform_admin.py's architecture note).
Kept separate from every other schema file the same way the platform-admin
concern is kept separate from club-scoped services/routers."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ModuleDefinitionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str
    description: str
    in_base_package: bool
    is_core: bool
    is_addon: bool
    monthly_price_eur: Optional[float] = None


class ClubModuleStatusSchema(BaseModel):
    module: ModuleDefinitionSchema
    enabled: bool
    changed_at: Optional[datetime] = None
    changed_by: Optional[str] = None


class ClubModulesOverviewResponse(BaseModel):
    club_id: uuid.UUID
    club_name: str
    modules: list[ClubModuleStatusSchema]
    monthly_addon_price_eur: float


class ToggleModuleRequest(BaseModel):
    enabled: bool
