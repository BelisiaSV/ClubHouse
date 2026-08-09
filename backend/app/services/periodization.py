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
    target_match_date: date
    target_peak_weekly_km: float = 25.0   # door coach bepaald piekvolume (100%-week)
    weeks: list = field(default_factory=list)   # list[CycleWeek]
    shift_count: int = 0

    def end_date(self) -> date:
        return self.start_date + timedelta(weeks=self.length_weeks)


LOAD_PCT_BY_FOCUS = {
    WeekFocus.ACCUMULATION: 75.0,
    WeekFocus.INTENSIFICATION: 90.0,
    WeekFocus.REALIZATION: 100.0,
    WeekFocus.DELOAD: 55.0,
    WeekFocus.RECOVERY: 40.0,
}

CYCLE_TEMPLATES = {
    4: [WeekFocus.ACCUMULATION, WeekFocus.INTENSIFICATION,
        WeekFocus.REALIZATION, WeekFocus.DELOAD],
    6: [WeekFocus.ACCUMULATION, WeekFocus.ACCUMULATION, WeekFocus.INTENSIFICATION,
        WeekFocus.INTENSIFICATION, WeekFocus.REALIZATION, WeekFocus.DELOAD],
    8: [WeekFocus.ACCUMULATION, WeekFocus.ACCUMULATION, WeekFocus.INTENSIFICATION,
        WeekFocus.INTENSIFICATION, WeekFocus.INTENSIFICATION, WeekFocus.REALIZATION,
        WeekFocus.REALIZATION, WeekFocus.DELOAD],
}


def build_cycle(name: str, length_weeks: int, start_date: date,
                 target_match_date: date, target_peak_weekly_km: float = 25.0) -> TrainingCycle:
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
    for w in cycle.weeks:
        week_end = w.week_start_date + timedelta(days=6)
        if w.week_start_date <= cycle.target_match_date <= week_end:
            w.focus = WeekFocus.REALIZATION
            w.planned_load_pct = LOAD_PCT_BY_FOCUS[WeekFocus.REALIZATION]
