"""
team_readiness.py

Teamreadiness en het daaruit afgeleide trainingsvoorstel (duur + km,
afgeschaald op basis van team-belasting/herstel).

KM-GEBASEERDE FITHEIDSLAAG (basis, ALTIJD actief): acute_km_7d/
chronic_km_28d/weekly_acute_km_history worden rechtstreeks afgeleid uit
effectief afgelegde training- en wedstrijdkilometers — geen coach-actie
nodig, werkt zonder dat er ooit een RPE/wellness-formulier ingevuld is.

RPE/WELLNESS-LAAG (optioneel, bovenop de km-laag): telt enkel mee als
rpe_module_active=True wordt meegegeven — zie app.services.platform_admin.
ModuleKey.RPE_WELLNESS. Is die module uit voor een club, dan bepaalt puur
de kilometerdata het resultaat; is ze aan, dan wint het strengste
(voorzichtigste) signaal van de twee lagen.

Zuiver en side-effect-vrij: geen databasetoegang.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from app.services.periodization import CycleWeek, Season, WeekFocus, get_active_cycle_and_week
from app.services.volume_planning import calculate_km_target_per_position, generate_cycle_km_plan


@dataclass
class PlayerReadiness:
    player_name: str
    # --- KM-GEBASEERDE BELASTING (externe load) — ALTIJD beschikbaar,
    # rechtstreeks afgeleid uit effectief afgelegde afstand (training +
    # wedstrijd), geen RPE-invoer van de coach/speler nodig. Dit is de
    # BASISLAAG van de fitheidsbepaling in het hele platform.
    acute_km_7d: float = 0.0
    chronic_km_28d: float = 0.0
    injury_flag: bool = False
    # Laatste 3 (of meer) wekelijkse acute-km-metingen, oudste eerst, meest
    # recente laatst — voor trenddetectie (zie _acwr_trending_up).
    weekly_acute_km_history: list = field(default_factory=list)

    # --- RPE/WELLNESS-LAAG — VOLLEDIG OPTIONEEL. Enkel ingevuld/gebruikt
    # als de RPE-module voor deze club geactiveerd is via het adminpaneel
    # (app.services.platform_admin.ModuleKey.RPE_WELLNESS). None = module
    # uit, of coach heeft deze speler nog niet ingevuld.
    acute_load_7d: Optional[float] = None
    chronic_load_28d: Optional[float] = None
    sleep_quality: Optional[int] = None
    fatigue_level: Optional[int] = None
    muscle_soreness: Optional[int] = None
    stress_level: Optional[int] = None
    mood: Optional[int] = None


@dataclass
class PlayerFlag:
    player_name: str
    flag_type: str        # 'overload' | 'underload' | 'poor_recovery' | 'injured' | 'acwr_trending_up'
    detail: str
    recommendation: str
    source: str = "km"    # 'km' (basislaag, altijd) | 'rpe' (enkel als module actief)


def _acwr_km(player: PlayerReadiness) -> Optional[float]:
    """De BASIS-ACWR van het platform: acute:chronische ratio op effectief
    afgelegde kilometers (training + wedstrijd), niet op RPE. Externe-
    belastingsmaten zoals afstand zijn in de sportwetenschap een erkend
    alternatief voor (of aanvulling op) interne/RPE-gebaseerde ACWR — en
    hier bewust de STANDAARD, want ze vragen geen actie van coach of
    speler: de data komt rechtstreeks uit de al ingevoerde trainings-/
    wedstrijdgegevens."""
    if player.chronic_km_28d <= 0:
        return None
    return round(player.acute_km_7d / player.chronic_km_28d, 2)


def _acwr_rpe(player: PlayerReadiness) -> Optional[float]:
    """Enkel bruikbaar/zinvol als de RPE-module actief is."""
    if player.acute_load_7d is None or player.chronic_load_28d is None or player.chronic_load_28d <= 0:
        return None
    return round(player.acute_load_7d / player.chronic_load_28d, 2)


def _wellness_composite(player: PlayerReadiness) -> Optional[float]:
    """Enkel berekenbaar als de RPE-module actief is EN alle velden ingevuld zijn."""
    fields = [player.sleep_quality, player.fatigue_level, player.muscle_soreness,
              player.stress_level, player.mood]
    if any(f is None for f in fields):
        return None
    normalized = [player.sleep_quality, 6 - player.fatigue_level,
                  6 - player.muscle_soreness, 6 - player.stress_level, player.mood]
    return round(sum(normalized) / len(normalized), 2)


def _acwr_trending_up(weekly_history: list, min_weeks: int = 3,
                       min_total_increase_pct: float = 0.15) -> bool:
    """
    Detecteert een GELEIDELIJK STIJGENDE belasting over opeenvolgende weken
    (op km-basis), ook al zit de ACWR nog onder de 1.5-alarmdrempel — vaak
    een vroeger signaal dan de drempeloverschrijding zelf. Vereist minstens
    'min_weeks' metingen, elk hoger dan de vorige, met een totale stijging
    van minstens 'min_total_increase_pct'.
    """
    if len(weekly_history) < min_weeks:
        return False
    recent = weekly_history[-min_weeks:]
    monotonic_increase = all(recent[i] < recent[i + 1] for i in range(len(recent) - 1))
    if not monotonic_increase or recent[0] <= 0:
        return False
    total_increase_pct = (recent[-1] - recent[0]) / recent[0]
    return total_increase_pct >= min_total_increase_pct


def _load_adjustment_factor(
    acwr_km: Optional[float],
    trending_up: bool = False,
    wellness: Optional[float] = None,
    acwr_rpe: Optional[float] = None,
    rpe_module_active: bool = False,
) -> float:
    """
    Km-ACWR is ALTIJD de basis van deze factor. De RPE-laag (wellness,
    sRPE-ACWR) telt enkel mee als rpe_module_active=True — is de module
    uit, dan bepaalt puur de kilometerdata het resultaat. Is de module
    aan, dan wordt het STRENGSTE (laagste, dus meest voorzichtige) van
    beide signalen gebruikt.
    """
    factor = 1.0
    if acwr_km is not None:
        if acwr_km > 1.5:
            factor = min(factor, 0.70)
        elif acwr_km > 1.3:
            factor = min(factor, 0.85)
        elif acwr_km < 0.8:
            factor = min(factor, 0.90)
    if trending_up:
        factor = min(factor, 0.90)

    if rpe_module_active:
        if acwr_rpe is not None:
            if acwr_rpe > 1.5:
                factor = min(factor, 0.70)
            elif acwr_rpe > 1.3:
                factor = min(factor, 0.85)
            elif acwr_rpe < 0.8:
                factor = min(factor, 0.90)
        if wellness is not None:
            if wellness < 2.5:
                factor = min(factor, 0.70)
            elif wellness < 3.2:
                factor = min(factor, 0.85)
    return factor


def flag_players(players: list, rpe_module_active: bool = False) -> list:
    """
    Genereert aandachtspunten. De km-gebaseerde vlaggen (overload/
    underload/trending_up) worden ALTIJD berekend — dit is de basislaag
    die zonder RPE werkt. De wellness-vlag ('poor_recovery') en een
    eventuele RPE-gebaseerde overload-vlag komen er ENKEL bij als
    rpe_module_active=True (doorgegeven vanuit app.services.platform_admin:
    is ModuleKey.RPE_WELLNESS actief voor deze club?). Is de module uit,
    dan worden RPE/wellness-velden op de speler genegeerd, zelfs als ze
    toevallig ingevuld zijn.
    """
    flags = []
    for p in players:
        if p.injury_flag:
            flags.append(PlayerFlag(p.player_name, "injured",
                                     "Actief blessure- of pijnsignaal.",
                                     "Uitsluiten van teamtraining, individueel/revalidatieprogramma.",
                                     source="km"))
            continue

        acwr_km = _acwr_km(p)
        trending_up = _acwr_trending_up(p.weekly_acute_km_history)

        if acwr_km is not None and acwr_km > 1.5:
            flags.append(PlayerFlag(p.player_name, "overload",
                                     f"Km-ACWR = {acwr_km} (>1.5, snelle belastingsopbouw in afgelegde afstand).",
                                     "Volume individueel met ~25-30% reduceren.", source="km"))
        elif acwr_km is not None and acwr_km < 0.8:
            flags.append(PlayerFlag(p.player_name, "underload",
                                     f"Km-ACWR = {acwr_km} (<0.8, mogelijk detraining).",
                                     "Kan een extra individuele MAS-gebaseerde sessie aan.", source="km"))
        elif trending_up:
            flags.append(PlayerFlag(
                p.player_name, "acwr_trending_up",
                f"Afgelegde afstand stijgt {len(p.weekly_acute_km_history[-3:])} weken op rij "
                f"({p.weekly_acute_km_history[-3:]}), km-ACWR ({acwr_km}) zit nog onder de alarmdrempel.",
                "Vroeg signaal — monitor komende week extra, geen directe reductie nodig maar geen "
                "verdere opbouw forceren.", source="km"))

        if rpe_module_active:
            wellness = _wellness_composite(p)
            acwr_rpe = _acwr_rpe(p)
            if acwr_rpe is not None and acwr_rpe > 1.5 and not any(f.player_name == p.player_name for f in flags):
                flags.append(PlayerFlag(p.player_name, "overload",
                                         f"RPE-ACWR = {acwr_rpe} (>1.5, snelle belastingsopbouw op basis van RPE).",
                                         "Volume individueel met ~25-30% reduceren.", source="rpe"))
            if wellness is not None and wellness < 2.5:
                flags.append(PlayerFlag(p.player_name, "poor_recovery",
                                         f"Wellness-score {wellness}/5.",
                                         "Monitoren, overweeg lichtere belasting of rustdag.", source="rpe"))
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
    session_index: int = 1          # which training in the week (1, 2, ...)
    player_flags: list = field(default_factory=list)
    distance_by_position: dict = field(default_factory=dict)   # {PlayerPosition: km}


def propose_next_training(
    week: CycleWeek, players: list, km_per_training: float, rpe_module_active: bool = False
) -> TrainingProposal:
    """
    km_per_training komt uit generate_cycle_km_plan() (zie volume_planning.py) voor
    dezelfde week — hier samengevoegd met team-readiness zodat duur ÉN
    afstandsdoel in één voorstel staan, consistent op- of afgeschaald.

    rpe_module_active: zie propose_training_week's docstring.
    """
    profile = TEAM_SESSION_PROFILES[week.focus]

    fit_players = [p for p in players if not p.injury_flag]
    if fit_players:
        factors = [
            _load_adjustment_factor(
                _acwr_km(p), _acwr_trending_up(p.weekly_acute_km_history),
                wellness=_wellness_composite(p), acwr_rpe=_acwr_rpe(p),
                rpe_module_active=rpe_module_active,
            )
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
        player_flags=flag_players(players, rpe_module_active=rpe_module_active),
        distance_by_position=calculate_km_target_per_position(adjusted_distance),
    )


def propose_training_week(
    season: Season, players: list, today: date, rpe_module_active: bool = False
) -> list:
    """
    Genereert een voorstel voor ALLE trainingen van de actieve week, niet
    enkel de eerstvolgende — zodat de coach op maandag al zijn hele week kan
    uitstippelen. Zoekt zelf de actieve cyclus/week op (get_active_cycle_and_week)
    op basis van 'today', en verdeelt het weekvolume over het aantal geplande
    trainingen (week.num_trainings), met een lichtjes oplopende intensiteit
    doorheen de week — een vereenvoudigde, maar gangbare microcyclus-opbouw
    naar de zwaarste sessie toe. Coaches kunnen dit als leidraad gebruiken en
    zelf bijsturen per sessie (zie propose_session_composition() voor de
    concrete oefenvormen van een gekozen sessie).

    rpe_module_active: doorgegeven vanuit app.services.platform_admin (is
    ModuleKey.RPE_WELLNESS actief voor deze club?) — bepaalt of de
    wellness/RPE-laag meetelt bovenop de altijd-actieve km-gebaseerde
    fitheidsbepaling."""
    cycle, week = get_active_cycle_and_week(season, today)
    if week is None:
        raise ValueError(f"Geen actieve cyclusweek gevonden voor {today}.")

    km_plans = generate_cycle_km_plan(cycle)
    km_plan_for_week = next(p for p in km_plans if p.week_number == week.week_number)

    profile = TEAM_SESSION_PROFILES[week.focus]
    num_sessions = max(1, week.num_trainings)

    fit_players = [p for p in players if not p.injury_flag]
    if fit_players:
        factors = [_load_adjustment_factor(
                       _acwr_km(p), _acwr_trending_up(p.weekly_acute_km_history),
                       wellness=_wellness_composite(p), acwr_rpe=_acwr_rpe(p),
                       rpe_module_active=rpe_module_active)
                   for p in fit_players]
        team_factor = round(sum(factors) / len(factors), 2)
    else:
        team_factor = 1.0

    if team_factor <= 0.80:
        note = (f"Teambelasting/herstel duidelijk onder norm (factor {team_factor}). "
                f"Volume deze week verlaagd — accent op techniek i.p.v. volume.")
    elif team_factor <= 0.90:
        note = f"Lichte team-vermoeidheid (factor {team_factor}): duur/km licht verlaagd."
    else:
        note = "Team-readiness normaal — sessies volgens planning."

    flags = flag_players(players, rpe_module_active=rpe_module_active)

    proposals = []
    for i in range(num_sessions):
        if num_sessions == 1:
            intensity_low = intensity_high = profile["intensity_low"]
        else:
            span = profile["intensity_high"] - profile["intensity_low"]
            frac = i / (num_sessions - 1)
            # laatste sessie van de week raakt het hoogste punt van de band;
            # eerdere sessies blijven er bewust net onder
            intensity_low = round(profile["intensity_low"] + frac * span * 0.85, 2)
            intensity_high = round(min(intensity_low + span * 0.15, profile["intensity_high"]), 2)

        adjusted_duration = round(profile["base_duration_min"] * team_factor)
        adjusted_distance = round(km_plan_for_week.km_per_training * team_factor, 2)

        proposals.append(TrainingProposal(
            week_focus=week.focus, suggested_session_type=profile["session_type"],
            intensity_pct_mas_low=intensity_low, intensity_pct_mas_high=intensity_high,
            base_duration_min=profile["base_duration_min"], adjusted_duration_min=adjusted_duration,
            base_distance_km=km_plan_for_week.km_per_training, adjusted_distance_km=adjusted_distance,
            team_readiness_factor=team_factor, adjustment_note=note,
            session_index=i + 1,
            player_flags=flags if i == 0 else [],  # aandachtspunten enkel bij sessie 1 tonen, niet herhalen
            distance_by_position=calculate_km_target_per_position(adjusted_distance),
        ))
    return proposals
