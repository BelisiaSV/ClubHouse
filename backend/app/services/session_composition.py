"""
session_composition.py

Oefenvormen — "AI physical coach" voor de trainingsinhoud. Vertaalt het
abstracte duur/afstanddoel uit team_readiness.propose_next_training() naar
concrete, herkenbare oefenvormen — bedoeld voor clubs zonder eigen fysieke
trainer. Twee gebruiksmodi:
  (a) propose_session_composition(): volledige sessieopbouw met meerdere
      vormen, als leidraad voor de coach.
  (b) calculate_vorm_target(): de coach kiest zelf één vorm uit het
      keuzemenu, het systeem rekent automatisch duur/afstand door.

BELANGRIJKE KANTTEKENING: de afstand-per-minuut-waarden per vorm zijn
schattingen op basis van gangbare bevindingen over kleine-veldspelen en
oefenvormen in het voetbal — pitchgrootte, spelregels en coachstijl geven
grote spreiding in de praktijk. Dit is een instelbaar planningsvertrekpunt,
geen exacte meting.

Zuiver en side-effect-vrij: geen databasetoegang.
"""

from dataclasses import dataclass
from enum import Enum

from app.services.periodization import WeekFocus


class OefenvormType(str, Enum):
    PAS_EN_TRAP = "pas_en_trap"
    BALBEZIT = "balbezit"
    TRANSITIE = "transitie"
    SSG = "ssg"              # small-sided games, doorgaans t/m 5v5
    MSG = "msg"               # medium-sided games, doorgaans 6v6-8v8
    LSG = "lsg"                # large-sided games, doorgaans 9v9+
    AFWERKING = "afwerking"
    PATROON = "patroon"


@dataclass
class OefenvormProfile:
    label: str
    distance_per_min_low_m: float     # afstand per minuut (meter), ondergrens
    distance_per_min_high_m: float    # afstand per minuut (meter), bovengrens
    intensity_pct_mas_low: float
    intensity_pct_mas_high: float
    typical_duration_min: tuple       # (min, max) gangbare blokduur
    player_count_sensitive: bool      # schaalt de belasting mee met het aantal spelers?
    notes: str


OEFENVORM_LIBRARY = {
    OefenvormType.PAS_EN_TRAP: OefenvormProfile(
        label="Pass-en-trapvorm", distance_per_min_low_m=70, distance_per_min_high_m=95,
        intensity_pct_mas_low=0.50, intensity_pct_mas_high=0.65, typical_duration_min=(8, 15),
        player_count_sensitive=False,
        notes="Lage belasting, geschikt als opwarming of technisch/rustig sluitstuk.",
    ),
    OefenvormType.BALBEZIT: OefenvormProfile(
        label="Balbezitvorm (positiespel/rondo)", distance_per_min_low_m=90, distance_per_min_high_m=115,
        intensity_pct_mas_low=0.65, intensity_pct_mas_high=0.80, typical_duration_min=(10, 15),
        player_count_sensitive=False,
        notes="Gematigde continue belasting, veel richtingsveranderingen op korte afstand.",
    ),
    OefenvormType.TRANSITIE: OefenvormProfile(
        label="Transitievorm (omschakeling)", distance_per_min_low_m=125, distance_per_min_high_m=155,
        intensity_pct_mas_low=0.85, intensity_pct_mas_high=1.00, typical_duration_min=(6, 12),
        player_count_sensitive=True,
        notes="Hoge intensiteit door snelle omschakelmomenten — kort houden, hoge herstelnood.",
    ),
    OefenvormType.SSG: OefenvormProfile(
        label="Small-sided game (t/m 5v5)", distance_per_min_low_m=95, distance_per_min_high_m=125,
        intensity_pct_mas_low=0.80, intensity_pct_mas_high=1.05, typical_duration_min=(4, 8),
        player_count_sensitive=True,
        notes="Hoge relatieve intensiteit (veel acties/richtingsveranderingen) bij beperkte totale afstand.",
    ),
    OefenvormType.MSG: OefenvormProfile(
        label="Medium-sided game (6v6-8v8)", distance_per_min_low_m=125, distance_per_min_high_m=150,
        intensity_pct_mas_low=0.85, intensity_pct_mas_high=1.05, typical_duration_min=(6, 12),
        player_count_sensitive=True,
        notes="Benadert al dicht de fysieke eisen van een wedstrijd.",
    ),
    OefenvormType.LSG: OefenvormProfile(
        label="Large-sided game (9v9+)", distance_per_min_low_m=140, distance_per_min_high_m=165,
        intensity_pct_mas_low=0.90, intensity_pct_mas_high=1.10, typical_duration_min=(8, 15),
        player_count_sensitive=True,
        notes="Meest wedstrijdspecifiek qua fysieke belasting.",
    ),
    OefenvormType.AFWERKING: OefenvormProfile(
        label="Afwerkvorm", distance_per_min_low_m=55, distance_per_min_high_m=85,
        intensity_pct_mas_low=0.40, intensity_pct_mas_high=0.60, typical_duration_min=(8, 15),
        player_count_sensitive=False,
        notes="Lage continue afstand door wachttijd in de rij, maar met korte explosieve pieken "
              "(sprint/afwerking) die niet in het %MAS-gemiddelde tot uiting komen.",
    ),
    OefenvormType.PATROON: OefenvormProfile(
        label="Patroonvorm", distance_per_min_low_m=75, distance_per_min_high_m=100,
        intensity_pct_mas_low=0.55, intensity_pct_mas_high=0.70, typical_duration_min=(8, 15),
        player_count_sensitive=False,
        notes="Vooral tactisch/technisch gericht, gematigde fysieke belasting.",
    ),
}

# Sessietemplates per cyclusfase: welke vormen, in welke volgorde en met
# welk aandeel van de totale sessieduur. Bewust opgebouwd van laag naar
# hoog naar laag (opwarming -> opbouw -> piek -> afwerking/afsluiter).
SESSION_TEMPLATES = {
    WeekFocus.ACCUMULATION: [
        (OefenvormType.PAS_EN_TRAP, 0.15), (OefenvormType.BALBEZIT, 0.35),
        (OefenvormType.PATROON, 0.25), (OefenvormType.AFWERKING, 0.15),
        (OefenvormType.PAS_EN_TRAP, 0.10),
    ],
    WeekFocus.INTENSIFICATION: [
        (OefenvormType.PAS_EN_TRAP, 0.10), (OefenvormType.BALBEZIT, 0.20),
        (OefenvormType.TRANSITIE, 0.30), (OefenvormType.MSG, 0.25),
        (OefenvormType.AFWERKING, 0.15),
    ],
    WeekFocus.REALIZATION: [
        (OefenvormType.PAS_EN_TRAP, 0.10), (OefenvormType.TRANSITIE, 0.20),
        (OefenvormType.MSG, 0.30), (OefenvormType.LSG, 0.25),
        (OefenvormType.AFWERKING, 0.15),
    ],
    WeekFocus.DELOAD: [
        (OefenvormType.PAS_EN_TRAP, 0.20), (OefenvormType.BALBEZIT, 0.30),
        (OefenvormType.PATROON, 0.30), (OefenvormType.AFWERKING, 0.20),
    ],
    WeekFocus.RECOVERY: [
        (OefenvormType.PAS_EN_TRAP, 0.25), (OefenvormType.BALBEZIT, 0.30),
        (OefenvormType.PATROON, 0.30), (OefenvormType.AFWERKING, 0.15),
    ],
}

PLAYER_COUNT_SCALING_MIN = 4    # onder dit aantal: laagste kant van de bandbreedte
PLAYER_COUNT_SCALING_MAX = 16   # boven dit aantal: hoogste kant van de bandbreedte


def _distance_per_min_for_vorm(vorm: OefenvormType, num_players: int) -> float:
    profile = OEFENVORM_LIBRARY[vorm]
    if not profile.player_count_sensitive:
        return (profile.distance_per_min_low_m + profile.distance_per_min_high_m) / 2
    span = PLAYER_COUNT_SCALING_MAX - PLAYER_COUNT_SCALING_MIN
    frac = max(0.0, min(1.0, (num_players - PLAYER_COUNT_SCALING_MIN) / span))
    return profile.distance_per_min_low_m + frac * (profile.distance_per_min_high_m - profile.distance_per_min_low_m)


@dataclass
class VormTarget:
    vorm: OefenvormType
    label: str
    duration_min: float
    distance_km: float
    intensity_pct_mas_low: float
    intensity_pct_mas_high: float
    notes: str


def calculate_vorm_target(vorm: OefenvormType, duration_min: float, num_players: int) -> VormTarget:
    """
    De coach kiest zelf één vorm uit het keuzemenu; dit rekent automatisch
    de verwachte afstand door, geschaald naar het aantal spelers voor
    vormen waar dat relevant is (SSG/MSG/LSG/transitie).
    """
    if vorm not in OEFENVORM_LIBRARY:
        raise ValueError(f"Onbekende oefenvorm: {vorm}")
    if duration_min <= 0:
        raise ValueError("Duur moet groter zijn dan 0.")
    profile = OEFENVORM_LIBRARY[vorm]
    dist_per_min = _distance_per_min_for_vorm(vorm, num_players)
    distance_km = round(dist_per_min * duration_min / 1000, 2)
    return VormTarget(
        vorm=vorm, label=profile.label, duration_min=duration_min, distance_km=distance_km,
        intensity_pct_mas_low=profile.intensity_pct_mas_low,
        intensity_pct_mas_high=profile.intensity_pct_mas_high, notes=profile.notes,
    )


@dataclass
class SessionCompositionProposal:
    week_focus: WeekFocus
    num_players: int
    target_duration_min: float
    target_distance_km: float
    blocks: list                 # list[VormTarget], in volgorde
    total_duration_min: float
    total_distance_km: float
    deviation_note: str


def propose_session_composition(
    week_focus: WeekFocus,
    num_players: int,
    target_duration_min: float,
    target_distance_km: float,
) -> SessionCompositionProposal:
    """
    Stelt een volledige sessieopbouw voor (meerdere vormen na elkaar) die
    samen ongeveer het duur- en afstandsdoel van propose_next_training()
    invullen. Dit is een LEIDRAAD, geen vast recept — de coach vult zelf
    de exacte oefenstof in per blok.
    """
    if week_focus not in SESSION_TEMPLATES:
        raise ValueError(f"Geen sessietemplate voor cyclusfase: {week_focus}")
    if num_players <= 0:
        raise ValueError("Aantal spelers moet groter zijn dan 0.")

    template = SESSION_TEMPLATES[week_focus]
    blocks = []
    for vorm, fraction in template:
        block_duration = round(target_duration_min * fraction)
        if block_duration <= 0:
            continue
        blocks.append(calculate_vorm_target(vorm, block_duration, num_players))

    total_duration = sum(b.duration_min for b in blocks)
    total_distance = round(sum(b.distance_km for b in blocks), 2)

    if target_distance_km > 0:
        deviation_pct = round((total_distance - target_distance_km) / target_distance_km * 100, 1)
    else:
        deviation_pct = 0.0

    if abs(deviation_pct) <= 10:
        note = f"Voorstel ligt dicht bij het km-doel ({total_distance} km t.o.v. doel {target_distance_km} km)."
    elif deviation_pct > 10:
        note = (f"Voorstel ligt {deviation_pct}% BOVEN het km-doel ({total_distance} vs. {target_distance_km} km) "
                f"— overweeg een vorm in te korten of te vervangen door een minder intensieve variant.")
    else:
        note = (f"Voorstel ligt {abs(deviation_pct)}% ONDER het km-doel ({total_distance} vs. {target_distance_km} km) "
                f"— overweeg een blok te verlengen of een intensievere vorm (bv. MSG i.p.v. balbezit) toe te voegen.")

    return SessionCompositionProposal(
        week_focus=week_focus, num_players=num_players,
        target_duration_min=target_duration_min, target_distance_km=target_distance_km,
        blocks=blocks, total_duration_min=total_duration, total_distance_km=total_distance,
        deviation_note=note,
    )
