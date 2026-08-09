from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_current_user
from app.models import User
from app.schemas_dashboards import (
    GenerateMakeupSchedulesRequest,
    GeneratedRunningProgramSchema,
    MissedMinutesRequest,
    MissedTrainingRequest,
)
from app.services.makeup_programs import (
    generate_makeup_schedules,
    generate_program_for_missed_minutes,
    generate_program_for_missed_training,
)

router = APIRouter(prefix="/api/makeup-programs", tags=["makeup-programs"])


@router.post("/generate", response_model=list[GeneratedRunningProgramSchema])
def generate(payload: GenerateMakeupSchedulesRequest, current_user: User = Depends(get_current_user)):
    """De 'Maak schema's'-knop: neemt een lijst kandidaten (wedstrijdminuten of
    trainingsafwezigheid) en genereert voor elk het passende inhaalprogramma."""
    candidates = [c.model_dump() for c in payload.candidates]
    try:
        programs = generate_makeup_schedules(candidates, payload.week.to_dataclass())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [GeneratedRunningProgramSchema.model_validate(p) for p in programs]


@router.post("/missed-minutes", response_model=GeneratedRunningProgramSchema)
def missed_minutes(payload: MissedMinutesRequest, current_user: User = Depends(get_current_user)):
    try:
        program = generate_program_for_missed_minutes(
            player_name=payload.player_name,
            mas_kmh=payload.mas_kmh,
            minutes_played=payload.minutes_played,
            week_focus=payload.week_focus,
            opponent_label=payload.opponent_label,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GeneratedRunningProgramSchema.model_validate(program)


@router.post("/missed-training", response_model=GeneratedRunningProgramSchema)
def missed_training(payload: MissedTrainingRequest, current_user: User = Depends(get_current_user)):
    try:
        program = generate_program_for_missed_training(
            player_name=payload.player_name,
            mas_kmh=payload.mas_kmh,
            week=payload.week.to_dataclass(),
            training_date_label=payload.training_date_label,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GeneratedRunningProgramSchema.model_validate(program)
