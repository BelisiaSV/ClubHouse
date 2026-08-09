"""
makeup_programs.py

Inhaalprogramma's: gemiste wedstrijdminuten ÉN gemiste trainingen, samengevoegd
in één homogeen datamodel (GeneratedRunningProgram) — dit is wat de
'Maak schema's'-knop als spelerskaart + detailpagina toont.

Zuiver en side-effect-vrij: geen databasetoegang.
"""

from dataclasses import dataclass
from math import ceil

from app.services.periodization import CycleWeek, WeekFocus

REFERENCE_MATCH_MINUTES = 90.0
MINUTES_THRESHOLD_FOR_MATCH_MAKEUP = 60   # club-instelbaar

# Intensiteitsprofiel per gemiste-trainingsweek-focus (individuele inhaalsessie)
MISSED_TRAINING_PROFILES = {
    WeekFocus.ACCUMULATION:    {"session_type": "Continue aerobe duurloop",
                                 "intensity_pct": 0.75, "base_duration_min": 35},
    WeekFocus.INTENSIFICATION: {"session_type": "VO2max-intervallen (30s/30s)",
                                 "intensity_pct": 1.00, "base_duration_min": 24,
                                 "work_s": 30, "rest_s": 30},
    WeekFocus.REALIZATION:     {"session_type": "HIT 15s/15s (matchspecifiek)",
                                 "intensity_pct": 1.10, "base_duration_min": 18,
                                 "work_s": 15, "rest_s": 15},
    WeekFocus.DELOAD:          {"session_type": "Actief herstel",
                                 "intensity_pct": 0.65, "base_duration_min": 20},
    WeekFocus.RECOVERY:        {"session_type": "Actief herstel",
                                 "intensity_pct": 0.60, "base_duration_min": 20},
}


@dataclass
class GeneratedRunningProgram:
    """Eén homogeen resultaat, ongeacht of de trigger een wedstrijd of een
    gemiste training was — dit is exact wat de 'Maak schema's'-knop als
    spelerskaart + detailpagina toont."""
    player_name: str
    reason: str                 # 'match_minutes' | 'training_absence'
    trigger_detail: str         # bv. "32' gespeeld vs Merksem" / "Afwezig op training 12/01"
    week_focus: WeekFocus
    mas_kmh: float
    session_type: str
    intensity_pct_mas: float
    target_speed_kmh: float
    structure_description: str
    total_duration_min: float
    total_distance_m: float


def qualifies_for_match_makeup(minutes_played: int,
                                threshold: int = MINUTES_THRESHOLD_FOR_MATCH_MAKEUP) -> bool:
    return 0 <= minutes_played < threshold


def _compensation_factor(minutes_played: float) -> float:
    """Niet-lineair: hoe minder gespeeld, hoe hoger de relatieve compensatie."""
    if minutes_played >= 60:
        return 0.25
    elif minutes_played >= 45:
        return 0.35
    elif minutes_played >= 20:
        return 0.45
    else:
        return 0.55


# Protocol-zones voor wedstrijdcompensatie, gekoppeld volgens de gangbare
# omgekeerde relatie tussen blokduur en intensiteit (hoe hoger %MAS, hoe
# korter het blok moet zijn om vol te houden — en omgekeerd). Elke zone
# vanaf 90 s werkt met ingebouwde versnellingen/richtingsveranderingen
# voor voetbalspecificiteit, in plaats van rechtlijnig lopen.
#
# Bronnen (o.a.): Buchheit & Laursen (2013) HIIT-programmeerprincipes;
# gangbare MAS-trainingszones (bv. 8x30s @100-110% MAS; 5-8x3min @95% MAS;
# 4-6x3-4min @90-95% MAS) — kortere blokken bij hogere %MAS, langere
# blokken met COD-elementen bij lagere %MAS.
MATCH_COMPENSATION_PROTOCOL_ZONES = [
    # (max_volume_min, intensity_pct, work_s, rest_s, label, football_specific)
    (6,  1.10, 15,  15,  "HIT 15s/15s (rechtlijnig, matchspecifieke topsnelheid)", False),
    (12, 1.00, 30,  30,  "Intervallen 30s/30s (rechtlijnig, met korte richtingsverandering halverwege)", True),
    (20, 0.88, 120, 60,  "Shuttle-tempoblokken 2' aan/1' uit, met ingebouwde versnellingen", True),
    (999, 0.75, 240, 90, "Duurloop met blokken van 4', ingebouwde versnellingen en richtingsveranderingen", True),
]


def _select_match_compensation_protocol(total_volume_min: float) -> dict:
    """
    Kiest intensiteit + blokduur op basis van hoeveel volumetijd nodig is:
    veel volume -> lagere intensiteit + langere, minder talrijke blokken
    (fysiologisch haalbaar, en ruimte voor voetbalspecifieke elementen);
    weinig volume -> hogere intensiteit + korte scherpe blokken.
    """
    for max_volume, intensity_pct, work_s, rest_s, label, football_specific in MATCH_COMPENSATION_PROTOCOL_ZONES:
        if total_volume_min <= max_volume:
            return {"intensity_pct": intensity_pct, "work_s": work_s, "rest_s": rest_s,
                    "label": label, "football_specific": football_specific}
    zone = MATCH_COMPENSATION_PROTOCOL_ZONES[-1]
    return {"intensity_pct": zone[1], "work_s": zone[2], "rest_s": zone[3],
            "label": zone[4], "football_specific": zone[5]}


def generate_program_for_missed_minutes(
    player_name: str,
    mas_kmh: float,
    minutes_played: int,
    week_focus: WeekFocus,
    opponent_label: str = "",
) -> GeneratedRunningProgram:
    """
    Trigger 1: speler speelde te weinig wedstrijdminuten.

    In plaats van altijd hetzelfde 15s/15s-format op te leggen, wordt eerst
    het benodigde volume berekend (deficit x compensatiefactor), en pas
    dan het passende protocol gekozen: kort/scherp bij weinig volume,
    langer/voetbalspecifiek (versnellingen, richtingsveranderingen) bij
    meer volume — zodat je nooit meer bij tientallen korte herhalingen op
    een submaximale snelheid uitkomt.
    """
    if mas_kmh <= 0:
        raise ValueError("MAS-score moet groter zijn dan 0.")

    deficit_minutes = REFERENCE_MATCH_MINUTES - minutes_played
    factor = _compensation_factor(minutes_played)
    total_work_time_min = deficit_minutes * factor

    protocol = _select_match_compensation_protocol(total_work_time_min)
    intensity_pct, work_s, rest_s = protocol["intensity_pct"], protocol["work_s"], protocol["rest_s"]

    target_speed_kmh = round(mas_kmh * intensity_pct, 2)
    target_speed_ms = target_speed_kmh / 3.6

    total_reps = max(1, round((total_work_time_min * 60) / work_s))
    distance_per_rep = round(target_speed_ms * work_s, 1)
    total_distance = round(distance_per_rep * total_reps, 1)

    cod_note = ""
    if protocol["football_specific"]:
        cod_note = (" — elke herhaling: laatste 5-6s versnellen naar sprinttempo "
                     "en/of een richtingsverandering van 90-180°, mimicken van matchacties")

    structure = (f"{total_reps}x [{work_s}s @ {target_speed_kmh} km/u "
                 f"({int(intensity_pct*100)}% MAS) / {rest_s}s rust]{cod_note}")

    trigger_detail = f"{minutes_played}' gespeeld" + (f" vs {opponent_label}" if opponent_label else "")

    return GeneratedRunningProgram(
        player_name=player_name, reason="match_minutes", trigger_detail=trigger_detail,
        week_focus=week_focus, mas_kmh=mas_kmh,
        session_type=f"Wedstrijdcompensatie — {protocol['label']}",
        intensity_pct_mas=intensity_pct, target_speed_kmh=target_speed_kmh,
        structure_description=structure, total_duration_min=round(total_work_time_min, 1),
        total_distance_m=total_distance,
    )


def generate_program_for_missed_training(
    player_name: str,
    mas_kmh: float,
    week: CycleWeek,
    training_date_label: str = "",
) -> GeneratedRunningProgram:
    """Trigger 2: speler was afwezig op een training."""
    if mas_kmh <= 0:
        raise ValueError("MAS-score moet groter zijn dan 0.")

    profile = MISSED_TRAINING_PROFILES[week.focus]
    load_scale = week.planned_load_pct / 100.0

    intensity_pct = profile["intensity_pct"]
    target_speed_kmh = round(mas_kmh * intensity_pct, 2)
    target_speed_ms = target_speed_kmh / 3.6
    scaled_duration_min = round(profile["base_duration_min"] * load_scale, 1)

    if "work_s" in profile:
        work_s, rest_s = profile["work_s"], profile["rest_s"]
        total_reps = max(1, ceil((scaled_duration_min * 60) / work_s))
        distance_per_rep = round(target_speed_ms * work_s, 1)
        total_distance = round(distance_per_rep * total_reps, 1)
        structure = (f"{total_reps}x [{work_s}s @ {target_speed_kmh} km/u "
                     f"({int(intensity_pct*100)}% MAS) / {rest_s}s rust]")
    else:
        total_distance = round(target_speed_ms * scaled_duration_min * 60, 1)
        structure = (f"Continue loop van {scaled_duration_min} min "
                     f"@ {target_speed_kmh} km/u ({int(intensity_pct*100)}% MAS)")

    trigger_detail = "Afwezig op training" + (f" ({training_date_label})" if training_date_label else "")

    return GeneratedRunningProgram(
        player_name=player_name, reason="training_absence", trigger_detail=trigger_detail,
        week_focus=week.focus, mas_kmh=mas_kmh, session_type=profile["session_type"],
        intensity_pct_mas=intensity_pct, target_speed_kmh=target_speed_kmh,
        structure_description=structure, total_duration_min=scaled_duration_min,
        total_distance_m=total_distance,
    )


def generate_makeup_schedules(candidates: list, week: CycleWeek) -> list:
    """
    Implementatie van de 'Maak schema's'-knop: neemt een lijst kandidaten
    (elk een dict) en genereert voor elk de juiste programma-variant.

    Verwacht per kandidaat:
      {'player_name': str, 'mas_kmh': float, 'reason': 'match_minutes' | 'training_absence',
       'minutes_played': int (enkel bij 'match_minutes'),
       'opponent_label' / 'training_date_label': str (optioneel)}
    """
    programs = []
    for c in candidates:
        if c["reason"] == "match_minutes":
            if not qualifies_for_match_makeup(c["minutes_played"]):
                continue
            programs.append(generate_program_for_missed_minutes(
                player_name=c["player_name"], mas_kmh=c["mas_kmh"],
                minutes_played=c["minutes_played"], week_focus=week.focus,
                opponent_label=c.get("opponent_label", ""),
            ))
        elif c["reason"] == "training_absence":
            programs.append(generate_program_for_missed_training(
                player_name=c["player_name"], mas_kmh=c["mas_kmh"], week=week,
                training_date_label=c.get("training_date_label", ""),
            ))
        else:
            raise ValueError(f"Onbekende reason: {c['reason']}")
    return programs
