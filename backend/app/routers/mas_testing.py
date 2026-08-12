import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_module
from app.models import CalendarEvent as DbCalendarEvent
from app.models import CalendarEventPlayer as DbCalendarEventPlayer
from app.models import MasTest, Player, User
from app.routers.periodization import load_season_from_db
from app.schemas_dashboards import (
    CalendarEventSchema,
    MASTestProtocolSchema,
    PlanNextMasTestRequest,
    RecordMasTestRequest,
    RecordMasTestResponse,
    TestPlanningResultSchema,
    TrainingZoneSchema,
)
from app.services.mas_testing import (
    MAS_TEST_PROTOCOLS,
    plan_next_mas_test,
    project_season_mas_test_events,
    recalculate_training_zones,
    record_mas_test,
)
from app.services.platform_admin import ModuleKey

router = APIRouter(
    prefix="/api/mas-testing", tags=["mas-testing"], dependencies=[Depends(require_module(ModuleKey.MAS_TEST))]
)


def _sync_mas_test_calendar(club_id: uuid.UUID, db: Session) -> list[DbCalendarEvent]:
    """(Her)projecteert alle nog vereiste MAS-testmomenten tot het einde van
    het seizoen en vervangt de nog-toekomstige geprojecteerde 'mas_test'-
    kalenderitems van de club door die verse projectie — verleden items
    blijven staan als geschiedenis. Wordt aangeroepen via POST /sync-calendar
    en automatisch na elke POST /record, zodat de kalender altijd de meest
    actuele projectie toont in plaats van een verouderd schema zodra een
    effectief testresultaat de baseline van een speler verandert."""
    today = date.today()
    season, _ = load_season_from_db(club_id, db)

    players = db.scalars(select(Player).where(Player.club_id == club_id, Player.is_active.is_(True))).all()
    name_to_player = {f"{p.first_name} {p.last_name}": p for p in players}

    players_last_test = {
        name: db.scalar(
            select(MasTest.test_date)
            .where(MasTest.player_id == player.id)
            .order_by(MasTest.test_date.desc())
            .limit(1)
        )
        for name, player in name_to_player.items()
    }

    events = project_season_mas_test_events(season, players_last_test, today=today)

    db.execute(
        delete(DbCalendarEvent).where(
            DbCalendarEvent.club_id == club_id,
            DbCalendarEvent.event_type == "mas_test",
            DbCalendarEvent.is_projected.is_(True),
            DbCalendarEvent.event_date >= today,
        )
    )
    db.flush()

    created: list[DbCalendarEvent] = []
    for ev in events:
        db_event = DbCalendarEvent(
            club_id=club_id, event_type="mas_test", event_date=ev.event_date, label=ev.label, is_projected=True
        )
        db.add(db_event)
        db.flush()
        for player_name in ev.player_names:
            player = name_to_player.get(player_name)
            if player is not None:
                db.add(DbCalendarEventPlayer(calendar_event_id=db_event.id, player_id=player.id))
        created.append(db_event)

    db.commit()
    for ev in created:
        db.refresh(ev)
    return created


@router.post("/plan-next-test", response_model=TestPlanningResultSchema)
def plan_next_test(payload: PlanNextMasTestRequest, current_user: User = Depends(get_current_user)):
    result = plan_next_mas_test(
        player_name=payload.player_name,
        last_test_date=payload.last_test_date,
        cycle=payload.cycle.to_dataclass(),
        today=payload.today,
        due_soon_window_days=payload.due_soon_window_days,
    )
    return TestPlanningResultSchema.model_validate(result)


@router.get("/zones", response_model=list[TrainingZoneSchema])
def zones(mas_kmh: float = Query(gt=0), current_user: User = Depends(get_current_user)):
    try:
        result = recalculate_training_zones(mas_kmh)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [TrainingZoneSchema.model_validate(z) for z in result]


@router.get("/protocols", response_model=list[MASTestProtocolSchema])
def list_protocols(current_user: User = Depends(get_current_user)):
    return [MASTestProtocolSchema.model_validate(p) for p in MAS_TEST_PROTOCOLS.values()]


@router.post("/record", response_model=RecordMasTestResponse)
def record_test(
    payload: RecordMasTestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verwerkt een ingevoerd testresultaat naar een MAS-score en logt die als
    nieuwe mas_test-rij. Herprojecteert daarna meteen de MAS-testkalender
    (_sync_mas_test_calendar) zodat nog-toekomstige testmomenten die van deze
    nieuwe baseline afhangen meteen worden bijgesteld."""
    player = db.get(Player, payload.player_id)
    if player is None or player.club_id != current_user.club_id:
        raise HTTPException(status_code=404, detail="Player not found")

    try:
        record = record_mas_test(
            player_name=f"{player.first_name} {player.last_name}",
            protocol_key=payload.protocol_key,
            raw_result_kmh=payload.raw_result_kmh,
            test_date=payload.test_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.add(
        MasTest(
            player_id=player.id,
            club_id=current_user.club_id,
            test_date=record.test_date,
            protocol=record.protocol_name,
            mas_kmh=record.mas_kmh,
            created_by=current_user.id,
        )
    )
    db.commit()

    synced = _sync_mas_test_calendar(current_user.club_id, db)

    return RecordMasTestResponse(
        player_id=player.id,
        mas_kmh=record.mas_kmh,
        protocol_name=record.protocol_name,
        test_date=record.test_date,
        calendar_events_synced=len(synced),
    )


@router.post("/sync-calendar", response_model=list[CalendarEventSchema])
def sync_calendar(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    events = _sync_mas_test_calendar(current_user.club_id, db)
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
