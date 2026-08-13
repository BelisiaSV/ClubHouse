"""
team_readiness.py

Teamreadiness (ACWR + wellness) en het daaruit afgeleide trainingsvoorstel
(duur + km, afgeschaald op basis van team-belasting/herstel).

Zuiver en side-effect-vrij: geen databasetoegang.
"""

from dataclasses import dataclass, field
from typing import Optional

from app.services.periodization import CycleWeek, WeekFocus


@dataclass
class PlayerReadiness:
    player_name: str
    acute_load_7d: float
    chronic_load_28d: float
    sleep_quality: int
    fatigue_level: int
    muscle_soreness: int
    stress_level: int
    mood: int
    injury_flag: bool = False
    # Laatste 3 (of meer) wekelijkse acute-load-metingen, oudste eerst,
    # MEEST RECENTE LAATST (dus [3 weken geleden, 2 weken geleden, deze
    # week]). Optioneel — als leeg, wordt enkel de momentopname gebruikt.
    weekly_acute_load_history: list = field(default_factory=list)


@dataclass
class PlayerFlag:
    player_name: str
    flag_type: str        # 'overload' | 'underload' | 'poor_recovery' | 'injured' | 'acwr_trending_up'
    detail: str
    recommendation: str


def _acwr(player: PlayerReadiness) -> Optional[float]:
    if player.chronic_load_28d <= 0:
        return None
    return round(player.acute_load_7d / player.chronic_load_28d, 2)


def _wellness_composite(player: PlayerReadiness) -> float:
    normalized = [player.sleep_quality, 6 - player.fatigue_level,
                  6 - player.muscle_soreness, 6 - player.stress_level, player.mood]
    return round(sum(normalized) / len(normalized), 2)


def _acwr_trending_up(weekly_acute_load_history: list, min_weeks: int = 3,
                       min_total_increase_pct: float = 0.15) -> bool:
    """
    Detecteert een GELEIDELIJK STIJGENDE belasting over opeenvolgende weken,
    ook al zit de ACWR nog onder de 1.5-alarmdrempel. Dit is vaak een
    vroeger signaal dan de drempeloverschrijding zelf — sportwetenschappelijk
    onderbouwd als 'ramping load' vóór blessurerisico. Vereist minstens
    'min_weeks' metingen, elk hoger dan de vorige, met een totale stijging
    van minstens 'min_total_increase_pct' over de hele periode.
    """
    if len(weekly_acute_load_history) < min_weeks:
        return False
    recent = weekly_acute_load_history[-min_weeks:]
    monotonic_increase = all(recent[i] < recent[i + 1] for i in range(len(recent) - 1))
    if not monotonic_increase or recent[0] <= 0:
        return False
    total_increase_pct = (recent[-1] - recent[0]) / recent[0]
    return total_increase_pct >= min_total_increase_pct


def _load_adjustment_factor(acwr: Optional[float], wellness: float, trending_up: bool = False) -> float:
    factor = 1.0
    if acwr is not None:
        if acwr > 1.5:
            factor = min(factor, 0.70)
        elif acwr > 1.3:
            factor = min(factor, 0.85)
        elif acwr < 0.8:
            factor = min(factor, 0.90)
    if wellness < 2.5:
        factor = min(factor, 0.70)
    elif wellness < 3.2:
        factor = min(factor, 0.85)
    if trending_up:
        # Milde extra correctie, ook als de absolute ACWR nog geen alarm geeft —
        # het is de RICHTING die hier het signaal is, niet de huidige waarde.
        factor = min(factor, 0.90)
    return factor


def flag_players(players: list) -> list:
    flags = []
    for p in players:
        if p.injury_flag:
            flags.append(PlayerFlag(p.player_name, "injured",
                                     "Actief blessure- of pijnsignaal.",
                                     "Uitsluiten van teamtraining, individueel/revalidatieprogramma."))
            continue
        acwr, wellness = _acwr(p), _wellness_composite(p)
        trending_up = _acwr_trending_up(p.weekly_acute_load_history)

        if acwr is not None and acwr > 1.5:
            flags.append(PlayerFlag(p.player_name, "overload",
                                     f"ACWR = {acwr} (>1.5, snelle belastingsopbouw).",
                                     "Volume individueel met ~25-30% reduceren."))
        elif acwr is not None and acwr < 0.8:
            flags.append(PlayerFlag(p.player_name, "underload",
                                     f"ACWR = {acwr} (<0.8, mogelijk detraining).",
                                     "Kan een extra individuele MAS-gebaseerde sessie aan."))
        elif trending_up:
            flags.append(PlayerFlag(
                p.player_name, "acwr_trending_up",
                f"Acute belasting stijgt {len(p.weekly_acute_load_history[-3:])} weken op rij "
                f"({p.weekly_acute_load_history[-3:]}), ACWR ({acwr}) zit nog onder de alarmdrempel.",
                "Vroeg signaal — monitor komende week extra, geen directe reductie nodig maar geen "
                "verdere opbouw forceren."
            ))

        if wellness < 2.5:
            flags.append(PlayerFlag(p.player_name, "poor_recovery",
                                     f"Wellness-score {wellness}/5.",
                                     "Monitoren, overweeg lichtere belasting of rustdag."))
    return flags


TEAM_SESSION_PROFILES = {
    WeekFocus.ACCUMULATION:    {"session_type": "Aerobe basis + tactische possessievorm",
                                 "intensity_low": 0.70, "intensity_high": 0.85, "base_duration_min": 90},
    WeekFocus.INTENSIFICATION: {"session_type": "Tempo/drempelblokken + duelvormen",
                                 "intensity_low": 0.85, "intensity_high": 1.00, "base_duration_min": 75},
    WeekFocus.REALIZATION:     {"session_type": "Matchsimulatie / HIT-afwerking",
                                 "intensity_low": 1.00, "intensity_high": 1.15, "base_duration_min": 60},
    WeekFocus.DELOAD:          {"session_type": "Techniek + actief herstel",
                                 "intensity_low": 0.55, "intensity_high": 0.70, "base_duration_min": 50},
    WeekFocus.RECOVERY:        {"session_type": "Actief herstel + lichte balvorm",
                                 "intensity_low": 0.55, "intensity_high": 0.65, "base_duration_min": 45},
}


@dataclass
class TrainingProposal:
    week_focus: WeekFocus
    suggested_session_type: str
    intensity_pct_mas_low: float
    intensity_pct_mas_high: float
    base_duration_min: int
    adjusted_duration_min: int
    base_distance_km: float
    adjusted_distance_km: float
    team_readiness_factor: float
    adjustment_note: str
    player_flags: list = field(default_factory=list)


def propose_next_training(week: CycleWeek, players: list, km_per_training: float) -> TrainingProposal:
    """
    km_per_training komt uit generate_cycle_km_plan() (zie volume_planning.py) voor
    dezelfde week — hier samengevoegd met team-readiness zodat duur ÉN
    afstandsdoel in één voorstel staan, consistent op- of afgeschaald.
    """
    profile = TEAM_SESSION_PROFILES[week.focus]

    fit_players = [p for p in players if not p.injury_flag]
    if fit_players:
        factors = [
            _load_adjustment_factor(_acwr(p), _wellness_composite(p), _acwr_trending_up(p.weekly_acute_load_history))
            for p in fit_players
        ]
        team_factor = round(sum(factors) / len(factors), 2)
    else:
        team_factor = 1.0

    adjusted_duration = round(profile["base_duration_min"] * team_factor)
    adjusted_distance = round(km_per_training * team_factor, 2)

    if team_factor <= 0.80:
        note = (f"Teambelasting/herstel duidelijk onder norm (factor {team_factor}). "
                f"Duur en km-doel verlaagd t.o.v. planning ({profile['base_duration_min']}' / "
                f"{km_per_training} km) — accent op techniek i.p.v. volume.")
    elif team_factor <= 0.90:
        note = f"Lichte team-vermoeidheid (factor {team_factor}): duur/km licht verlaagd."
    else:
        note = "Team-readiness normaal — sessie kan volgens planning uitgevoerd worden."

    return TrainingProposal(
        week_focus=week.focus, suggested_session_type=profile["session_type"],
        intensity_pct_mas_low=profile["intensity_low"], intensity_pct_mas_high=profile["intensity_high"],
        base_duration_min=profile["base_duration_min"], adjusted_duration_min=adjusted_duration,
        base_distance_km=km_per_training, adjusted_distance_km=adjusted_distance,
        team_readiness_factor=team_factor, adjustment_note=note,
        player_flags=flag_players(players),
    )
