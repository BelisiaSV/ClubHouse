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
from app.models import RunningGroup as DbRunningGroup
from app.models import RunningGroupPlayer as DbRunningGroupPlayer
from app.routers.periodization import load_season_from_db
from app.schemas_dashboards import (
    CalendarEventSchema,
    ConfirmRunningGroupsRequest,
    MASTestProtocolSchema,
    PlanNextMasTestRequest,
    RecordMasTestBatchRequest,
    RecordMasTestBatchResponse,
    RecordMasTestRequest,
    RecordMasTestResponse,
    RunningGroupMemberSchema,
    RunningGroupSchema,
    SkippedRunningGroupPlayer,
    SuggestRunningGroupsRequest,
    SuggestRunningGroupsResponse,
    TestPlanningResultSchema,
    TrainingZoneSchema,
)
from app.services.mas_testing import (
    MAS_TEST_PROTOCOLS,
    assign_running_groups,
    plan_next_mas_test,
    project_season_mas_test_events,
    recalculate_training_zones,
    record_mas_test,
    record_mas_test_batch,
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


@router.post("/record-batch", response_model=RecordMasTestBatchResponse)
def record_test_batch(
    payload: RecordMasTestBatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stap B van de MAS-test-kalenderflow (na protocolkeuze in stap A): de
    volledige kern in één 'Opslaan voor volledige groep'-actie, in plaats van
    een aparte opslag per speler. Spelers zonder ingevuld resultaat worden
    overgeslagen, niet de hele batch laten falen — skipped_player_ids toont
    wie nog ontbreekt. Elk opgeslagen resultaat gaat naar de mas_tests-tabel
    zodat het zowel de trainingszones als de toekomstige testplanning voedt,
    net als POST /record."""
    players = db.scalars(
        select(Player).where(Player.club_id == current_user.club_id, Player.is_active.is_(True))
    ).all()
    players_by_id = {p.id: p for p in players}
    for entry in payload.results:
        if entry.player_id not in players_by_id:
            raise HTTPException(status_code=404, detail=f"Player not found: {entry.player_id}")

    # record_mas_test_batch() is keyed by player_name (same acknowledged
    # limitation as flag_players() elsewhere in this codebase — two
    # same-named players in one club would collide); matched back to
    # player_id here via that name for persistence.
    name_to_player_id = {f"{p.first_name} {p.last_name}": pid for pid, p in players_by_id.items()}
    results = [
        {
            "player_name": f"{players_by_id[e.player_id].first_name} {players_by_id[e.player_id].last_name}",
            "raw_result_kmh": e.raw_result_kmh,
        }
        for e in payload.results
    ]

    try:
        batch = record_mas_test_batch(results, payload.protocol_key, payload.test_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    saved_player_ids = []
    for record in batch["records"]:
        player_id = name_to_player_id[record.player_name]
        db.add(
            MasTest(
                player_id=player_id,
                club_id=current_user.club_id,
                test_date=record.test_date,
                protocol=record.protocol_name,
                mas_kmh=record.mas_kmh,
                created_by=current_user.id,
            )
        )
        saved_player_ids.append(player_id)
    db.commit()

    synced = _sync_mas_test_calendar(current_user.club_id, db)

    skipped_player_ids = [name_to_player_id[name] for name in batch["skipped_players"]]
    return RecordMasTestBatchResponse(
        saved_player_ids=saved_player_ids,
        skipped_player_ids=skipped_player_ids,
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


def _group_training_zones(prescriptie_mas_kmh: float) -> list[TrainingZoneSchema]:
    return [TrainingZoneSchema.model_validate(z) for z in recalculate_training_zones(prescriptie_mas_kmh)]


@router.post("/running-groups/suggest", response_model=SuggestRunningGroupsResponse)
def suggest_running_groups(
    payload: SuggestRunningGroupsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stelt looptypegroepen voor op basis van elke actieve speler's laatste
    MAS-score (assign_running_groups) — dit is wat het bevestigingsscherm na
    een voltooide batch MAS-test toont, VOOR de coach bevestigt/aanpast.
    Persisteert nog niets; zie POST /running-groups/confirm."""
    players = db.scalars(
        select(Player).where(Player.club_id == current_user.club_id, Player.is_active.is_(True))
    ).all()

    players_mas: list[dict] = []
    skipped: list[SkippedRunningGroupPlayer] = []
    player_id_by_name: dict[str, uuid.UUID] = {}
    for player in players:
        name = f"{player.first_name} {player.last_name}"
        latest_mas = db.scalar(
            select(MasTest).where(MasTest.player_id == player.id).order_by(MasTest.test_date.desc()).limit(1)
        )
        if latest_mas is None:
            skipped.append(
                SkippedRunningGroupPlayer(player_id=player.id, player_name=name, reason="Geen MAS-test beschikbaar")
            )
            continue
        players_mas.append({"player_name": name, "mas_kmh": float(latest_mas.mas_kmh)})
        player_id_by_name[name] = player.id

    try:
        groups = assign_running_groups(players_mas, payload.num_groups)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    mas_by_name = {p["player_name"]: p["mas_kmh"] for p in players_mas}
    return SuggestRunningGroupsResponse(
        groups=[
            RunningGroupSchema(
                label=g.label,
                players=[
                    RunningGroupMemberSchema(
                        player_id=player_id_by_name[name], player_name=name, mas_kmh=mas_by_name[name]
                    )
                    for name in g.players
                ],
                prescriptie_mas_kmh=g.prescriptie_mas_kmh,
                avg_mas_kmh=g.avg_mas_kmh,
                min_mas_kmh=g.min_mas_kmh,
                max_mas_kmh=g.max_mas_kmh,
                training_zones=_group_training_zones(g.prescriptie_mas_kmh),
            )
            for g in groups
        ],
        skipped=skipped,
    )


@router.post("/running-groups/confirm", response_model=list[RunningGroupSchema])
def confirm_running_groups(
    payload: ConfirmRunningGroupsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bevestigt (eventueel door de coach aangepaste) looptypegroepen en
    vervangt de vorige bevestigde groepen van de club volledig — delete-then-
    recreate, geen diff/merge, net als _sync_mas_test_calendar hierboven.
    Alle stats (prescriptie/avg/min/max-MAS) worden hier SERVER-SIDE
    herberekend uit elke speler's laatste MAS-score, nooit vertrouwd van de
    client."""
    all_player_ids = [pid for g in payload.groups for pid in g.player_ids]
    if not all_player_ids:
        raise HTTPException(status_code=400, detail="Minstens één groep met spelers vereist.")
    if len(all_player_ids) != len(set(all_player_ids)):
        raise HTTPException(status_code=400, detail="Een speler kan niet in meer dan één groep tegelijk zitten.")

    players = db.scalars(
        select(Player).where(Player.club_id == current_user.club_id, Player.id.in_(all_player_ids))
    ).all()
    players_by_id = {p.id: p for p in players}
    missing = set(all_player_ids) - set(players_by_id)
    if missing:
        raise HTTPException(status_code=404, detail=f"Onbekende speler(s): {', '.join(str(m) for m in missing)}")

    db.execute(delete(DbRunningGroup).where(DbRunningGroup.club_id == current_user.club_id))
    db.flush()

    result_groups: list[RunningGroupSchema] = []
    for g in payload.groups:
        member_mas: list[tuple[Player, float]] = []
        for player_id in g.player_ids:
            player = players_by_id[player_id]
            latest_mas = db.scalar(
                select(MasTest).where(MasTest.player_id == player_id).order_by(MasTest.test_date.desc()).limit(1)
            )
            if latest_mas is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Geen MAS-test beschikbaar voor {player.first_name} {player.last_name} — "
                        f"kan groep '{g.label}' niet bevestigen."
                    ),
                )
            member_mas.append((player, float(latest_mas.mas_kmh)))

        mas_values = [mas for _, mas in member_mas]
        prescriptie = round(min(mas_values), 2)
        avg_mas = round(sum(mas_values) / len(mas_values), 2)
        min_mas = round(min(mas_values), 2)
        max_mas = round(max(mas_values), 2)

        db_group = DbRunningGroup(
            club_id=current_user.club_id,
            label=g.label,
            prescriptie_mas_kmh=prescriptie,
            avg_mas_kmh=avg_mas,
            min_mas_kmh=min_mas,
            max_mas_kmh=max_mas,
        )
        db.add(db_group)
        db.flush()
        for player, _ in member_mas:
            db.add(DbRunningGroupPlayer(running_group_id=db_group.id, player_id=player.id))

        result_groups.append(
            RunningGroupSchema(
                label=g.label,
                players=[
                    RunningGroupMemberSchema(
                        player_id=player.id, player_name=f"{player.first_name} {player.last_name}", mas_kmh=mas
                    )
                    for player, mas in member_mas
                ],
                prescriptie_mas_kmh=prescriptie,
                avg_mas_kmh=avg_mas,
                min_mas_kmh=min_mas,
                max_mas_kmh=max_mas,
                training_zones=_group_training_zones(prescriptie),
            )
        )

    db.commit()
    return result_groups


@router.get("/running-groups", response_model=list[RunningGroupSchema])
def get_running_groups(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """De laatst bevestigde looptypegroepen van de club, elk met de bijhorende
    groeps-interval-doelen (training_zones) — dit is wat elders gebruikt
    wordt om intervaldoelen per groep i.p.v. per individuele speler voor te
    stellen."""
    db_groups = db.scalars(
        select(DbRunningGroup)
        .where(DbRunningGroup.club_id == current_user.club_id)
        .order_by(DbRunningGroup.created_at)
    ).all()

    result = []
    for db_group in db_groups:
        members = []
        for gp in db_group.players:
            player = db.get(Player, gp.player_id)
            if player is None:
                continue
            latest_mas = db.scalar(
                select(MasTest).where(MasTest.player_id == player.id).order_by(MasTest.test_date.desc()).limit(1)
            )
            members.append(
                RunningGroupMemberSchema(
                    player_id=player.id,
                    player_name=f"{player.first_name} {player.last_name}",
                    mas_kmh=float(latest_mas.mas_kmh) if latest_mas else float(db_group.prescriptie_mas_kmh),
                )
            )
        result.append(
            RunningGroupSchema(
                label=db_group.label,
                players=members,
                prescriptie_mas_kmh=float(db_group.prescriptie_mas_kmh),
                avg_mas_kmh=float(db_group.avg_mas_kmh),
                min_mas_kmh=float(db_group.min_mas_kmh),
                max_mas_kmh=float(db_group.max_mas_kmh),
                training_zones=_group_training_zones(float(db_group.prescriptie_mas_kmh)),
            )
        )
    return result
