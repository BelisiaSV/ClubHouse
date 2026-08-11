"""
session_composition.py

Oefenvormen — "AI physical coach" voor de trainingsinhoud. Vertaalt het
abstracte duur/afstandsdoel uit team_readiness.propose_next_training() naar
concrete, herkenbare oefenvormen — bedoeld voor clubs zonder eigen fysieke
trainer. Twee gebruiksmodi:
  (a) propose_session_composition(): volledige sessieopbouw met meerdere
      vormen, als leidraad voor de coach.
  (b) calculate_vorm_target(): de coach kiest zelf één vorm uit het
      keuzemenu, het systeem rekent automatisch duur/afstand door.

ONTWERPPRINCIPE: het KM-DOEL is leidend, niet de sessieduur. Een fysieke
trainer redeneert "hoeveel tijd heb ik nodig aan deze vorm om het doel te
bereiken", niet "hoe vul ik de volledige sessieduur met vormen" — dat
laatste leidt bij hoge-intensiteitsvormen al snel tot een grove
overschrijding. propose_session_composition() schaalt daarom de bloktijden
actief bij tot de som zo dicht mogelijk bij het km-doel ligt.

BLOKSTRUCTUUR PARTIJVORMEN: small/medium/large-sided games en
transitievormen worden NOOIT als één ononderbroken blok voorgesteld.
Herhaalde bouts van 2-4 minuten met 1-2 minuten rust ertussen is de
gangbare, blessurebeperkende opbouw uit onderzoek naar kleine-veldspelen
(bv. Aguiar et al., Hill-Haas et al.) — één lang blok stapelt vermoeidheid
op zonder herstelvenster en verhoogt zo het risico.

BELANGRIJKE KANTTEKENING: de afstand-per-minuut-waarden per vorm zijn
schattingen op basis van gangbare bevindingen over kleine-veldspelen en
oefenvormen in het voetbal — pitchgrootte, spelregels en coachstijl geven
grote spreiding in de praktijk. Dit is een instelbaar planningsvertrekpunt,
geen exacte meting.

Zuiver en side-effect-vrij: geen databasetoegang.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

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
    typical_duration_min: tuple        # (min, max) gangbare TOTALE werktijd (excl. rust)
    player_count_sensitive: bool       # schaalt de belasting mee met het aantal spelers?
    bout_duration_min: Optional[float]  # None = continu blok, anders herhaalde bouts
    rest_between_bouts_min: Optional[float]
    notes: str


# Relatieve veldoppervlakte per speler (RPA, m²) per subformaat — bevestigd
# tegen meerdere GPS-studies (o.a. PLOS One 2020 area-per-player-onderzoek;
# 6v6 op 125-150 m²/speler geeft aantoonbaar de hoogste HR-respons/TRIMP;
# LSG >200 m²/speler nodig voor betekenisvolle HSR/sprintafstand). Grenzen
# tussen categorieën zijn in de literatuur niet universeel vastgelegd —
# dit is een instelbaar werkkader, geen exacte norm.
FIELD_DIMENSION_GUIDE = {
    "3v3":   {"pitch_m": "20x25 - 22x25", "rpa_m2": "83-92"},
    "4v4":   {"pitch_m": "25x30", "rpa_m2": "94"},
    "5v5":   {"pitch_m": "30x35", "rpa_m2": "105"},
    "6v6":   {"pitch_m": "40x45", "rpa_m2": "150"},
    "7v7":   {"pitch_m": "45x50", "rpa_m2": "161"},
    "8v8":   {"pitch_m": "50x65", "rpa_m2": "203"},
    "9v9":   {"pitch_m": "60x75", "rpa_m2": "225"},
    "10v10": {"pitch_m": "60x75 - strafschopgebied tot strafschopgebied", "rpa_m2": "225-250"},
    "11v11": {"pitch_m": "105x68 (officieel veld)", "rpa_m2": "325"},
}


OEFENVORM_LIBRARY = {
    OefenvormType.PAS_EN_TRAP: OefenvormProfile(
        label="Pass-en-trapvorm", distance_per_min_low_m=70, distance_per_min_high_m=95,
        intensity_pct_mas_low=0.50, intensity_pct_mas_high=0.65, typical_duration_min=(8, 15),
        player_count_sensitive=False, bout_duration_min=None, rest_between_bouts_min=None,
        notes="Lage belasting, geschikt als opwarming of technisch/rustig sluitstuk. Continu blok.",
    ),
    OefenvormType.BALBEZIT: OefenvormProfile(
        label="Balbezitvorm (positiespel/rondo)", distance_per_min_low_m=90, distance_per_min_high_m=115,
        intensity_pct_mas_low=0.65, intensity_pct_mas_high=0.80, typical_duration_min=(10, 15),
        player_count_sensitive=False, bout_duration_min=None, rest_between_bouts_min=None,
        notes="Gematigde continue belasting, veel richtingsveranderingen op korte afstand.",
    ),
    OefenvormType.TRANSITIE: OefenvormProfile(
        label="Transitievorm (omschakeling)", distance_per_min_low_m=125, distance_per_min_high_m=155,
        intensity_pct_mas_low=0.85, intensity_pct_mas_high=1.00, typical_duration_min=(6, 20),
        player_count_sensitive=True, bout_duration_min=3.0, rest_between_bouts_min=2.0,
        notes="Hoge intensiteit door snelle omschakelmomenten — bouts van 3' met 2' rust, "
              "i.p.v. één lang blok, om acute vermoeidheidsopstapeling te vermijden.",
    ),
    OefenvormType.SSG: OefenvormProfile(
        label="Small-sided game (3v3-5v5)", distance_per_min_low_m=95, distance_per_min_high_m=125,
        intensity_pct_mas_low=0.80, intensity_pct_mas_high=1.05, typical_duration_min=(6, 24),
        player_count_sensitive=True, bout_duration_min=3.0, rest_between_bouts_min=2.0,
        notes="RPA ca. 83-105 m²/speler — neuromusculaire nadruk (versnellen/remmen/duels), "
              "weinig ruimte voor lange sprints. Bouts van 3' met 2' rust (volledig herstel "
              "vereist voor herhaalde explosiviteit).",
    ),
    OefenvormType.MSG: OefenvormProfile(
        label="Medium-sided game (6v6-7v7)", distance_per_min_low_m=125, distance_per_min_high_m=150,
        intensity_pct_mas_low=0.85, intensity_pct_mas_high=0.95, typical_duration_min=(8, 24),
        player_count_sensitive=True, bout_duration_min=5.5, rest_between_bouts_min=2.5,
        notes="RPA ca. 150-161 m²/speler — bevestigd in onderzoek als de zone met de hoogste "
              "HR-respons/TRIMP (6v6 op 125-150 m²/speler). Bouts van 5,5' met 2,5' rust.",
    ),
    OefenvormType.LSG: OefenvormProfile(
        label="Large-sided game (8v8+)", distance_per_min_low_m=140, distance_per_min_high_m=165,
        intensity_pct_mas_low=0.90, intensity_pct_mas_high=1.10, typical_duration_min=(10, 25),
        player_count_sensitive=True, bout_duration_min=9.0, rest_between_bouts_min=3.5,
        notes="RPA >200 m²/speler — nodig om betekenisvolle HSR-/sprintafstand te bereiken "
              "(topsnelheid >25 km/u mogelijk). Bouts van 9' met 3,5' rust: de langere rust is "
              "nodig om de hartslag te laten zakken vóór herhaalde sprints (blessurepreventie).",
    ),
    OefenvormType.AFWERKING: OefenvormProfile(
        label="Afwerkvorm", distance_per_min_low_m=55, distance_per_min_high_m=85,
        intensity_pct_mas_low=0.40, intensity_pct_mas_high=0.60, typical_duration_min=(8, 15),
        player_count_sensitive=False, bout_duration_min=None, rest_between_bouts_min=None,
        notes="Lage continue afstand door wachttijd in de rij, met korte explosieve pieken "
              "(sprint/afwerking) die niet in het %MAS-gemiddelde tot uiting komen.",
    ),
    OefenvormType.PATROON: OefenvormProfile(
        label="Patroonvorm", distance_per_min_low_m=75, distance_per_min_high_m=100,
        intensity_pct_mas_low=0.55, intensity_pct_mas_high=0.70, typical_duration_min=(8, 15),
        player_count_sensitive=False, bout_duration_min=None, rest_between_bouts_min=None,
        notes="Vooral tactisch/technisch gericht, gematigde fysieke belasting. Continu blok.",
    ),
}

# Sessietemplates per cyclusfase: welke vormen, in welke volgorde, en hun
# RELATIEVE aandeel — wordt gebruikt als startpunt vóór de km-gestuurde
# herschaling, niet als vaste eindwaarde.
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


FORMAT_MAX_PLAYERS_PER_SIDE = {
    OefenvormType.SSG: 5,           # 3v3-5v5
    OefenvormType.MSG: 7,           # 6v6-7v7
    OefenvormType.LSG: None,        # 8v8+, geen bovengrens per definitie
    OefenvormType.TRANSITIE: 6,     # praktisch vergelijkbaar met SSG/MSG-achtige groepsgrootte
}


def _field_dimension_hint(vorm: OefenvormType, per_side: int) -> str:
    """Toont enkel wat de coach nodig heeft: veldmaat + aantal veldspelers.
    Geen RPA/m²-jargon — te technisch voor de doelgroep, ook al stuurt
    RPA de berekening intern wél mee (zie FIELD_DIMENSION_GUIDE)."""
    key = f"{per_side}v{per_side}"
    guide = FIELD_DIMENSION_GUIDE.get(key)
    if not guide:
        return ""
    return f", veld {guide['pitch_m']}m, {per_side} veldspelers per team"


def _suggested_format_label(vorm: OefenvormType, num_players: int) -> str:
    """Houdt rekening met de MAXIMALE teamgrootte per vormtype (bv. SSG
    blijft max. 5v5, ook bij een grote groep), stelt rotatie voor wanneer
    er meer spelers zijn dan één veld aankan, en voegt een veldmaathint toe
    (zie FIELD_DIMENSION_GUIDE)."""
    profile = OEFENVORM_LIBRARY[vorm]
    if not profile.player_count_sensitive:
        return ""
    natural_per_side = max(2, num_players // 2)
    cap = FORMAT_MAX_PLAYERS_PER_SIDE.get(vorm)
    if cap is not None and natural_per_side > cap:
        per_side = cap
        rotation_note = f", rouleer groepen — {num_players} spelers beschikbaar"
    else:
        per_side = natural_per_side
        rotation_note = ""
    return f" ({per_side}v{per_side}{rotation_note}{_field_dimension_hint(vorm, per_side)})"


@dataclass
class VormTarget:
    vorm: OefenvormType
    label: str
    duration_min: float              # totale WERKTIJD (excl. rust)
    distance_km: float
    intensity_pct_mas_low: float
    intensity_pct_mas_high: float
    num_bouts: Optional[int]
    bout_duration_min: Optional[float]
    rest_between_bouts_min: Optional[float]
    total_clock_time_min: float      # werktijd + rust — wat effectief op het veld nodig is
    format_hint: str
    notes: str


def calculate_vorm_target(vorm: OefenvormType, duration_min: float, num_players: int) -> VormTarget:
    """
    Gebruikt voor CONTINUE vormen (pass-en-trap, balbezit, patroon,
    afwerking) waar de coach de werktijd rechtstreeks instelt, én intern
    door propose_session_composition() om vanuit een gewenste werktijd een
    startvoorstel te bouwen.

    Voor PARTIJVORMEN (SSG/MSG/LSG/transitie) is dit NIET de functie die de
    coach-UI voor handmatige aanpassing mag aanroepen — gebruik daar
    calculate_vorm_target_by_reps(), zodat de bloktijd zelf (wetenschappelijk
    vastgelegd, bv. 3' voor SSG) nooit door vrije invoer kan verschuiven.
    Deze functie rondt een gewenste werktijd wel af naar een heel aantal
    bouts van de vaste lengte, maar mag niet gebruikt worden om zelf een
    afwijkende bloktijd te forceren (bv. '5 min werk verdeeld over 3 bouts'
    zou een bloktijd van 1,7' opleveren — dat is exact wat vermeden moet
    worden).

    'duration_min' is de GEWENSTE totale werktijd; wordt begrensd tot de
    typical_duration_min-bandbreedte van de vorm (veiligheidsplafond).
    """
    if vorm not in OEFENVORM_LIBRARY:
        raise ValueError(f"Onbekende oefenvorm: {vorm}")
    if duration_min <= 0:
        raise ValueError("Duur moet groter zijn dan 0.")
    if num_players <= 0:
        raise ValueError("Aantal spelers moet groter zijn dan 0.")

    profile = OEFENVORM_LIBRARY[vorm]
    duration_min, clamp_note = _clamp_to_typical_duration(vorm, duration_min)
    dist_per_min = _distance_per_min_for_vorm(vorm, num_players)

    if profile.bout_duration_min is not None:
        num_bouts = max(1, round(duration_min / profile.bout_duration_min))
        actual_work_duration = num_bouts * profile.bout_duration_min
        rest_time = (num_bouts - 1) * profile.rest_between_bouts_min
        total_clock_time = actual_work_duration + rest_time
    else:
        num_bouts = None
        actual_work_duration = duration_min
        total_clock_time = duration_min

    distance_km = round(dist_per_min * actual_work_duration / 1000, 2)

    return VormTarget(
        vorm=vorm, label=profile.label, duration_min=round(actual_work_duration, 1),
        distance_km=distance_km,
        intensity_pct_mas_low=profile.intensity_pct_mas_low,
        intensity_pct_mas_high=profile.intensity_pct_mas_high,
        num_bouts=num_bouts, bout_duration_min=profile.bout_duration_min,
        rest_between_bouts_min=profile.rest_between_bouts_min,
        total_clock_time_min=round(total_clock_time, 1),
        format_hint=_suggested_format_label(vorm, num_players),
        notes=profile.notes + (f" {clamp_note}" if clamp_note else ""),
    )


def calculate_vorm_target_by_reps(vorm: OefenvormType, num_bouts: int, num_players: int) -> VormTarget:
    """
    DE functie die de coach-UI moet aanroepen wanneer hij een partijvorm
    (SSG/MSG/LSG/transitie) handmatig aanpast. De coach kiest enkel het
    AANTAL herhalingen — de bloktijd zelf (bv. 3' voor SSG) staat vast en is
    nooit instelbaar, exact om de fout uit de vorige versie te voorkomen
    (een bloktijd die verschuift naargelang wat de coach in twee losse
    velden intikt).

    num_bouts wordt begrensd tot een veilig maximum, afgeleid van de
    typical_duration_min-bovengrens van de vorm gedeeld door de bloktijd.
    """
    if vorm not in OEFENVORM_LIBRARY:
        raise ValueError(f"Onbekende oefenvorm: {vorm}")
    profile = OEFENVORM_LIBRARY[vorm]
    if profile.bout_duration_min is None:
        raise ValueError(
            f"{profile.label} is een continue vorm zonder bout-structuur — "
            f"gebruik calculate_vorm_target() met een werktijd i.p.v. een aantal bouts."
        )
    if num_bouts <= 0:
        raise ValueError("Aantal bouts moet groter zijn dan 0.")
    if num_players <= 0:
        raise ValueError("Aantal spelers moet groter zijn dan 0.")

    max_bouts = max(1, int(profile.typical_duration_min[1] // profile.bout_duration_min))
    clamp_note = ""
    if num_bouts > max_bouts:
        clamp_note = (f" Aantal bouts begrensd van {num_bouts} naar {max_bouts} "
                       f"(veiligheidsplafond voor deze vorm: max. {profile.typical_duration_min[1]}' werktijd).")
        num_bouts = max_bouts

    requested_duration = num_bouts * profile.bout_duration_min
    result = calculate_vorm_target(vorm, requested_duration, num_players)
    if clamp_note:
        result.notes += clamp_note
    return result


def _clamp_to_typical_duration(vorm: OefenvormType, duration_min: float):
    """Begrenst een gevraagde werktijd tot de typical_duration_min-bandbreedte
    van de vorm — een zacht veiligheidsplafond tegen onrealistische invoer
    (bv. 40' ononderbroken small-sided games)."""
    profile = OEFENVORM_LIBRARY[vorm]
    low, high = profile.typical_duration_min
    if duration_min > high:
        return high, f"(Werktijd begrensd tot het veilige maximum van {high}' voor deze vorm.)"
    return duration_min, ""


@dataclass
class SessionCompositionProposal:
    week_focus: WeekFocus
    num_players: int
    target_duration_min: float
    target_distance_km: float
    blocks: list                 # list[VormTarget], in volgorde
    total_work_duration_min: float
    total_clock_time_min: float
    total_distance_km: float
    deviation_note: str
    optional_dry_run_topup: Optional["DryRunTopUp"] = None


def propose_session_composition(
    week_focus: WeekFocus,
    num_players: int,
    target_duration_min: float,
    target_distance_km: float,
    team_avg_mas_kmh: Optional[float] = None,
    player_flags: Optional[list] = None,
) -> SessionCompositionProposal:
    """
    Stelt een volledige sessieopbouw voor die zo dicht mogelijk bij het
    KM-DOEL uitkomt — dat is de leidende grootheid, niet de sessieduur.
    Dit is een VOORSTEL: de coach kan elk blok zelf aanpassen. Gebruik
    daarna summarize_composition() om de aangepaste blokken opnieuw te
    laten optellen tegen hetzelfde doel (incl. overload-bewustzijn).

    Werkwijze:
    1. Bouw een baseline-verdeling via de sessietemplate van de cyclusfase
       (proportioneel qua werktijd).
    2. Bereken de totale afstand van die baseline.
    3. Herschaal ALLE bloktijden met dezelfde factor (target/baseline) zodat
       de som zo dicht mogelijk bij het km-doel uitkomt.
    4. Herbereken elk blok met de herschaalde tijd — partijvormen ronden
       daarbij af naar een heel aantal bouts (zie calculate_vorm_target).
    5. Als er, ondanks de herschaling, nog een merkbaar tekort overblijft
       (bv. door afronding naar volledige bouts), wordt een OPTIONELE
       droge loopvorm voorgesteld om dat laatste stuk in te vullen —
       zie propose_optional_dry_running_topup().

    total_clock_time_min kan hoger liggen dan target_duration_min zodra
    rustperiodes tussen bouts meegerekend worden — dat is verwacht en
    correct, geen foutmelding.
    """
    if week_focus not in SESSION_TEMPLATES:
        raise ValueError(f"Geen sessietemplate voor cyclusfase: {week_focus}")
    if num_players <= 0:
        raise ValueError("Aantal spelers moet groter zijn dan 0.")
    if target_distance_km <= 0:
        raise ValueError("Km-doel moet groter zijn dan 0.")

    template = SESSION_TEMPLATES[week_focus]

    # Stap 1-2: baseline
    baseline_blocks = []
    for vorm, fraction in template:
        block_duration = target_duration_min * fraction
        if block_duration <= 0:
            continue
        baseline_blocks.append((vorm, block_duration))
    baseline_distance = sum(
        calculate_vorm_target(vorm, dur, num_players).distance_km for vorm, dur in baseline_blocks
    )

    # Stap 3: herschaalfactor — begrensd om degenererende gevallen te vermijden
    scale = target_distance_km / baseline_distance if baseline_distance > 0 else 1.0
    scale = max(0.3, min(scale, 2.5))

    # Stap 4: herbereken elk blok met de herschaalde tijd
    blocks = [calculate_vorm_target(vorm, dur * scale, num_players) for vorm, dur in baseline_blocks]

    summary = summarize_composition(blocks, target_distance_km, player_flags=player_flags)

    # Stap 5: optionele droge loopvorm bij een resterend tekort
    optional_topup = None
    remaining_km = round(target_distance_km - summary["total_distance_km"], 2)
    if remaining_km > 0.15 and team_avg_mas_kmh:   # kleine tekorten (<150m) zijn niet de moeite
        optional_topup = propose_optional_dry_running_topup(remaining_km, team_avg_mas_kmh)

    return SessionCompositionProposal(
        week_focus=week_focus, num_players=num_players,
        target_duration_min=target_duration_min, target_distance_km=target_distance_km,
        blocks=blocks, total_work_duration_min=summary["total_work_duration_min"],
        total_clock_time_min=summary["total_clock_time_min"],
        total_distance_km=summary["total_distance_km"],
        deviation_note=summary["deviation_note"],
        optional_dry_run_topup=optional_topup,
    )


def summarize_composition(blocks: list, target_distance_km: float, player_flags: Optional[list] = None) -> dict:
    """
    Telt een blokkenlijst (origineel voorstel, OF de door de coach zelf
    aangepaste versie) opnieuw op tegen het km-doel. Dit is de functie die
    de frontend na elke handmatige aanpassing opnieuw aanroept, zodat de
    coach altijd het actuele totaal en de afwijking t.o.v. het weekdoel
    ziet — inclusief een expliciete waarschuwing als er al overbelaste of
    onvoldoende herstelde spelers gemeld zijn EN het voorstel duidelijk
    boven het doel uitkomt (samen een reëel overbelastingsrisico).
    """
    total_work_duration = round(sum(b.duration_min for b in blocks), 1)
    total_clock_time = round(sum(b.total_clock_time_min for b in blocks), 1)
    total_distance = round(sum(b.distance_km for b in blocks), 2)

    deviation_pct = round((total_distance - target_distance_km) / target_distance_km * 100, 1) \
        if target_distance_km > 0 else 0.0

    at_risk_players = [f for f in (player_flags or []) if f.flag_type in ("overload", "poor_recovery")]

    if abs(deviation_pct) <= 8:
        note = f"Voorstel ligt dicht bij het km-doel ({total_distance} km t.o.v. doel {target_distance_km} km)."
    elif deviation_pct > 8:
        note = (f"Voorstel ligt {deviation_pct}% boven het km-doel ({total_distance} vs. {target_distance_km} km).")
        if at_risk_players:
            names = ", ".join(dict.fromkeys(f.player_name for f in at_risk_players))  # dedupe, behoud volgorde
            note += (f" Let op: {names} zit(ten) al in overbelasting/onvoldoende herstel — extra "
                     f"volume boven het doel is voor hen af te raden, overweeg voor hen een lichtere rol.")
        else:
            note += " Kort desgewenst één blok met één bout in om dichter bij het doel te komen."
    else:
        note = (f"Voorstel ligt {abs(deviation_pct)}% onder het km-doel ({total_distance} vs. {target_distance_km} km) "
                f"— voeg desgewenst een blok toe, of gebruik de optionele droge loopvorm.")

    return {
        "total_work_duration_min": total_work_duration,
        "total_clock_time_min": total_clock_time,
        "total_distance_km": total_distance,
        "deviation_pct": deviation_pct,
        "deviation_note": note,
    }


# --- Optionele droge loopvorm (geen bal) om een resterend km-tekort te dichten ---
# Hergebruikt bewust dezelfde intensiteit/blok/rust-zones als de bestaande
# wedstrijd-compensatiemodule (sectie 3) — dezelfde onderbouwing (Buchheit &
# Laursen HIIT-zones) geldt hier. Aanvullend bevestigd door onderzoek naar
# repeated-sprint training: maximale sprints ≤10s met hersteltijd ≤60s,
# met arbeid:rust-verhoudingen van 1:1 (kwaliteit behouden onder vermoeidheid)
# tot 1:6 (maximale hersteltijd per herhaling) — de hier gebruikte zones
# vallen binnen die gangbare bandbreedte.
DRY_RUN_ZONES = [
    # (max_resterende_km, intensity_pct, work_s, rest_s, label)
    (0.5, 1.10, 15, 15, "Korte prikkels op topsnelheid"),
    (1.2, 1.00, 30, 30, "Middellange herhalingen"),
    (2.5, 0.88, 120, 60, "Tempo-herhalingen"),
    (999, 0.75, 240, 90, "Duurloop in blokken"),
]


@dataclass
class DryRunTopUp:
    label: str
    reps: int
    distance_per_rep_m: int
    time_per_rep_s: float
    rest_s: float
    intensity_pct_mas: float
    total_distance_m: float
    instruction: str


def propose_optional_dry_running_topup(remaining_distance_km: float, team_avg_mas_kmh: float) -> DryRunTopUp:
    """
    Optionele, aanklikbare loopvorm (geen bal) om een resterend km-tekort
    op te vullen na de sessieopbouw. Kiest intensiteit en herhalingsafstand
    op basis van hoeveel er nog nodig is (kleiner tekort -> korter/sneller,
    groter tekort -> langer/rustiger), volgens dezelfde zones als de
    wedstrijd-compensatiemodule. team_avg_mas_kmh is best een voorzichtige
    schatting (bv. gemiddelde of net onder het teamgemiddelde), zodat de
    minst getrainde speler niet overvraagd wordt — de coach kan dit per
    speler/groep bijsturen.
    """
    if remaining_distance_km <= 0:
        raise ValueError("Er is geen resterende afstand om aan te vullen.")
    if team_avg_mas_kmh <= 0:
        raise ValueError("MAS-score moet groter zijn dan 0.")

    zone = next(z for z in DRY_RUN_ZONES if remaining_distance_km <= z[0])
    _, intensity_pct, work_s, rest_s, label = zone

    target_speed_kmh = round(team_avg_mas_kmh * intensity_pct, 2)
    target_speed_ms = target_speed_kmh / 3.6

    raw_distance_per_rep = target_speed_ms * work_s
    distance_per_rep = max(5, round(raw_distance_per_rep / 5) * 5)   # afgerond op 5m, praktisch haalbaar
    actual_time_per_rep_s = round(distance_per_rep / target_speed_ms, 1)

    reps = max(1, round((remaining_distance_km * 1000) / distance_per_rep))
    total_distance_m = reps * distance_per_rep

    instruction = (f"{reps}x {distance_per_rep}m in {actual_time_per_rep_s}s, {rest_s}s rust "
                    f"({int(intensity_pct*100)}% MAS, {target_speed_kmh} km/u)")

    return DryRunTopUp(
        label=label, reps=reps, distance_per_rep_m=distance_per_rep,
        time_per_rep_s=actual_time_per_rep_s, rest_s=rest_s, intensity_pct_mas=intensity_pct,
        total_distance_m=total_distance_m, instruction=instruction,
    )
