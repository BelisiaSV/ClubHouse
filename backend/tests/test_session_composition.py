"""
Regression test for the km-goal-driven rescaling in
services.session_composition.propose_session_composition(), specifically
against the longer partijvorm-bouts (SSG 3'/2' rust, MSG 5,5'/2,5' rust,
LSG 9'/3,5' rust) introduced to bring the rest structure in line with
small-sided-games literature. Those longer bouts/rest windows round total
distance down more aggressively (whole bouts, not fractional minutes), so
this pins the known-good result to guard against the rescaling drifting
outside an acceptable margin of the coach's km target.
"""

from app.services.periodization import WeekFocus
from app.services.session_composition import propose_session_composition

KM_TARGET_TOLERANCE_PCT = 10


def test_intensification_18_players_68min_63km_stays_within_10pct_of_km_target():
    composition = propose_session_composition(
        week_focus=WeekFocus.INTENSIFICATION,
        num_players=18,
        target_duration_min=68,
        target_distance_km=6.3,
    )

    deviation_pct = abs(composition.total_distance_km - 6.3) / 6.3 * 100
    assert deviation_pct <= KM_TARGET_TOLERANCE_PCT, (
        f"Voorstel ({composition.total_distance_km} km) wijkt {deviation_pct:.1f}% af van het "
        f"km-doel (6.3 km) — meer dan de toegestane {KM_TARGET_TOLERANCE_PCT}%."
    )

    # Pin to the currently known-good result so a silent regression in the
    # rescaling/rounding logic shows up as a precise failure, not just a
    # tolerance breach.
    assert composition.total_distance_km == 5.99
