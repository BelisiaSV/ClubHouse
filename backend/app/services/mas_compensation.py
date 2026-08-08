"""
mas_compensation.py
Berekent een geindividualiseerde HIT-compensatiesessie (15s/15s methode)
voor wisselspelers op basis van hun individuele MAS-score en gespeelde minuten.

Ported verbatim (constants, factor table, formulas) from the architecture
document's `calculate_hit_compensation` reference implementation.
"""

from dataclasses import dataclass
from math import ceil

# ---------------------------------------------------------
# Configuratie / sportwetenschappelijke constanten
# ---------------------------------------------------------
REFERENCE_MATCH_MINUTES = 90.0  # volledige wedstrijd als referentie
WORK_DURATION_S = 15  # 15s werk
REST_DURATION_S = 15  # 15s passieve/actieve rust
REPS_PER_BLOCK = 12  # bv. 12 x 15s/15s per blok = 6 min blok
REST_BETWEEN_BLOCKS_MIN = 3.0


def _compensation_factor(minutes_played: float) -> float:
    """Niet-lineair: hoe minder gespeeld, hoe hoger de relatieve compensatie nodig."""
    if minutes_played >= 60:
        return 0.25  # kleine topping-up sessie
    elif minutes_played >= 45:
        return 0.35
    elif minutes_played >= 20:
        return 0.45
    else:
        return 0.55  # nauwelijks gespeeld -> bijna volledige compensatie


@dataclass
class HITPrescription:
    player_name: str
    mas_kmh: float
    minutes_played: float
    intensity_pct: float
    target_speed_kmh: float
    target_speed_ms: float
    total_work_time_min: float
    total_reps: int
    blocks: int
    reps_per_block: int
    distance_per_rep_m: float
    total_distance_m: float
    protocol_description: str


def calculate_hit_compensation(
    player_name: str,
    mas_kmh: float,
    minutes_played: float,
    intensity_pct: float = 1.10,  # 110% MAS, aanpasbaar per positie/leeftijd
    work_s: int = WORK_DURATION_S,
    rest_s: int = REST_DURATION_S,
    reps_per_block: int = REPS_PER_BLOCK,
) -> HITPrescription:
    """
    Bereken een 15s/15s HIT-compensatieprotocol voor een wisselspeler.

    Parameters
    ----------
    mas_kmh : Individuele Maximale Aerobe Snelheid in km/u (uit meest recente mas_test)
    minutes_played : Effectief gespeelde minuten in de wedstrijd
    intensity_pct : Doelintensiteit t.o.v. MAS (1.10 = 110%)
    """
    if mas_kmh <= 0:
        raise ValueError("MAS-score moet groter zijn dan 0.")
    if minutes_played < 0 or minutes_played > REFERENCE_MATCH_MINUTES:
        raise ValueError("Gespeelde minuten moeten tussen 0 en 90 liggen.")

    # 1. Minutentekort t.o.v. volledige wedstrijd
    deficit_minutes = REFERENCE_MATCH_MINUTES - minutes_played

    # 2. Compensatiefactor toepassen -> netto werktijd (aan hoge intensiteit) in minuten
    factor = _compensation_factor(minutes_played)
    total_work_time_min = deficit_minutes * factor

    # 3. Doelsnelheid in km/u en m/s
    target_speed_kmh = round(mas_kmh * intensity_pct, 2)
    target_speed_ms = round(target_speed_kmh / 3.6, 3)

    # 4. Vertaal werktijd naar aantal 15s-herhalingen
    total_work_seconds = total_work_time_min * 60
    total_reps = max(1, ceil(total_work_seconds / work_s))

    # 5. Groepeer in blokken van N herhalingen, met langere rust tussen blokken
    blocks = max(1, ceil(total_reps / reps_per_block))

    # 6. Afstand per herhaling en totaal (voor GPS/video-validatie)
    distance_per_rep_m = round(target_speed_ms * work_s, 1)
    total_distance_m = round(distance_per_rep_m * total_reps, 1)

    protocol_description = (
        f"{total_reps}x [{work_s}s @ {target_speed_kmh} km/u ({int(intensity_pct*100)}% MAS) "
        f"/ {rest_s}s passieve rust], verdeeld over {blocks} blok(ken) van max. "
        f"{reps_per_block} reps, met {REST_BETWEEN_BLOCKS_MIN} min rust tussen blokken."
    )

    return HITPrescription(
        player_name=player_name,
        mas_kmh=mas_kmh,
        minutes_played=minutes_played,
        intensity_pct=intensity_pct,
        target_speed_kmh=target_speed_kmh,
        target_speed_ms=target_speed_ms,
        total_work_time_min=round(total_work_time_min, 1),
        total_reps=total_reps,
        blocks=blocks,
        reps_per_block=reps_per_block,
        distance_per_rep_m=distance_per_rep_m,
        total_distance_m=total_distance_m,
        protocol_description=protocol_description,
    )
