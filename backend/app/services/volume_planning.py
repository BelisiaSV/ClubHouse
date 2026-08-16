"""
volume_planning.py

Wekelijkse kilometerplanning per cyclusfase: verdeelt het cyclus-piekvolume
over de weken (via planned_load_pct), trekt het wedstrijdaandeel eraf, en
verdeelt de rest over de geplande trainingen.

Zuiver en side-effect-vrij: geen databasetoegang.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.services.makeup_programs import REFERENCE_MATCH_MINUTES
from app.services.periodization import TrainingCycle, WeekFocus


class PlayerPosition(str, Enum):
    GK = "GK"
    CB = "CB"
    FB = "FB"
    DM = "DM"
    CM = "CM"
    AM = "AM"
    WNG = "WNG"
    ST = "ST"


@dataclass
class WeeklyKmPlan:
    week_number: int
    focus: WeekFocus
    weekly_target_km: float
    match_distance_km: float
    training_distance_km: float
    km_per_training: float
    note: str


DEFAULT_AVG_MATCH_DISTANCE_KM = 10.5   # instelbaar per club/niveau


def generate_cycle_km_plan(
    cycle: TrainingCycle,
    avg_match_distance_km: float = DEFAULT_AVG_MATCH_DISTANCE_KM,
    min_recovery_km_per_training: float = 3.0,
) -> list:
    """Trainings-km en wedstrijd-km worden VOLLEDIG ONTKOPPELD berekend, in
    plaats van wedstrijd-km af te trekken van een krimpend weektotaal (dat
    liet het trainingsvolume in een deloadweek-met-wedstrijd bijna tot 0 km
    inzakken — de wedstrijd-km bleef onveranderd terwijl het weektotaal met
    load_pct kromp, dus at de wedstrijd een steeds groter aandeel van een
    steeds kleiner totaal op). Een wedstrijd 'deload' je niet: je speelt hem
    nog steeds volledig, ongeacht de trainingsfase.

    Rekenwijze:
    1. Een trainings-piekvolume wordt EENMALIG afgeleid uit
       cycle.target_peak_weekly_km (dat de coach instelt als 'totaal in de
       piekweek, uitgaand van 1 wedstrijd die week') door er één gemiddelde
       wedstrijdafstand van af te trekken.
    2. Dat trainings-piekvolume wordt PER WEEK geschaald met
       week.planned_load_pct — dit bepaalt de trainings-km, volledig los
       van of er die week een wedstrijd is.
    3. De wedstrijd-km wordt apart en ONGEWIJZIGD opgeteld, o.b.v. het
       WERKELIJKE aantal wedstrijden die week (week.num_matches) — nooit
       afgeleid van of afgetrokken van het trainingsdeel.
    4. weekly_target_km = training_distance_km + match_distance_km (een SOM,
       geen aftrekking meer)."""
    training_peak_km = max(0.0, cycle.target_peak_weekly_km - avg_match_distance_km)

    plans = []
    for week in cycle.weeks:
        training_distance_km = round(training_peak_km * (week.planned_load_pct / 100), 2)
        match_distance_km = round(week.num_matches * avg_match_distance_km, 2)
        weekly_target_km = round(training_distance_km + match_distance_km, 2)

        note = ""
        if week.num_trainings > 0:
            km_per_training = round(training_distance_km / week.num_trainings, 2)
            if 0 < km_per_training < min_recovery_km_per_training:
                km_per_training = min_recovery_km_per_training
                note = f"Opgetrokken naar het minimum van {min_recovery_km_per_training} km."
        else:
            km_per_training = 0.0
            note = "Geen trainingen gepland deze week."

        plans.append(WeeklyKmPlan(
            week_number=week.week_number, focus=week.focus, weekly_target_km=weekly_target_km,
            match_distance_km=match_distance_km, training_distance_km=training_distance_km,
            km_per_training=km_per_training,
            note=note or (f"{week.num_matches} wedstrijd(en) + {week.num_trainings} training(en) "
                           f"-> {km_per_training} km/training."),
        ))
    return plans


# --- Kilometerdoel per positie -----------------------------------------
# GPS-onderzoek in het voetbal toont consistent dat buitenspelers en
# centrale middenvelders doorgaans meer afstand afleggen dan centrale
# verdedigers of doelmannen. km_per_training uit het weekplan is een
# TEAMGEMIDDELDE; deze gewichten herverdelen dat gemiddelde realistischer
# per positie. Instelbaar per club — de standaardwaarden zijn een
# redelijk uitgangspunt, geen exacte wet.
DEFAULT_POSITION_KM_WEIGHTS = {
    PlayerPosition.GK: 0.55,
    PlayerPosition.CB: 0.85,
    PlayerPosition.FB: 1.05,
    PlayerPosition.DM: 0.95,
    PlayerPosition.CM: 1.15,
    PlayerPosition.AM: 1.05,
    PlayerPosition.WNG: 1.15,
    PlayerPosition.ST: 1.00,
}


def calculate_km_target_per_position(km_per_training: float, position_weights: Optional[dict] = None) -> dict:
    """Herverdeelt het teamgemiddelde km_per_training (uit WeeklyKmPlan) naar
    een doel per positie. position_weights laat de club de standaard-
    gewichten overschrijven."""
    weights = position_weights or DEFAULT_POSITION_KM_WEIGHTS
    return {pos: round(km_per_training * weight, 2) for pos, weight in weights.items()}


# --- Werkelijke wedstrijdafstand per speler, op basis van positie + minuten ---
# Bron: CIES Football Observatory (gepoolde data, 7.855 wedstrijden) — gebruikt
# als instelbaar UITGANGSPUNT. Amateurwedstrijden liggen doorgaans lager in
# absolute afstand, maar de verhouding tussen posities is doorgaans vergelijkbaar.
# Vervangt NIET de teamplanning (generate_cycle_km_plan blijft de vooraf
# geschatte weekbelasting bepalen) — dit berekent de WERKELIJKE, achteraf
# vastgestelde bijdrage van een speler zodra zijn speelminuten gekend zijn.
POSITION_REFERENCE_MATCH_DISTANCE_KM = {
    PlayerPosition.GK: 5.0,
    PlayerPosition.CB: 9.6,
    PlayerPosition.FB: 10.5,
    PlayerPosition.DM: 10.3,
    PlayerPosition.CM: 11.0,
    PlayerPosition.AM: 10.8,
    PlayerPosition.WNG: 10.9,
    PlayerPosition.ST: 10.1,
}


def calculate_player_match_distance(
    position: "PlayerPosition",
    minutes_played: int,
    reference_distances: Optional[dict] = None,
) -> float:
    """
    Schat de werkelijk afgelegde afstand van een speler in een wedstrijd,
    op basis van zijn positie en gespeelde minuten. Vereenvoudigde
    lineaire schaling t.o.v. de volledige-matchreferentie voor die positie
    (bv. een aanvallende middenvelder op 90' -> 10.8 km; op 75' -> 9.0 km).

    Kanttekening: dit is een lineaire benadering. In de praktijk lopen
    invallers soms relatief méér per minuut (frisse benen, vaak op het
    scherpst van de snede ingebracht), maar zonder eigen GPS-data is
    lineaire schaling het meest verdedigbare, transparante uitgangspunt.
    """
    if minutes_played <= 0:
        return 0.0
    refs = reference_distances or POSITION_REFERENCE_MATCH_DISTANCE_KM
    if position not in refs:
        raise ValueError(f"Geen referentieafstand gekend voor positie: {position}")
    full_match_distance = refs[position]
    return round(full_match_distance * (minutes_played / REFERENCE_MATCH_MINUTES), 2)


@dataclass
class PlayerWeeklyDistanceLog:
    player_name: str
    week_number: int
    match_distance_km: float          # automatisch berekend en ingevuld
    training_distance_km: float = 0.0  # opgeteld uit effectief afgewerkte trainingen

    @property
    def total_km(self) -> float:
        return round(self.match_distance_km + self.training_distance_km, 2)


def populate_match_distance_for_week(match_appearances: list, week_number: int) -> list:
    """
    Vult AUTOMATISCH de wedstrijdkilometers in voor elke speler die
    speelde, zodra zijn minuten gekend zijn (na het invullen van de
    match_minutes bij een afgeronde wedstrijd). Dit voedt de kilometers
    van die speler voor de cyclusweek waarin de wedstrijd plaatsvond —
    geen handmatige invoer nodig.

    match_appearances: lijst van dicts
      {'player_name': str, 'position': PlayerPosition, 'minutes_played': int}
    """
    logs = []
    for entry in match_appearances:
        if entry["minutes_played"] <= 0:
            continue  # niet gespeeld -> geen wedstrijdafstand, wel eventueel compensatie (zie sectie 3)
        distance = calculate_player_match_distance(entry["position"], entry["minutes_played"])
        logs.append(PlayerWeeklyDistanceLog(
            player_name=entry["player_name"], week_number=week_number,
            match_distance_km=distance,
        ))
    return logs


# --- Week-km-overzicht per positie, per cyclusweek ------------------------
# Voegt de kilometerplanning (generate_cycle_km_plan) en de positie-
# gewichten hierboven samen tot ÉÉN overzicht: per week van de cyclus, per
# positie, hoeveel km via training en hoeveel via de wedstrijd verwacht
# wordt — samen gelijk aan het weektotaal van die fase.
#
# BELANGRIJK: de wedstrijd-km hier is de DEFAULT/verwachte waarde bij een
# volledige wedstrijd (90'), gebruikt voor VOORAF plannen. Zodra de
# werkelijke speelminuten gekend zijn, gebruik dan
# calculate_player_match_distance() voor de WERKELIJKE afstand per speler
# — dat kan afwijken van deze defaultwaarde.

@dataclass
class PositionWeeklyKm:
    position: PlayerPosition
    training_km: float      # totaal via training deze week (alle trainingen samen)
    match_km: float          # verwachte wedstrijd-km (default: volledige wedstrijd, 90')
    total_km: float


@dataclass
class WeeklyKmOverview:
    week_number: int
    focus: WeekFocus
    team_weekly_target_km: float     # team-niveau totaal uit generate_cycle_km_plan()
    team_training_km: float
    team_match_km: float
    by_position: list                # list[PositionWeeklyKm]


def generate_weekly_km_overview_by_position(
    cycle: TrainingCycle,
    avg_match_distance_km: float = DEFAULT_AVG_MATCH_DISTANCE_KM,
    training_position_weights: Optional[dict] = None,
    match_position_refs: Optional[dict] = None,
) -> list:
    """Genereert voor ELKE week van de cyclus een volledig km-overzicht per
    positie: trainings-km + wedstrijd-km apart weergegeven, samen gelijk
    aan (of zeer dicht bij) het teamtotaal van die week."""
    training_weights = training_position_weights or DEFAULT_POSITION_KM_WEIGHTS
    match_refs = match_position_refs or POSITION_REFERENCE_MATCH_DISTANCE_KM

    km_plans = generate_cycle_km_plan(cycle, avg_match_distance_km=avg_match_distance_km)

    overviews = []
    for week, plan in zip(cycle.weeks, km_plans):
        weekly_training_total = plan.km_per_training * week.num_trainings

        by_position = []
        for position in PlayerPosition:
            position_training_km = round(
                (training_weights.get(position, 1.0)) * plan.km_per_training * week.num_trainings, 2
            )
            position_match_km = round(match_refs.get(position, avg_match_distance_km) * week.num_matches, 2)
            by_position.append(PositionWeeklyKm(
                position=position, training_km=position_training_km,
                match_km=position_match_km, total_km=round(position_training_km + position_match_km, 2),
            ))

        overviews.append(WeeklyKmOverview(
            week_number=week.week_number, focus=week.focus,
            team_weekly_target_km=plan.weekly_target_km,
            team_training_km=round(weekly_training_total, 2),
            team_match_km=plan.match_distance_km,
            by_position=by_position,
        ))
    return overviews
