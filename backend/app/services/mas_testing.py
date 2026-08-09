"""
mas_testing.py

MAS-testplanning (wanneer moet een speler opnieuw getest worden) en de
automatische afleiding van trainingszones uit een MAS-score.

Zuiver en side-effect-vrij: geen databasetoegang.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from app.services.periodization import TrainingCycle, WeekFocus

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
