from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Player, RPE
from app.schemas import WellnessResponse

router = APIRouter(prefix="/api", tags=["wellness"])

ACUTE_WINDOW_DAYS = 7
CHRONIC_WINDOW_DAYS = 28

# Standard ACWR risk bands (Gabbett sweet-spot model).
LOW_RATIO_THRESHOLD = 0.8
CAUTION_RATIO_THRESHOLD = 1.3
HIGH_RATIO_THRESHOLD = 1.5


def _load_sum(db: Session, player_id: int, start: date, end: date) -> float:
    entries = db.scalars(
        select(RPE).where(RPE.player_id == player_id, RPE.entry_date >= start, RPE.entry_date <= end)
    ).all()
    return float(sum(e.rpe_value * e.duration_minutes for e in entries))


@router.get("/wellness-status", response_model=WellnessResponse)
def wellness_status(playerId: int, db: Session = Depends(get_db)):
    player = db.get(Player, playerId)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")

    today = date.today()
    acute_start = today - timedelta(days=ACUTE_WINDOW_DAYS - 1)
    chronic_start = today - timedelta(days=CHRONIC_WINDOW_DAYS - 1)

    acute_load = _load_sum(db, playerId, acute_start, today)
    chronic_load_28d = _load_sum(db, playerId, chronic_start, today)
    chronic_weekly_avg = chronic_load_28d / (CHRONIC_WINDOW_DAYS / ACUTE_WINDOW_DAYS)

    if chronic_weekly_avg == 0:
        return WellnessResponse(
            playerId=playerId,
            acuteLoad7d=acute_load,
            chronicLoad28d=chronic_load_28d,
            acwr=None,
            flag="insufficient_data",
            message="Not enough historical RPE data (28-day chronic load is zero) to compute ACWR.",
        )

    acwr = round(acute_load / chronic_weekly_avg, 2)

    if acwr < LOW_RATIO_THRESHOLD:
        flag, message = "orange", "Acute load is low relative to chronic load — undertraining/detraining risk."
    elif acwr <= CAUTION_RATIO_THRESHOLD:
        flag, message = "green", "ACWR within the sweet spot — training load is well managed."
    elif acwr <= HIGH_RATIO_THRESHOLD:
        flag, message = "orange", "ACWR elevated — monitor load and consider moderating intensity."
    else:
        flag, message = "red", "ACWR spike detected — high injury risk, reduce load."

    return WellnessResponse(
        playerId=playerId,
        acuteLoad7d=acute_load,
        chronicLoad28d=chronic_load_28d,
        acwr=acwr,
        flag=flag,
        message=message,
    )
