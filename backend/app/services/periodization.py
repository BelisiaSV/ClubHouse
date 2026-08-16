"""
periodization.py

Gedeeld datamodel (WeekFocus, CycleWeek, TrainingCycle, cyclustemplates) plus
de periodiseringslogica: cyclus opbouwen en herberekenen bij afgelasting.

Dit is de canonieke bron voor WeekFocus/CycleWeek/TrainingCycle — de andere
services-modules (mas_testing, makeup_programs, team_readiness, volume_planning)
importeren deze types vanuit hier in plaats van ze te herdefiniëren.

Zuiver en side-effect-vrij: geen databasetoegang. De FastAPI-routers halen de
benodigde data op en roepen deze bouwstenen aan.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Optional


# =============================================================
# 0. GEDEELD DATAMODEL
# =============================================================

class WeekFocus(str, Enum):
    ACCUMULATION = "accumulation"
    INTENSIFICATION = "intensification"
    REALIZATION = "realization"
    DELOAD = "deload"
    RECOVERY = "recovery"


@dataclass
class CycleWeek:
    week_number: int
    week_start_date: date
    focus: WeekFocus
    planned_load_pct: float
    num_matches: int = 0           # wedstrijden gepland/gespeeld die week
    num_trainings: int = 2         # amateur/provinciale reeksen: doorgaans 2x/week


@dataclass
class TrainingCycle:
    name: str
    length_weeks: int              # 4, 6 of 8
    start_date: date
    # Optioneel: bij het kiezen van een cyclus is de exacte doelwedstrijd vaak
    # nog niet gekend — target_match_date wordt daarna automatisch bepaald door
    # align_cycle_to_nearest_match() zodra er effectief wedstrijden in de
    # kalender staan, in plaats van dat de coach dit handmatig moet invullen.
    target_match_date: Optional[date] = None
    target_peak_weekly_km: float = 23.0   # door coach bepaald piekvolume (100%-week)
    weeks: list = field(default_factory=list)   # list[CycleWeek]
    shift_count: int = 0

    def end_date(self) -> date:
        return self.start_date + timedelta(weeks=self.length_weeks)


LOAD_PCT_BY_FOCUS = {
    # VOLUME-curve (km/trainingsduur) — bewust OMGEKEERD aan de intensiteitscurve
    # in de sessieprofielen (die correct oploopt naar de realisatieweek).
    #
    # Klassiek periodiseringsmodel (Matveyev/Bompa): volume bouwt op in de
    # voorbereidende/accumulatiefase, waarna intensiteit stijgt richting de
    # wedstrijdspecifieke fase terwijl het volume geleidelijk afneemt
    # ("tapering"). Cruciaal injuriepreventie-argument: zouden volume én
    # intensiteit allebei in dezelfde week pieken, dan stapelt dat twee
    # afzonderlijke risicofactoren in exact dezelfde week — dat vermijdt
    # deze curve bewust.
    WeekFocus.ACCUMULATION: 100.0,      # piekvolume, lagere intensiteit
    WeekFocus.INTENSIFICATION: 90.0,    # licht dalend volume, stijgende intensiteit
    WeekFocus.REALIZATION: 75.0,        # verder getaperd volume, piekintensiteit/wedstrijdspecificiteit
    WeekFocus.DELOAD: 50.0,             # scherpe taper, voor supercompensatie
    WeekFocus.RECOVERY: 40.0,
}

CYCLE_TEMPLATES = {
    4: [WeekFocus.ACCUMULATION, WeekFocus.INTENSIFICATION,
        WeekFocus.REALIZATION, WeekFocus.DELOAD],
    6: [WeekFocus.ACCUMULATION, WeekFocus.ACCUMULATION, WeekFocus.INTENSIFICATION,
        WeekFocus.INTENSIFICATION, WeekFocus.REALIZATION, WeekFocus.DELOAD],
    # 8 weken: middencyclus-hersteldip (RECOVERY, week 4) vóór de tweede
    # opbouw — voorkomt dat vermoeidheid zich 7 weken lang opstapelt vóór
    # de eerste rust, en geeft de tweede intensificatie/realisatie-fase
    # een frissere basis om op te bouwen.
    8: [WeekFocus.ACCUMULATION, WeekFocus.ACCUMULATION, WeekFocus.INTENSIFICATION,
        WeekFocus.RECOVERY, WeekFocus.INTENSIFICATION, WeekFocus.REALIZATION,
        WeekFocus.REALIZATION, WeekFocus.DELOAD],
}


def build_cycle(name: str, length_weeks: int, start_date: date,
                 target_match_date: Optional[date] = None, target_peak_weekly_km: float = 23.0) -> TrainingCycle:
    template = CYCLE_TEMPLATES[length_weeks]
    cycle = TrainingCycle(
        name=name, length_weeks=length_weeks, start_date=start_date,
        target_match_date=target_match_date, target_peak_weekly_km=target_peak_weekly_km,
    )
    for i, focus in enumerate(template):
        cycle.weeks.append(CycleWeek(
            week_number=i + 1,
            week_start_date=start_date + timedelta(weeks=i),
            focus=focus,
            planned_load_pct=LOAD_PCT_BY_FOCUS[focus],
        ))
    return cycle


# --- Seizoen: aaneengeschakelde cyclussen van variabele lengte ------------
# Een coach kan bv. een voorbereidingscyclus van 8 weken laten volgen door
# herhaalde competitiecyclussen van 4 weken — elke nieuwe cyclus start
# exact waar de vorige eindigt, zodat er geen gaten of overlap ontstaan.

@dataclass
class Season:
    name: str
    cycles: list = field(default_factory=list)   # list[TrainingCycle], op volgorde


def add_cycle_to_season(
    season: Season,
    length_weeks: int,
    target_match_date: Optional[date] = None,
    target_peak_weekly_km: float = 23.0,
    name: Optional[str] = None,
    start_date: Optional[date] = None,
) -> TrainingCycle:
    """
    Voegt een nieuwe cyclus toe ná de laatste cyclus in het seizoen.
    start_date is enkel verplicht voor de EERSTE cyclus van het seizoen;
    daarna wordt automatisch aangesloten op cycles[-1].end_date().
    """
    if season.cycles:
        resolved_start = season.cycles[-1].end_date()
    elif start_date is not None:
        resolved_start = start_date
    else:
        raise ValueError("De eerste cyclus van een seizoen vereist een expliciete start_date.")

    cycle_name = name or f"Cyclus {len(season.cycles) + 1} ({length_weeks}w)"
    cycle = build_cycle(cycle_name, length_weeks, resolved_start, target_match_date, target_peak_weekly_km)
    season.cycles.append(cycle)
    return cycle


def get_active_cycle_and_week(season: Season, today: date):
    """
    Zoekt DYNAMISCH welke cyclus en welke week van die cyclus vandaag geldig
    is. Dit moet bij ELKE klik op 'Maak schema's' of het 'Next training'-
    tabblad opnieuw aangeroepen worden — nooit een cyclus/week statisch
    doorgeven of cachen, want de coach kan een cyclus tussentijds aanpassen
    (afgelasting, cyclus vroeger/later starten, etc.).

    Geeft (cycle, week) terug, of (None, None) als vandaag buiten elke
    cyclus in het seizoen valt (bv. een pauze tussen twee cyclussen).
    """
    for cycle in season.cycles:
        if cycle.start_date <= today < cycle.end_date():
            for i, week in enumerate(cycle.weeks):
                next_week_start = (cycle.weeks[i + 1].week_start_date
                                    if i + 1 < len(cycle.weeks) else cycle.end_date())
                if week.week_start_date <= today < next_week_start:
                    return cycle, week
    return None, None


def queue_next_cycle(
    season: Season,
    length_weeks: int,
    today: date,
    target_match_date: Optional[date] = None,
    target_peak_weekly_km: float = 23.0,
    name: Optional[str] = None,
) -> TrainingCycle:
    """
    Stelt de EERSTVOLGENDE cyclus in — via de weekselector op het dashboard.
    De ACTIEVE, lopende cyclus wordt hier nooit door aangeraakt.

    - Geen actieve cyclus? Nieuwe cyclus start vandaag (of overschrijft een
      reeds voor vandaag klaargezette, nog niet gestarte eerste cyclus).
    - Actieve cyclus is de laatste in de lijst (nog niets klaargezet)?
      Nieuwe cyclus wordt toegevoegd ná het einde van de actieve cyclus.
    - Staat er al een volgende cyclus klaar, maar is die nog NIET gestart?
      Dan mag de coach van gedachte veranderen (misklik, andere keuze) —
      de klaargezette cyclus wordt overschreven, met behoud van dezelfde
      startdatum (meteen na de actieve cyclus). De actieve cyclus zelf
      verandert hierdoor niet.
    """
    active_cycle, _ = get_active_cycle_and_week(season, today)

    if active_cycle is None:
        if season.cycles and season.cycles[-1].start_date > today:
            queued = season.cycles[-1]
            new_cycle = build_cycle(name or queued.name, length_weeks, queued.start_date,
                                     target_match_date, target_peak_weekly_km)
            season.cycles[-1] = new_cycle
            return new_cycle
        return add_cycle_to_season(season, length_weeks, target_match_date,
                                    target_peak_weekly_km, name, start_date=today)

    if season.cycles[-1] is active_cycle:
        return add_cycle_to_season(season, length_weeks, target_match_date,
                                    target_peak_weekly_km, name)

    queued_cycle = season.cycles[-1]
    if queued_cycle.start_date <= today:
        # Veiligheidscheck: zou hier normaal niet voorkomen (dan zou hij actief zijn).
        raise ValueError("De klaargezette cyclus is intussen gestart en kan niet meer aangepast worden.")

    updated_cycle = build_cycle(name or queued_cycle.name, length_weeks, queued_cycle.start_date,
                                 target_match_date, target_peak_weekly_km)
    season.cycles[-1] = updated_cycle
    return updated_cycle


# --- Seizoensstart: expliciete eerste-cyclus-flow ------------------------
# Elke trainer start zijn seizoen op een andere datum. De EERSTE cyclus van
# een seizoen vraagt dus expliciet een startdatum; ELKE cyclus DAARNA (via
# queue_next_cycle hierboven) sluit automatisch aan op het einde van de
# vorige — geen datum meer nodig. Apart, herkenbaar entrypoint zodat
# 'seizoen starten' en 'volgende cyclus kiezen' twee duidelijk gescheiden
# acties in de API worden (app/routers/periodization.py's POST /seasons vs.
# POST /seasons/{season_id}/next-cycle).

def start_new_season(
    name: str,
    start_date: date,
    length_weeks: int,
    target_match_date: Optional[date] = None,
    target_peak_weekly_km: float = 23.0,
) -> Season:
    """Start een nieuw seizoen: de trainer geeft ÉÉN keer een startdatum in,
    voor de allereerste cyclus — geen doelwedstrijddatum, die hoort hier niet
    thuis (vaak nog niet gekend). Elke volgende cyclus wordt nadien gekozen
    via queue_next_cycle(), waar ook geen datum-invoer meer nodig is; de
    doelwedstrijddatum wordt pas later, automatisch, bepaald via
    align_cycle_to_nearest_match() zodra er effectief wedstrijden in de
    kalender staan."""
    if length_weeks not in CYCLE_TEMPLATES:
        raise ValueError(f"Ongeldige cycluslengte: {length_weeks} (kies 4, 6 of 8).")
    season = Season(name=name)
    add_cycle_to_season(
        season, length_weeks=length_weeks, target_match_date=target_match_date,
        target_peak_weekly_km=target_peak_weekly_km, name=f"{name} — Cyclus 1", start_date=start_date,
    )
    return season


def edit_active_cycle(
    season: Season,
    today: date,
    new_start_date: Optional[date] = None,
    new_length_weeks: Optional[int] = None,
    new_target_peak_weekly_km: Optional[float] = None,
) -> list[TrainingCycle]:
    """Corrigeert de ACTIEVE cyclus (startdatum en/of lengte en/of piekvolume)
    — voor wanneer de coach zich vergist heeft bij het instellen ervan, of
    gewoon een andere startdatum wil. Elke cyclus die al ná de actieve
    klaargezet stond, schuift automatisch mee (elk sluit weer naadloos aan op
    het einde van de vorige, net als add_cycle_to_season dat bij het eerst
    aanmaken doet) in plaats van de wijziging te blokkeren zodra er al een
    volgende cyclus bestaat — die klaargezette cyclus is per definitie nog
    niet gestart, dus er is nooit al trainingsdata (MAS-testen, RPE, km) op
    haar datums gelogd die zou ontsporen.

    Geeft de aangepaste cycli terug in seizoensvolgorde, te beginnen bij de
    actieve cyclus zelf gevolgd door elke cascaded-herbouwde cyclus erna —
    de aanroeper (router) moet ze allemaal persisteren."""
    active_cycle, _ = get_active_cycle_and_week(season, today)
    if active_cycle is None:
        raise ValueError("Geen actieve cyclus gevonden.")

    idx = season.cycles.index(active_cycle)
    length_weeks = new_length_weeks or active_cycle.length_weeks
    if length_weeks not in CYCLE_TEMPLATES:
        raise ValueError(f"Ongeldige cycluslengte: {length_weeks} (kies 4, 6 of 8).")

    corrected = build_cycle(
        name=active_cycle.name, length_weeks=length_weeks,
        start_date=new_start_date or active_cycle.start_date,
        target_match_date=active_cycle.target_match_date,
        target_peak_weekly_km=new_target_peak_weekly_km or active_cycle.target_peak_weekly_km,
    )
    season.cycles[idx] = corrected
    changed = [corrected]

    cursor_end = corrected.end_date()
    for i in range(idx + 1, len(season.cycles)):
        queued = season.cycles[i]
        rebuilt = build_cycle(
            name=queued.name, length_weeks=queued.length_weeks, start_date=cursor_end,
            target_match_date=None, target_peak_weekly_km=queued.target_peak_weekly_km,
        )
        season.cycles[i] = rebuilt
        changed.append(rebuilt)
        cursor_end = rebuilt.end_date()

    return changed


def align_cycle_to_nearest_match(cycle: TrainingCycle, match_dates: list) -> Optional[date]:
    """Lijnt de realisatieweek van een cyclus automatisch uit op de
    dichtstbijzijnde ECHTE wedstrijd uit de kalender, in plaats van dat de
    coach bij het kiezen van een cyclus handmatig een 'doelwedstrijddatum'
    moet invullen. Wordt aangeroepen telkens een wedstrijd wordt toegevoegd/
    gewijzigd in de kalender (zie app/routers/matches.py) — geen eenmalige,
    statische instelling.

    Herstelt EERST de zuivere CYCLE_TEMPLATES-volgorde voor elke week (enkel
    veilig op een structureel ongewijzigde cyclus, shift_count == 0 — een
    cyclus die al door handle_match_cancellation() herschikt is, telt niet
    meer 1-op-1 met het sjabloon en wordt hier met rust gelaten) vóór de
    nieuw gekozen week als REALIZATION gemarkeerd wordt. Zonder deze reset
    blijft een EERDER gekozen week voor altijd op REALIZATION staan telkens
    de 'dichtstbijzijnde wedstrijd' verschuift naar een andere week (bv. na
    het toevoegen/verplaatsen van een wedstrijd) — build_cycle()/
    CYCLE_TEMPLATES's contiguë fasevolgorde raakt dan zichtbaar door elkaar
    (bv. Intensificatie → Realisatie → Intensificatie → Realisatie i.p.v.
    aaneengesloten blokken), ook al is CYCLE_TEMPLATES zelf altijd correct
    gebleven.

    Geeft de gekozen datum terug, of None als er geen enkele wedstrijd binnen
    een redelijk venster van de cyclus valt (dan blijft de realisatieweek op
    de sjabloonpositie staan)."""
    if not match_dates:
        return None
    candidates = [d for d in match_dates if cycle.start_date <= d <= cycle.end_date() + timedelta(days=7)]
    if not candidates:
        return None
    chosen = min(candidates, key=lambda d: abs((d - cycle.end_date()).days))
    cycle.target_match_date = chosen

    if cycle.shift_count == 0:
        template = CYCLE_TEMPLATES.get(cycle.length_weeks)
        if template is not None and len(template) == len(cycle.weeks):
            for week, focus in zip(cycle.weeks, template):
                week.focus = focus
                week.planned_load_pct = LOAD_PCT_BY_FOCUS[focus]

    _align_realization_to_match(cycle)
    return chosen


# =============================================================
# 1. PERIODISERING: cyclus herberekenen bij afgelasting
# =============================================================

def handle_match_cancellation(
    cycle: TrainingCycle,
    cancelled_match_date: date,
    new_match_date: date,
    reason: str = "winterweer",
) -> TrainingCycle:
    """
    Schuift de cyclus op vanaf het afgelastingspunt en injecteert
    onderhoudsweken (RECOVERY) zodat er geen trainingsgat ontstaat.
    De laatste week wordt opnieuw uitgelijnd als REALIZATION-week op de
    nieuwe wedstrijddatum.
    """
    shift_weeks = _weeks_between(cancelled_match_date, new_match_date)
    if shift_weeks <= 0:
        raise ValueError("Nieuwe matchdatum moet na de afgelaste datum liggen.")

    cutover_index = _find_cutover_week(cycle, cancelled_match_date)

    maintenance_weeks = []
    for w in range(shift_weeks):
        maintenance_weeks.append(CycleWeek(
            week_number=0,
            week_start_date=cycle.weeks[cutover_index].week_start_date + timedelta(weeks=w),
            focus=WeekFocus.RECOVERY,
            planned_load_pct=LOAD_PCT_BY_FOCUS[WeekFocus.RECOVERY],
        ))

    remaining_original_weeks = cycle.weeks[cutover_index:]
    for w in remaining_original_weeks:
        w.week_start_date += timedelta(weeks=shift_weeks)

    new_weeks = cycle.weeks[:cutover_index] + maintenance_weeks + remaining_original_weeks
    for i, w in enumerate(new_weeks):
        w.week_number = i + 1

    cycle.weeks = new_weeks
    cycle.target_match_date = new_match_date
    cycle.shift_count += 1

    _align_realization_to_match(cycle)
    return cycle


def _weeks_between(d1: date, d2: date) -> int:
    return (d2 - d1).days // 7 + (1 if (d2 - d1).days % 7 else 0)


def _find_cutover_week(cycle: TrainingCycle, cancelled_date: date) -> int:
    for i, w in enumerate(cycle.weeks):
        if w.week_start_date >= cancelled_date:
            return i
    return len(cycle.weeks) - 1


def _align_realization_to_match(cycle: TrainingCycle) -> None:
    if cycle.target_match_date is None:
        return
    for w in cycle.weeks:
        week_end = w.week_start_date + timedelta(days=6)
        if w.week_start_date <= cycle.target_match_date <= week_end:
            w.focus = WeekFocus.REALIZATION
            w.planned_load_pct = LOAD_PCT_BY_FOCUS[WeekFocus.REALIZATION]
