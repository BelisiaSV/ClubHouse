"""
volume_planning.py

Wekelijkse kilometerplanning per cyclusfase: verdeelt het cyclus-piekvolume
over de weken (via planned_load_pct), trekt het wedstrijdaandeel eraf, en
verdeelt de rest over de geplande trainingen.

Zuiver en side-effect-vrij: geen databasetoegang.
"""

from dataclasses import dataclass

from app.services.periodization import TrainingCycle, WeekFocus


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
    plans = []
    for week in cycle.weeks:
        weekly_target_km = round(cycle.target_peak_weekly_km * (week.planned_load_pct / 100), 2)
        match_distance_km = round(week.num_matches * avg_match_distance_km, 2)
        training_distance_km = round(weekly_target_km - match_distance_km, 2)

        note = ""
        if training_distance_km < 0:
            training_distance_km = 0.0
            note = (f"Wedstrijdcongestie ({week.num_matches} wedstrijden): "
                    f"trainingsvolume ondergeschikt aan herstel.")

        if week.num_trainings > 0:
            km_per_training = round(training_distance_km / week.num_trainings, 2)
            if 0 < km_per_training < min_recovery_km_per_training and not note:
                km_per_training = min_recovery_km_per_training
                note = f"Opgetrokken naar het minimum van {min_recovery_km_per_training} km."
        else:
            km_per_training = 0.0
            note = note or "Geen trainingen gepland deze week."

        plans.append(WeeklyKmPlan(
            week_number=week.week_number, focus=week.focus, weekly_target_km=weekly_target_km,
            match_distance_km=match_distance_km, training_distance_km=training_distance_km,
            km_per_training=km_per_training,
            note=note or (f"{week.num_matches} wedstrijd(en) + {week.num_trainings} training(en) "
                           f"-> {km_per_training} km/training."),
        ))
    return plans
