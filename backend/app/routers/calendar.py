from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import CalendarEvent as DbCalendarEvent
from app.models import User
from app.schemas_dashboards import CalendarEventSchema

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/events", response_model=list[CalendarEventSchema])
def list_events(
    event_type: str | None = Query(default=None),
    from_date: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(DbCalendarEvent).where(DbCalendarEvent.club_id == current_user.club_id)
    if event_type is not None:
        stmt = stmt.where(DbCalendarEvent.event_type == event_type)
    if from_date is not None:
        stmt = stmt.where(DbCalendarEvent.event_date >= from_date)
    stmt = stmt.order_by(DbCalendarEvent.event_date)

    events = db.scalars(stmt).all()
    return [
        CalendarEventSchema(
            id=ev.id,
            event_type=ev.event_type,
            event_date=ev.event_date,
            label=ev.label,
            is_projected=ev.is_projected,
            player_ids=[p.player_id for p in ev.players],
        )
        for ev in events
    ]
