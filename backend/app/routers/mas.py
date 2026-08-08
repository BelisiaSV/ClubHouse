from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MasTest, Player
from app.schemas import CompensationRequest, CompensationResponse
from app.services.mas_compensation import calculate_hit_compensation

router = APIRouter(prefix="/mas", tags=["mas"])


@router.post("/compensation", response_model=CompensationResponse)
def compensation(payload: CompensationRequest, db: Session = Depends(get_db)):
    player = db.get(Player, payload.player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")

    latest_mas = db.scalar(
        select(MasTest)
        .where(MasTest.player_id == payload.player_id)
        .order_by(MasTest.test_date.desc())
        .limit(1)
    )
    if latest_mas is None:
        raise HTTPException(status_code=404, detail="No MAS test found for this player")

    try:
        prescription = calculate_hit_compensation(
            player_name=f"{player.first_name} {player.last_name}",
            mas_kmh=float(latest_mas.mas_kmh),
            minutes_played=payload.minutes_played,
            intensity_pct=payload.intensity_pct,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CompensationResponse(
        player_id=player.id,
        player_name=prescription.player_name,
        mas_kmh=prescription.mas_kmh,
        mas_test_date=latest_mas.test_date.isoformat(),
        minutes_played=prescription.minutes_played,
        intensity_pct=prescription.intensity_pct,
        target_speed_kmh=prescription.target_speed_kmh,
        target_speed_ms=prescription.target_speed_ms,
        total_work_time_min=prescription.total_work_time_min,
        total_reps=prescription.total_reps,
        blocks=prescription.blocks,
        reps_per_block=prescription.reps_per_block,
        distance_per_rep_m=prescription.distance_per_rep_m,
        total_distance_m=prescription.total_distance_m,
        protocol_description=prescription.protocol_description,
    )
