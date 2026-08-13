"""
rpe_wellness.py

Bepaalt of de RPE/wellness-invulvraag vandaag moet verschijnen: enkel op
dagen met een geplande training of wedstrijd, niet dagelijks (zie het
aangeleverde vragenlijst-overzicht — bij amateurclubs met 1-2 sessies/week
verhoogt een dagelijkse vraag vooral "enquêtemoeheid").

Zuiver en side-effect-vrij: geen databasetoegang — app/routers/rpe_wellness.py
haalt de training_weekdays van de club en de match-data op en roept dit aan.
"""

from dataclasses import dataclass
from datetime import date


@dataclass
class SessionDayResult:
    is_session_day: bool
    reason: str | None  # 'match' | 'training' | None


def is_session_day(target_date: date, training_weekdays: list[int] | None, match_dates: list[date]) -> SessionDayResult:
    """training_weekdays: 0=Monday..6=Sunday (Python's date.weekday()), as
    configured on the club (Club.training_weekdays) — None/empty means no
    recurring training schedule has been set up yet, so only match days
    trigger the prompt until a coach configures it in Settings."""
    if target_date in match_dates:
        return SessionDayResult(is_session_day=True, reason="match")
    if training_weekdays and target_date.weekday() in training_weekdays:
        return SessionDayResult(is_session_day=True, reason="training")
    return SessionDayResult(is_session_day=False, reason=None)
