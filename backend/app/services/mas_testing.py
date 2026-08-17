"""
mas_testing.py

MAS-testplanning (wanneer moet een speler opnieuw getest worden) en de
automatische afleiding van trainingszones uit een MAS-score.

Zuiver en side-effect-vrij: geen databasetoegang.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from app.services.periodization import Season, TrainingCycle, WeekFocus

MIN_INTERVAL_WEEKS = 4      # nooit vaker testen dan dit
MAX_INTERVAL_WEEKS = 6      # bovengrens: hoe lang een MAS-score "geldig" blijft


@dataclass
class TestPlanningResult:
    player_name: str
    last_test_date: Optional[date]
    weeks_since_last_test: Optional[float]
    next_required_test_date: date
    reason: str
    status: str  # 'ok' | 'due_soon' | 'overdue'


def plan_next_mas_test(
    player_name: str,
    last_test_date: Optional[date],
    cycle: TrainingCycle,
    today: date,
    due_soon_window_days: int = 7,
) -> TestPlanningResult:
    if last_test_date is None:
        return TestPlanningResult(
            player_name=player_name, last_test_date=None, weeks_since_last_test=None,
            next_required_test_date=today,
            reason="Geen eerdere MAS-test gevonden — baseline-test vereist.",
            status="overdue",
        )

    weeks_since = (today - last_test_date).days / 7

    upcoming_key_week = next(
        (w for w in cycle.weeks
         if w.week_start_date >= today
         and w.focus in (WeekFocus.INTENSIFICATION, WeekFocus.REALIZATION)),
        None,
    )

    candidate_dates, reasons = [], []

    if upcoming_key_week is not None:
        weeks_gap = (upcoming_key_week.week_start_date - last_test_date).days / 7
        if weeks_gap >= MIN_INTERVAL_WEEKS:
            candidate_dates.append(upcoming_key_week.week_start_date - timedelta(days=3))
            reasons.append(f"Test vereist vóór {upcoming_key_week.focus.value}-week "
                            f"(start {upcoming_key_week.week_start_date}).")

    max_interval_deadline = last_test_date + timedelta(weeks=MAX_INTERVAL_WEEKS)
    candidate_dates.append(max_interval_deadline)
    reasons.append(f"Testscore mag niet ouder worden dan {MAX_INTERVAL_WEEKS} weken.")

    next_required_test_date = min(candidate_dates)
    binding_reason = reasons[candidate_dates.index(next_required_test_date)]

    days_until_due = (next_required_test_date - today).days
    status = "overdue" if days_until_due < 0 else (
        "due_soon" if days_until_due <= due_soon_window_days else "ok")

    return TestPlanningResult(
        player_name=player_name, last_test_date=last_test_date,
        weeks_since_last_test=round(weeks_since, 1),
        next_required_test_date=next_required_test_date,
        reason=binding_reason, status=status,
    )


@dataclass
class MASTestCalendarEvent:
    """Eén te plannen teamtestmoment, voor de kalender."""
    event_date: date
    player_names: list
    label: str


def _next_required_test_date_in_season(last_test_date: date, season: Season, from_date: date):
    """
    Zelfde regel als plan_next_mas_test(), maar zoekt over ALLE cyclussen
    van het seizoen heen in plaats van binnen één cyclus — nodig om
    testmomenten te kunnen projecteren tot het einde van het seizoen,
    ook als die in een cyclus liggen die nu nog niet actief/klaargezet is.
    """
    all_weeks = [w for cycle in season.cycles for w in cycle.weeks]
    upcoming_key_week = next(
        (w for w in all_weeks if w.week_start_date >= from_date
         and w.focus in (WeekFocus.INTENSIFICATION, WeekFocus.REALIZATION)),
        None,
    )
    candidates, reasons = [], []
    if upcoming_key_week is not None:
        gap_weeks = (upcoming_key_week.week_start_date - last_test_date).days / 7
        if gap_weeks >= MIN_INTERVAL_WEEKS:
            candidates.append(upcoming_key_week.week_start_date - timedelta(days=3))
            reasons.append(f"Vóór {upcoming_key_week.focus.value}-week ({upcoming_key_week.week_start_date}).")
    max_deadline = last_test_date + timedelta(weeks=MAX_INTERVAL_WEEKS)
    candidates.append(max_deadline)
    reasons.append(f"Testscore verloopt na {MAX_INTERVAL_WEEKS} weken.")
    next_date = min(candidates)
    return next_date, reasons[candidates.index(next_date)]


def project_season_mas_test_events(
    season: Season,
    players_last_test: dict,      # {player_name: last_test_date | None}
    today: date,
    group_window_days: int = 3,
) -> list:
    """
    Projecteert ALLE vereiste MAS-testmomenten tot het einde van het
    seizoen — niet enkel de eerstvolgende. Dit is wat de kalender in één
    keer moet vullen met 'MAS-test'-items over alle resterende cyclussen,
    in plaats van dat er telkens pas ná een effectieve test een nieuw
    kalender-item verschijnt.

    Werkwijze per speler: vertrek van de laatst gekende testdatum, bepaal
    de volgende vereiste datum (_next_required_test_date_in_season), ga
    ervan uit dat de coach die haalt, en herhaal tot het einde van het
    seizoen. Dit is een PROJECTIE — als een test effectief later gebeurt
    dan gepland, moet deze functie opnieuw aangeroepen worden om de
    resterende kalender-items bij te stellen (geen eenmalige, statische
    berekening).
    """
    if not season.cycles:
        return []
    season_end = season.cycles[-1].end_date()

    player_dates = {}
    for name, last_test_date in players_last_test.items():
        dates = []
        if last_test_date is None:
            # Nooit getest -> baseline-test is ONMIDDELLIJK vereist (zelfde regel
            # als plan_next_mas_test), dus het eerste projectiepunt is vandaag.
            dates.append(today)
            cursor_last_test = today
            search_from = today + timedelta(days=1)
        else:
            cursor_last_test = last_test_date
            search_from = today
        for _ in range(50):  # veiligheidslimiet tegen oneindige lus
            next_date, _reason = _next_required_test_date_in_season(cursor_last_test, season, search_from)
            if next_date > season_end:
                break
            dates.append(next_date)
            cursor_last_test = next_date          # aanname: coach test tijdig op deze datum
            search_from = next_date + timedelta(days=1)
        player_dates[name] = dates

    all_dates = sorted({d for dates in player_dates.values() for d in dates})
    events, used_dates = [], set()
    for d in all_dates:
        if d in used_dates:
            continue
        grouped_players = [name for name, dates in player_dates.items()
                            if any(0 <= (dd - d).days <= group_window_days for dd in dates)]
        events.append(MASTestCalendarEvent(
            event_date=d, player_names=grouped_players,
            label=f"MAS-test ({len(grouped_players)} speler(s))",
        ))
        used_dates.add(d)
    return events


@dataclass
class TrainingZone:
    name: str
    pct_mas_low: float
    pct_mas_high: float
    speed_low_kmh: float
    speed_high_kmh: float
    typical_use: str


ZONE_DEFINITIONS = [
    ("Actief herstel",   0.60, 0.70, "Lichte duurloop, dag na wedstrijd/zware sessie"),
    ("Aerobe duurloop",  0.70, 0.80, "Continue duurtraining, basis-uithouding"),
    ("Tempo / drempel",  0.80, 0.90, "Langere intervallen (3-8 min), aeroob-anaerobe grens"),
    ("VO2max-interval",  0.90, 1.05, "Korte-lange intervallen (2-4 min of 30s/30s)"),
    ("HIT (15s/15s)",    1.05, 1.20, "Kortdurende intermitterende blokken, matchspecifiek"),
]


def recalculate_training_zones(mas_kmh: float) -> list:
    """Wordt aangeroepen telkens een nieuwe mas_test wordt ingevoerd."""
    if mas_kmh <= 0:
        raise ValueError("MAS-score moet groter zijn dan 0.")
    return [
        TrainingZone(name=name, pct_mas_low=low, pct_mas_high=high,
                     speed_low_kmh=round(mas_kmh * low, 2),
                     speed_high_kmh=round(mas_kmh * high, 2),
                     typical_use=use)
        for name, low, high, use in ZONE_DEFINITIONS
    ]


# --- LOOPTYPEGROEPEN: spelers indelen op MAS voor groepsgebaseerde intervaldoelen ---
# I.p.v. voor elke speler apart een intervalschema op te stellen, worden
# spelers op basis van hun MAS-score in enkele groepen ingedeeld, elk met
# hetzelfde intervaldoel binnen de groep. Praktisch onmisbaar zonder eigen
# fysieke trainer, en overzichtelijker voor de coach op het veld.
DEFAULT_RUN_GROUP_LABELS = {
    2: ["De Motoren", "De Diesels"],
    3: ["De Motoren", "De Hybrides", "De Diesels"],
    4: ["De Motoren", "De Sportwagens", "De Hybrides", "De Diesels"],
}
MIN_SPREAD_FOR_GROUPING_KMH = 1.0   # onder dit verschil (snelste-traagste): geen opdeling zinvol
GAP_SIGNIFICANCE_FACTOR = 1.5       # een kloof moet minstens 1,5x de gemiddelde afstand zijn
                                     # om als 'echte' groepsgrens te tellen, niet toeval


@dataclass
class RunningGroup:
    label: str
    players: list                # list[str] spelersnamen
    prescriptie_mas_kmh: float   # VEILIGHEIDSANKER: laagste MAS in de groep, niet het gemiddelde
    avg_mas_kmh: float
    min_mas_kmh: float
    max_mas_kmh: float


def assign_running_groups(players_mas: list, num_groups: int = 3,
                           group_labels: Optional[list] = None) -> dict:
    """
    Verdeelt spelers in looptypegroepen op basis van NATUURLIJKE CLUSTERS
    in hun MAS-scores — niet op een vast aantal spelers per groep. Zoekt
    de grootste kloven (verschillen) in de gesorteerde MAS-reeks en knipt
    daar, in plaats van de kern gewoon in even grote stukken te delen.

    WAAROM: bij een kern die dicht bij elkaar zit (vaak het geval — een
    kern is zelden willekeurig verspreid over de hele MAS-schaal) kan een
    vaste-groepsgrootte-verdeling twee spelers met bijna identieke MAS in
    verschillende groepen duwen, puur omdat ze net aan weerszijden van de
    rangschikkingsgrens vallen. Kloofgebaseerd groeperen voorkomt dat.

    Praktisch gevolg: de groepen zijn NIET noodzakelijk even groot — dat
    is net de bedoeling, het weerspiegelt de werkelijke spreiding in de
    kern in plaats van een opgelegde verdeling.

    Geeft een dict terug met 'groups' (list[RunningGroup]) en 'note'
    (str, gevuld als de kern te weinig spreiding heeft voor het gevraagde
    aantal groepen — dan wordt automatisch met minder groepen gewerkt).

    players_mas: [{'player_name': str, 'mas_kmh': float}, ...]
    """
    if num_groups < 2:
        raise ValueError("Minstens 2 groepen nodig.")
    if len(players_mas) < num_groups:
        raise ValueError(f"Te weinig spelers ({len(players_mas)}) voor {num_groups} groepen.")

    sorted_players = sorted(players_mas, key=lambda p: p["mas_kmh"], reverse=True)
    values = [p["mas_kmh"] for p in sorted_players]

    # Is de volledige spreiding van de kern te klein om zinvol op te delen?
    total_spread = values[0] - values[-1]
    if total_spread < MIN_SPREAD_FOR_GROUPING_KMH:
        note = (f"Spreiding in de kern is klein ({round(total_spread, 2)} km/u tussen snelste en "
                f"traagste) — de hele kern traint samen op één prescriptie-MAS in plaats van "
                f"kunstmatig op te delen.")
        mas_values = values
        group = RunningGroup(
            label=(group_labels[0] if group_labels else "Volledige kern"),
            players=[p["player_name"] for p in sorted_players],
            prescriptie_mas_kmh=round(min(mas_values), 2),
            avg_mas_kmh=round(sum(mas_values) / len(mas_values), 2),
            min_mas_kmh=round(min(mas_values), 2), max_mas_kmh=round(max(mas_values), 2),
        )
        return {"groups": [group], "note": note}

    # Bereken alle opeenvolgende kloven (dalend gesorteerd, dus altijd >= 0)
    gaps = [(values[i] - values[i + 1], i) for i in range(len(values) - 1)]
    # Een kloof telt enkel als 'echt' als hij duidelijk groter is dan de
    # GEMIDDELDE afstand tussen spelers in deze kern — anders kiest het
    # algoritme gewoon de grootste van een reeks bijna-gelijke kloofjes,
    # wat een scheve, kunstmatige indeling zou geven bij een kern die
    # eigenlijk vrij homogeen is.
    avg_gap = total_spread / (len(values) - 1)
    meaningful_gaps = [g for g in gaps if g[0] > GAP_SIGNIFICANCE_FACTOR * avg_gap]

    note = ""
    effective_num_groups = num_groups
    if len(meaningful_gaps) < num_groups - 1:
        effective_num_groups = len(meaningful_gaps) + 1
        note = (f"De kern heeft weinig spreiding in MAS — automatisch teruggeschaald van "
                f"{num_groups} naar {effective_num_groups} groep(en), want er zijn niet genoeg "
                f"natuurlijke kloven om {num_groups} zinvol te onderscheiden groepen te vormen.")

    # Kies de (effective_num_groups - 1) grootste kloven als knippunten
    split_indices = sorted(
        idx for _, idx in sorted(meaningful_gaps, key=lambda g: g[0], reverse=True)[:effective_num_groups - 1]
    )

    labels = group_labels or DEFAULT_RUN_GROUP_LABELS.get(
        effective_num_groups, [f"Groep {i + 1}" for i in range(effective_num_groups)]
    )
    if len(labels) != effective_num_groups:
        labels = [f"Groep {i + 1}" for i in range(effective_num_groups)]

    groups = []
    start = 0
    for i, split_idx in enumerate(split_indices + [len(sorted_players) - 1]):
        chunk = sorted_players[start:split_idx + 1]
        mas_values = [p["mas_kmh"] for p in chunk]
        groups.append(RunningGroup(
            label=labels[i], players=[p["player_name"] for p in chunk],
            prescriptie_mas_kmh=round(min(mas_values), 2),
            avg_mas_kmh=round(sum(mas_values) / len(mas_values), 2),
            min_mas_kmh=round(min(mas_values), 2), max_mas_kmh=round(max(mas_values), 2),
        ))
        start = split_idx + 1

    return {"groups": groups, "note": note}


# --- 2.5 MAS-TESTPROTOCOLLEN: bibliotheek waaruit de trainer kiest --------
# Vier veldtesten die voor amateurvoetbal haalbaar zijn, elk met eigen
# afweging tussen nauwkeurigheid, benodigdheden en voetbalspecificiteit
# (richtingsveranderingen). 'result_label' beschrijft wat de trainer exact
# invoert; 'correction_factor' vertaalt dat resultaat naar een MAS-score
# (1.0 = resultaat IS de MAS, geen omrekening nodig).

@dataclass
class MASTestProtocol:
    key: str
    name: str
    description: str
    equipment: list           # benodigdheden
    how_to_administer: str
    result_label: str         # wat de trainer invoert
    correction_factor: float  # vermenigvuldigingsfactor naar MAS


MAS_TEST_PROTOCOLS = {
    "vameval": MASTestProtocol(
        key="vameval",
        name="VAMEVAL",
        description=(
            "Continue, geleidelijk oplopende looptest op een rond parcours (bv. 400m-piste). "
            "Geldt als een van de meest betrouwbare en eenvoudig te organiseren MAS-testen, "
            "en is geschikt om een hele groep tegelijk te testen omdat iedereen zichtbaar blijft."
        ),
        equipment=["Piste of vlak parcours (veelvoud van 20m, bv. 400m)", "Pionnen om de 20m",
                   "Audiosignaal/app met het officiële VAMEVAL-protocol (geen willekeurige "
                   "internet-soundtrack — die komen vaak niet meer overeen met het huidige protocol)"],
        how_to_administer=(
            "Spelers lopen van pion naar pion (elke 20m) en moeten elke pion bereiken op het "
            "moment van het geluidssignaal. Gestart wordt aan ±8 km/u, de snelheid stijgt elke "
            "minuut met 0.5 km/u. De test stopt voor een speler zodra hij 2 keer een pion niet "
            "op tijd bereikt. De MAS is de snelheid van het laatst volledig afgewerkte niveau."
        ),
        result_label="Laatst volledig afgewerkte snelheid (km/u)",
        correction_factor=1.0,
    ),
    "30-15-ift": MASTestProtocol(
        key="30-15-ift",
        name="30-15 Intermittent Fitness Test (30-15 IFT)",
        description=(
            "Intermitterende shuttle-test (30s lopen, 15s pauze) over een 40m-parcours, met "
            "richtingsveranderingen — daardoor het meest voetbalspecifiek van de vier testen, "
            "omdat het niet enkel de aerobe capaciteit maar ook het herstel tussen inspanningen "
            "en de wendbaarheid mee test."
        ),
        equipment=["40m rechte lijn (vrij, bv. een deel van het veld of een zaal)",
                   "Pionnen op 0m, 20m en 40m", "Audiosignaal/app met het 30-15 IFT-protocol"],
        how_to_administer=(
            "Spelers lopen heen en terug over de 40m in blokken van 30s inspanning gevolgd door "
            "15s passief herstel, telkens gestuurd door het geluidssignaal. Start aan 8 km/u, "
            "+0.5 km/u per blok van 30s. De test stopt bij vrijwillige uitputting of wanneer een "
            "speler 2 keer na elkaar de lijn niet op tijd bereikt. Het resultaat is VIFT (snelheid "
            "van het laatst volledig afgewerkte blok) — dit is NIET rechtstreeks de MAS: door het "
            "intermitterende karakter ligt VIFT hoger dan de werkelijke MAS. Het platform herleidt "
            "dit automatisch naar een geschatte MAS."
        ),
        result_label="VIFT — laatst volledig afgewerkte snelheid (km/u)",
        correction_factor=0.87,  # Buchheit & Laursen (2013): 85-90% van VIFT als MAS-schatting
    ),
    "umtt": MASTestProtocol(
        key="umtt",
        name="Université de Montréal Track Test (Léger-Boucher)",
        description=(
            "Continue looptest op de piste, gelijkaardig aan VAMEVAL maar met iets grotere "
            "snelheidsstappen — een goed alternatief als er geen VAMEVAL-audiobestand "
            "beschikbaar is, met vergelijkbare benodigdheden."
        ),
        equipment=["Piste of vlak parcours (veelvoud van 50m aanbevolen)", "Pionnen om de 50m",
                   "Audiosignaal/app met het UMTT-protocol"],
        how_to_administer=(
            "Zelfde opzet als VAMEVAL: spelers lopen continu rond het parcours en moeten elke "
            "pion op het geluidssignaal bereiken, met een geleidelijk oplopende snelheid per "
            "minuut. De MAS is de snelheid van het laatst volledig afgewerkte niveau."
        ),
        result_label="Laatst volledig afgewerkte snelheid (km/u)",
        correction_factor=1.0,
    ),
    "shuttle-20m": MASTestProtocol(
        key="shuttle-20m",
        name="20m Shuttle Run (Léger-test / 'beeptest')",
        description=(
            "De bekendste en meest toegankelijke test — vraagt het minste aan materiaal en "
            "ruimte, maar is fysiek belastender voor de benen door de vele keerbewegingen op "
            "20m, en licht minder nauwkeurig dan VAMEVAL door de grotere snelheidssprongen."
        ),
        equipment=["20m vrije ruimte (bv. een zaal of deel van het veld)", "Pionnen op beide uiteinden",
                   "Audiosignaal/app met het Léger 20m-shuttlerunprotocol"],
        how_to_administer=(
            "Spelers lopen heen en terug over 20m, telkens op het geluidssignaal. De snelheid "
            "stijgt per niveau (ongeveer elke minuut). De test stopt wanneer een speler 2 keer "
            "na elkaar de lijn niet op tijd bereikt. De MAS is de snelheid van het laatst "
            "volledig afgewerkte niveau."
        ),
        result_label="Laatst volledig afgewerkte snelheid (km/u)",
        correction_factor=1.0,
    ),
}


@dataclass
class MASTestRecord:
    player_name: str
    protocol_key: str
    protocol_name: str
    test_date: date
    raw_result_kmh: float
    mas_kmh: float


def record_mas_test(player_name: str, protocol_key: str, raw_result_kmh: float, test_date: date) -> MASTestRecord:
    """
    Verwerkt een ingegeven testresultaat naar een MAS-score, met de juiste
    correctiefactor voor het gekozen protocol. Dit is wat er gebeurt zodra
    de trainer een resultaat ingeeft/uploadt — ook voor de allereerste
    (baseline) test van een speler.
    """
    if protocol_key not in MAS_TEST_PROTOCOLS:
        raise ValueError(f"Onbekend testprotocol: {protocol_key}")
    if raw_result_kmh <= 0:
        raise ValueError("Testresultaat moet groter zijn dan 0.")

    protocol = MAS_TEST_PROTOCOLS[protocol_key]
    mas_kmh = round(raw_result_kmh * protocol.correction_factor, 2)

    return MASTestRecord(
        player_name=player_name, protocol_key=protocol_key, protocol_name=protocol.name,
        test_date=test_date, raw_result_kmh=raw_result_kmh, mas_kmh=mas_kmh,
    )


def record_mas_test_batch(results: list, protocol_key: str, test_date: date) -> dict:
    """
    Verwerkt de resultaten van de VOLLEDIGE kern in één aanroep — dit is wat
    de 'Opslaan voor volledige groep'-knop op het batch-invulscherm (stap B,
    na de protocolkeuze in stap A) aanroept, in plaats van een aparte
    opslagactie per speler.

    results: [{'player_name': str, 'raw_result_kmh': float}, ...] — één
    protocol en testdatum geldt voor de hele batch (het hele team neemt op
    hetzelfde moment dezelfde test af).

    Spelers met een ongeldig resultaat (niet ingevuld, <= 0) worden
    overgeslagen in plaats van de hele batch te laten falen — de lijst
    overgeslagen namen komt terug mee zodat de coach ziet wie nog ontbreekt.
    """
    if protocol_key not in MAS_TEST_PROTOCOLS:
        raise ValueError(f"Onbekend testprotocol: {protocol_key}")

    records, skipped = [], []
    for entry in results:
        raw = entry.get("raw_result_kmh")
        if raw is None or raw <= 0:
            skipped.append(entry.get("player_name", "onbekend"))
            continue
        records.append(record_mas_test(entry["player_name"], protocol_key, raw, test_date))

    return {"records": records, "skipped_players": skipped}
