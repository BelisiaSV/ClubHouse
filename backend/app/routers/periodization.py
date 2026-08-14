import uuid
from datetime import date, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_module
from app.models import Club
from app.models import CycleLength as DbCycleLength
from app.models import Match as DbMatch
from app.models import MatchStatus as DbMatchStatus
from app.models import TrainingCycle as DbTrainingCycle
from app.models import TrainingCycleWeek as DbTrainingCycleWeek
from app.models import User
from app.models import WeekFocus as DbWeekFocus
from app.schemas_dashboards import (
    BuildCycleRequest,
    CurrentCyclesResponse,
    NextCycleRequest,
    PatchActiveCycleRequest,
    QueueNextCycleRequest,
    RescheduleCycleRequest,
    StartSeasonRequest,
    StartSeasonResponse,
    TrainingCycleSchema,
    WeeklyKmOverviewSchema,
)
from app.services.periodization import CycleWeek as ServiceCycleWeek
from app.services.periodization import Season
from app.services.periodization import TrainingCycle as ServiceTrainingCycle
from app.services.periodization import WeekFocus as ServiceWeekFocus
from app.services.periodization import align_cycle_to_nearest_match, build_cycle
from app.services.periodization import edit_active_cycle as svc_edit_active_cycle
from app.services.periodization import get_active_cycle_and_week, handle_match_cancellation
from app.services.periodization import queue_next_cycle as svc_queue_next_cycle
from app.services.periodization import start_new_season as svc_start_new_season
from app.services.platform_admin import ModuleKey
from app.services.volume_planning import generate_weekly_km_overview_by_position

router = APIRouter(
    prefix="/api/periodization", tags=["periodization"], dependencies=[Depends(require_module(ModuleKey.KALENDER))]
)

_LENGTH_WEEKS_TO_DB = {
    4: DbCycleLength.FOUR_WEEKS,
    6: DbCycleLength.SIX_WEEKS,
    8: DbCycleLength.EIGHT_WEEKS,
}
_DB_LENGTH_TO_WEEKS = {v: k for k, v in _LENGTH_WEEKS_TO_DB.items()}


def _club_match_dates(club_id: uuid.UUID, db: Session) -> list[date]:
    """Real Match rows (scheduled/played), normalized to UTC calendar dates
    — shared by _load_cycle_from_db's per-week match counting and
    realign_season_to_matches's cycle-alignment, so both agree on exactly
    which matches count."""
    return [
        d.astimezone(timezone.utc).date()
        for d in db.scalars(
            select(DbMatch.match_date).where(
                DbMatch.club_id == club_id,
                DbMatch.status.in_([DbMatchStatus.SCHEDULED, DbMatchStatus.PLAYED]),
            )
        ).all()
    ]


def _load_cycle_from_db(db_cycle: DbTrainingCycle, club: Club, db: Session) -> ServiceTrainingCycle:
    """DB rows -> one service TrainingCycle, with num_matches/num_trainings
    per week actually computed instead of left at CycleWeek's bare dataclass
    defaults (0 / 2) — needed for generate_cycle_km_plan()/
    generate_weekly_km_overview_by_position() to mean anything:
    - num_trainings: club.training_weekdays' length (see
      app.services.rpe_wellness's docstring for why that's the only source
      of "which weekdays does this club train on"); falls back to the
      CycleWeek default of 2 if that's not configured yet.
    - num_matches: real Match rows (scheduled/played, not postponed/
      cancelled) whose date falls inside that week."""
    week_rows = db.scalars(
        select(DbTrainingCycleWeek)
        .where(DbTrainingCycleWeek.training_cycle_id == db_cycle.id)
        .order_by(DbTrainingCycleWeek.week_number)
    ).all()

    num_trainings = len(club.training_weekdays) if club.training_weekdays else 2

    # Fetched once for the whole club and filtered in Python rather than a
    # per-week query with a date-range WHERE clause — simpler than juggling
    # match_date's timestamptz vs. the weeks' plain dates, and cheap at the
    # data volumes a single club ever has.
    match_dates = _club_match_dates(club.id, db)

    weeks = []
    for i, w in enumerate(week_rows):
        week_end = week_rows[i + 1].week_start_date if i + 1 < len(week_rows) else db_cycle.end_date
        num_matches = sum(1 for d in match_dates if w.week_start_date <= d < week_end)
        weeks.append(
            ServiceCycleWeek(
                week_number=w.week_number,
                week_start_date=w.week_start_date,
                focus=ServiceWeekFocus(w.focus.value),
                planned_load_pct=float(w.planned_load_pct or 0),
                num_matches=num_matches,
                num_trainings=num_trainings,
            )
        )

    return ServiceTrainingCycle(
        name=db_cycle.name,
        length_weeks=_DB_LENGTH_TO_WEEKS[db_cycle.length_type],
        start_date=db_cycle.start_date,
        target_match_date=db_cycle.target_match_date,
        target_peak_weekly_km=float(db_cycle.target_peak_weekly_km),
        weeks=weeks,
        shift_count=db_cycle.shift_count,
    )


def load_season_from_db(club_id: uuid.UUID, db: Session) -> tuple[Season, list[uuid.UUID]]:
    """Reconstructs a Season (all of the club's cycles, chronologically) from
    training_cycles/training_cycle_weeks, DB rows -> service dataclasses. The
    club's DB is_active flag is deliberately ignored here — which cycle/week
    counts as active is always recomputed dynamically from dates (see
    Season.get_active_cycle_and_week's docstring), never trusted from a
    static column. Returns the Season alongside a parallel list of each
    cycle's DB id (same order as season.cycles), so callers can tell whether
    queue_next_cycle() appended a brand new cycle or overwrote the existing
    last one, and persist accordingly."""
    club = db.get(Club, club_id)
    db_cycles = db.scalars(
        select(DbTrainingCycle).where(DbTrainingCycle.club_id == club_id).order_by(DbTrainingCycle.start_date)
    ).all()
    season = Season(name="Season")
    cycle_db_ids: list[uuid.UUID] = []
    for db_cycle in db_cycles:
        season.cycles.append(_load_cycle_from_db(db_cycle, club, db))
        cycle_db_ids.append(db_cycle.id)
    return season, cycle_db_ids


def realign_season_to_matches(club_id: uuid.UUID, db: Session) -> None:
    """Re-aligns every one of the club's cycles' realization week to the
    nearest real match (services.periodization.align_cycle_to_nearest_match)
    — call this whenever a match is added or changed (see
    app/routers/matches.py), instead of the coach entering a target match
    date by hand when choosing a cycle. A cycle with no match nearby is left
    on its template position, unchanged."""
    season, cycle_db_ids = load_season_from_db(club_id, db)
    match_dates = _club_match_dates(club_id, db)

    changed = False
    for cycle, db_cycle_id in zip(season.cycles, cycle_db_ids):
        chosen = align_cycle_to_nearest_match(cycle, match_dates)
        if chosen is None:
            continue
        changed = True
        db_cycle = db.get(DbTrainingCycle, db_cycle_id)
        db_cycle.target_match_date = chosen
        week_rows = {
            w.week_number: w
            for w in db.scalars(
                select(DbTrainingCycleWeek).where(DbTrainingCycleWeek.training_cycle_id == db_cycle_id)
            ).all()
        }
        for week in cycle.weeks:
            row = week_rows.get(week.week_number)
            if row is not None:
                row.focus = DbWeekFocus(week.focus.value)
                row.planned_load_pct = week.planned_load_pct

    if changed:
        db.commit()


def _persist_as_active_cycle(cycle, club_id, db: Session) -> DbTrainingCycle:
    """Stores the computed cycle as the club's one active training cycle, so
    server-side lookups (e.g. POST /api/makeup-programs/generate-for-match) can
    resolve "the active cycle/week" without the frontend re-sending it."""
    for existing in db.scalars(
        select(DbTrainingCycle).where(DbTrainingCycle.club_id == club_id, DbTrainingCycle.is_active.is_(True))
    ):
        existing.is_active = False

    db_cycle = DbTrainingCycle(
        club_id=club_id,
        name=cycle.name,
        length_type=_LENGTH_WEEKS_TO_DB[cycle.length_weeks],
        start_date=cycle.start_date,
        end_date=cycle.end_date(),
        target_match_date=cycle.target_match_date,
        target_peak_weekly_km=cycle.target_peak_weekly_km,
        is_active=True,
        shift_count=cycle.shift_count,
    )
    db.add(db_cycle)
    db.flush()

    for week in cycle.weeks:
        db.add(
            DbTrainingCycleWeek(
                training_cycle_id=db_cycle.id,
                week_number=week.week_number,
                week_start_date=week.week_start_date,
                focus=DbWeekFocus(week.focus.value),
                planned_load_pct=week.planned_load_pct,
            )
        )
    db.commit()
    db.refresh(db_cycle)
    return db_cycle


@router.post("/cycles", response_model=TrainingCycleSchema)
def create_cycle(
    payload: BuildCycleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cycle = build_cycle(
        name=payload.name,
        length_weeks=payload.length_weeks,
        start_date=payload.start_date,
        target_match_date=payload.target_match_date,
        target_peak_weekly_km=payload.target_peak_weekly_km,
    )
    _persist_as_active_cycle(cycle, current_user.club_id, db)
    return TrainingCycleSchema.model_validate(cycle)


@router.post("/cycles/reschedule", response_model=TrainingCycleSchema)
def reschedule_cycle(payload: RescheduleCycleRequest, current_user: User = Depends(get_current_user)):
    """Herberekent een cyclus wanneer de doelwedstrijd wordt afgelast: schuift de
    resterende weken op en injecteert onderhoudsweken zodat er geen trainingsgat
    ontstaat."""
    cycle = payload.cycle.to_dataclass()
    try:
        updated = handle_match_cancellation(
            cycle,
            cancelled_match_date=payload.cancelled_match_date,
            new_match_date=payload.new_match_date,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TrainingCycleSchema.model_validate(updated)


def _persist_queued_cycle(
    season: Season,
    cycles_before: int,
    cycle_db_ids: list[uuid.UUID],
    result: ServiceTrainingCycle,
    club_id: uuid.UUID,
    db: Session,
) -> DbTrainingCycle:
    """Shared by POST /cycles/queue-next and POST /seasons/{id}/next-cycle —
    both just call services.periodization.queue_next_cycle() against a
    Season loaded a different way (whole-club vs. one season/club, see
    load_season_from_db) and then need the identical append-or-overwrite
    persistence svc_queue_next_cycle's docstring describes."""
    if len(season.cycles) > cycles_before:
        db_cycle = DbTrainingCycle(
            club_id=club_id,
            name=result.name,
            length_type=_LENGTH_WEEKS_TO_DB[result.length_weeks],
            start_date=result.start_date,
            end_date=result.end_date(),
            target_match_date=result.target_match_date,
            target_peak_weekly_km=result.target_peak_weekly_km,
            is_active=False,
            shift_count=result.shift_count,
        )
        db.add(db_cycle)
        db.flush()
    else:
        db_cycle = db.get(DbTrainingCycle, cycle_db_ids[-1])
        db_cycle.name = result.name
        db_cycle.length_type = _LENGTH_WEEKS_TO_DB[result.length_weeks]
        db_cycle.end_date = result.end_date()
        db_cycle.target_match_date = result.target_match_date
        db_cycle.target_peak_weekly_km = result.target_peak_weekly_km
        db_cycle.shift_count = result.shift_count
        db.execute(delete(DbTrainingCycleWeek).where(DbTrainingCycleWeek.training_cycle_id == db_cycle.id))
        db.flush()

    for week in result.weeks:
        db.add(
            DbTrainingCycleWeek(
                training_cycle_id=db_cycle.id,
                week_number=week.week_number,
                week_start_date=week.week_start_date,
                focus=DbWeekFocus(week.focus.value),
                planned_load_pct=week.planned_load_pct,
            )
        )
    db.commit()
    db.refresh(db_cycle)
    return db_cycle


@router.post("/cycles/queue-next", response_model=TrainingCycleSchema)
def queue_next_cycle_endpoint(
    payload: QueueNextCycleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """De weekselector: stelt de eerstvolgende cyclus in zonder de actieve,
    lopende cyclus aan te raken. Een tweede aanroep terwijl de actieve cyclus
    nog loopt overschrijft de klaargezette (nog niet gestarte) volgende
    cyclus — geen 400 meer, want van gedachte veranderen over een cyclus die
    nog niet gestart is, is geen foutgeval (zie services.periodization.
    queue_next_cycle's docstring)."""
    today = date.today()
    season, cycle_db_ids = load_season_from_db(current_user.club_id, db)
    cycles_before = len(season.cycles)

    try:
        result = svc_queue_next_cycle(
            season,
            length_weeks=payload.length_weeks,
            target_match_date=payload.target_match_date,
            today=today,
            target_peak_weekly_km=payload.target_peak_weekly_km,
            name=payload.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _persist_queued_cycle(season, cycles_before, cycle_db_ids, result, current_user.club_id, db)
    return TrainingCycleSchema.model_validate(result)


def _find_cycle_index(season: Season, cycle: ServiceTrainingCycle) -> int:
    return next(i for i, c in enumerate(season.cycles) if c is cycle)


@router.get("/cycles/current", response_model=CurrentCyclesResponse)
def get_current_cycles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Voor de Instellingen-pagina: de actieve cyclus (dynamisch bepaald,
    nooit de statische is_active-kolom) en de klaargezette volgende cyclus,
    als die er is — zodat de coach beide op elk moment kan zien en
    aanpassen in plaats van enkel blind een nieuwe te kunnen klaarzetten."""
    today = date.today()
    season, cycle_db_ids = load_season_from_db(current_user.club_id, db)
    active_cycle, _ = get_active_cycle_and_week(season, today)

    active_schema = None
    if active_cycle is not None:
        idx = _find_cycle_index(season, active_cycle)
        active_schema = TrainingCycleSchema.model_validate(active_cycle).model_copy(
            update={"id": cycle_db_ids[idx]}
        )

    queued_schema = None
    if season.cycles and (active_cycle is None or season.cycles[-1] is not active_cycle):
        queued_cycle = season.cycles[-1]
        if queued_cycle.start_date > today:
            queued_schema = TrainingCycleSchema.model_validate(queued_cycle).model_copy(
                update={"id": cycle_db_ids[-1]}
            )

    can_edit_active_cycle = bool(active_cycle is not None and season.cycles[-1] is active_cycle)
    return CurrentCyclesResponse(active=active_schema, queued=queued_schema, can_edit_active_cycle=can_edit_active_cycle)


@router.patch("/cycles/active", response_model=TrainingCycleSchema)
def patch_active_cycle(
    payload: PatchActiveCycleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Past de lopende, actieve cyclus aan. Naam en piekvolume zijn altijd
    veilig aan te passen in-place. start_date/length_weeks zijn structureel
    (herbouwen de weken volledig, via services.periodization.
    edit_active_cycle) en enkel toegestaan zolang er nog geen volgende
    cyclus is klaargezet — zie dat functiedoc voor waarom."""
    today = date.today()
    season, cycle_db_ids = load_season_from_db(current_user.club_id, db)
    active_cycle, _ = get_active_cycle_and_week(season, today)
    if active_cycle is None:
        raise HTTPException(status_code=404, detail="Geen actieve cyclus gevonden.")

    idx = _find_cycle_index(season, active_cycle)
    db_cycle = db.get(DbTrainingCycle, cycle_db_ids[idx])
    updates = payload.model_dump(exclude_unset=True)

    if "start_date" in updates or "length_weeks" in updates:
        try:
            result = svc_edit_active_cycle(
                season, today,
                new_start_date=updates.get("start_date"),
                new_length_weeks=updates.get("length_weeks"),
                new_target_peak_weekly_km=updates.get("target_peak_weekly_km"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if "name" in updates:
            result.name = updates["name"]

        db_cycle.name = result.name
        db_cycle.length_type = _LENGTH_WEEKS_TO_DB[result.length_weeks]
        db_cycle.start_date = result.start_date
        db_cycle.end_date = result.end_date()
        db_cycle.target_peak_weekly_km = result.target_peak_weekly_km
        db.execute(delete(DbTrainingCycleWeek).where(DbTrainingCycleWeek.training_cycle_id == db_cycle.id))
        db.flush()
        for week in result.weeks:
            db.add(
                DbTrainingCycleWeek(
                    training_cycle_id=db_cycle.id,
                    week_number=week.week_number,
                    week_start_date=week.week_start_date,
                    focus=DbWeekFocus(week.focus.value),
                    planned_load_pct=week.planned_load_pct,
                )
            )
        db.commit()
        db.refresh(db_cycle)

        # A corrected start date/length can shift which real matches now
        # fall inside the cycle's window — re-align immediately rather
        # than leaving target_match_date on whatever the old window picked.
        realign_season_to_matches(current_user.club_id, db)
        db.refresh(db_cycle)
        active_cycle = result
    else:
        if "name" in updates:
            active_cycle.name = updates["name"]
            db_cycle.name = updates["name"]
        if "target_peak_weekly_km" in updates:
            active_cycle.target_peak_weekly_km = updates["target_peak_weekly_km"]
            db_cycle.target_peak_weekly_km = updates["target_peak_weekly_km"]
        db.commit()

    return TrainingCycleSchema.model_validate(active_cycle).model_copy(
        update={"id": db_cycle.id, "target_match_date": db_cycle.target_match_date}
    )


@router.get("/training-cycles/{cycle_id}/km-overview", response_model=list[WeeklyKmOverviewSchema])
def get_km_overview(
    cycle_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Per week van de cyclus: teamtotaal + uitsplitsing training/wedstrijd/
    totaal per positie (services.volume_planning.
    generate_weekly_km_overview_by_position)."""
    db_cycle = db.get(DbTrainingCycle, cycle_id)
    if db_cycle is None or db_cycle.club_id != current_user.club_id:
        raise HTTPException(status_code=404, detail="Cyclus niet gevonden.")

    club = db.get(Club, current_user.club_id)
    cycle = _load_cycle_from_db(db_cycle, club, db)
    overview = generate_weekly_km_overview_by_position(cycle)
    return [WeeklyKmOverviewSchema.model_validate(o) for o in overview]


@router.post("/seasons", response_model=StartSeasonResponse)
def start_season(
    payload: StartSeasonRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start het allereerste seizoen van een club: enige plek waar een
    startdatum nog expliciet ingegeven wordt (services.periodization.
    start_new_season). Elke cyclus daarna gaat via POST /seasons/{season_id}
    /next-cycle, waar de datum altijd automatisch aansluit op het einde van
    de vorige cyclus.

    Er bestaat geen aparte 'seizoenen'-tabel — season_id in de respons is
    de club_id zelf, wat de club in dit datamodel al is: één doorlopende
    cyclusgeschiedenis. Weigert de aanvraag (409) als er al cyclussen
    bestaan, want dat zou een tweede, mogelijk overlappende geschiedenis
    naast de eerste creëren in plaats van hem netjes te vervolgen — daarvoor
    is next-cycle er net."""
    existing = db.scalar(select(DbTrainingCycle.id).where(DbTrainingCycle.club_id == current_user.club_id).limit(1))
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="Er loopt al een seizoen voor deze club. Gebruik next-cycle om een cyclus toe te voegen.",
        )

    season = svc_start_new_season(
        name=payload.name,
        start_date=payload.start_date,
        length_weeks=payload.length_weeks,
        target_match_date=payload.target_match_date,
        target_peak_weekly_km=payload.target_peak_weekly_km,
    )
    db_cycle = _persist_as_active_cycle(season.cycles[0], current_user.club_id, db)
    return StartSeasonResponse(
        season_id=current_user.club_id,
        cycle=TrainingCycleSchema.model_validate(season.cycles[0]).model_copy(update={"id": db_cycle.id}),
    )


@router.post("/seasons/{season_id}/next-cycle", response_model=TrainingCycleSchema)
def next_cycle(
    season_id: uuid.UUID,
    payload: NextCycleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stelt de eerstvolgende cyclus in (services.periodization.
    queue_next_cycle) — zelfde gedrag als POST /cycles/queue-next, onder de
    seizoens-gerichte URL. Geen datumveld: de startdatum wordt altijd
    automatisch afgeleid van het einde van de vorige cyclus, nooit door de
    client meegegeven — start_date staat enkel in het requestschema om hem
    hier expliciet te kunnen weigeren in plaats van hem stilzwijgend te
    negeren."""
    if season_id != current_user.club_id:
        raise HTTPException(status_code=404, detail="Seizoen niet gevonden.")
    if payload.start_date is not None:
        raise HTTPException(
            status_code=400,
            detail="start_date is hier niet toegestaan — de datum wordt automatisch bepaald op basis van "
            "het einde van de vorige cyclus.",
        )

    today = date.today()
    season, cycle_db_ids = load_season_from_db(current_user.club_id, db)
    cycles_before = len(season.cycles)

    try:
        result = svc_queue_next_cycle(
            season,
            length_weeks=payload.length_weeks,
            target_match_date=payload.target_match_date,
            today=today,
            target_peak_weekly_km=payload.target_peak_weekly_km,
            name=payload.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _persist_queued_cycle(season, cycles_before, cycle_db_ids, result, current_user.club_id, db)
    return TrainingCycleSchema.model_validate(result)
