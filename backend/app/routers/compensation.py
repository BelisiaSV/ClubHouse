from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Player
from app.schemas import CompensationRequest, CompensationResponse

router = APIRouter(prefix="/api", tags=["compensation"])

# Coaching-staff-tunable protocol parameters for HIT compensation running.
MATCH_FULL_MINUTES = 90
HIT_INTENSITY_PCT = 1.10  # run at 110% of MAS
INTERVAL_WORK_SECONDS = 15
INTERVAL_REST_SECONDS = 15
# Minutes of high-intensity compensation running prescribed per minute of match time missed.
COMPENSATION_RATIO = 0.40


@router.post("/calculate-compensation", response_model=CompensationResponse)
def calculate_compensation(payload: CompensationRequest, db: Session = Depends(get_db)):
    player = db.get(Player, payload.playerId)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")

    minutes_missed = max(0, MATCH_FULL_MINUTES - payload.matchMinutes)
    target_speed_ms = round(player.mas_score * HIT_INTENSITY_PCT, 2)

    total_running_minutes = minutes_missed * COMPENSATION_RATIO
    total_running_seconds = total_running_minutes * 60
    repetitions = int(round(total_running_seconds / INTERVAL_WORK_SECONDS)) if total_running_seconds > 0 else 0

    actual_running_seconds = repetitions * INTERVAL_WORK_SECONDS
    total_distance_meters = round(target_speed_ms * actual_running_seconds, 1)
    total_session_seconds = repetitions * (INTERVAL_WORK_SECONDS + INTERVAL_REST_SECONDS)

    return CompensationResponse(
        playerId=player.id,
        masScore=player.mas_score,
        matchMinutes=payload.matchMinutes,
        minutesMissed=minutes_missed,
        targetSpeedMs=target_speed_ms,
        intervalWorkSeconds=INTERVAL_WORK_SECONDS,
        intervalRestSeconds=INTERVAL_REST_SECONDS,
        repetitions=repetitions,
        totalDistanceMeters=total_distance_meters,
        totalRunningDurationMinutes=round(actual_running_seconds / 60, 1),
        totalSessionDurationMinutes=round(total_session_seconds / 60, 1),
    )
