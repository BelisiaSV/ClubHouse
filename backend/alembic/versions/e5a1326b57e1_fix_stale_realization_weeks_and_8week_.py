"""fix stale realization weeks and 8-week recovery template

Revision ID: e5a1326b57e1
Revises: 0d5dd9f0e342
Create Date: 2026-08-16T14:00:00.000000

"""
from datetime import timedelta
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5a1326b57e1'
down_revision: Union[str, None] = '0d5dd9f0e342'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Mirrors app/services/periodization.py's CYCLE_TEMPLATES/LOAD_PCT_BY_FOCUS —
# kept as plain literals here rather than importing the app module, same
# convention as every other data-fixing migration in this project (migrations
# must stay correct forever, independent of the app's current code).
_CYCLE_TEMPLATES = {
    4: ['accumulation', 'intensification', 'realization', 'deload'],
    6: ['accumulation', 'accumulation', 'intensification', 'intensification', 'realization', 'deload'],
    8: ['accumulation', 'accumulation', 'intensification', 'recovery', 'intensification',
        'realization', 'realization', 'deload'],
}
_LOAD_PCT = {'accumulation': 100.00, 'intensification': 90.00, 'realization': 75.00,
             'deload': 50.00, 'recovery': 40.00}
_LENGTH_TYPE_TO_WEEKS = {'4_weeks': 4, '6_weeks': 6, '8_weeks': 8}


def upgrade() -> None:
    # align_cycle_to_nearest_match() (app/services/periodization.py) picks
    # the week nearest a cycle's end as its REALIZATION week whenever real
    # matches change, but never reverted a PREVIOUSLY-chosen week back to
    # its template focus first — so as which week counted as "nearest"
    # shifted over a season (matches added/moved/rescheduled), old
    # REALIZATION weeks stayed stuck alongside newly-chosen ones, leaving
    # some existing cycles' stored training_cycle_weeks rows with the phase
    # order corrupted (e.g. two REALIZATION weeks, no longer contiguous
    # blocks) even though CYCLE_TEMPLATES/build_cycle() were themselves
    # always correct. This resets every affected cycle's weeks back to the
    # pure template (including the new 8-week RECOVERY-at-position-4), then
    # reapplies the single target_match_date-based REALIZATION override —
    # the exact same logic the fixed align_cycle_to_nearest_match() now
    # applies on every future match change, just run once here for
    # cycles that already drifted.
    #
    # Only touches cycles with shift_count == 0 and a week count still
    # matching the plain template — a cycle already structurally reshaped
    # by handle_match_cancellation() no longer corresponds 1:1 with the
    # template and is left untouched, same safety condition the service
    # fix uses.
    conn = op.get_bind()
    cycles = conn.execute(
        sa.text("SELECT id, length_type, target_match_date, shift_count FROM training_cycles")
    ).fetchall()

    for cycle_id, length_type, target_match_date, shift_count in cycles:
        if shift_count:
            continue
        length_weeks = _LENGTH_TYPE_TO_WEEKS.get(length_type)
        template = _CYCLE_TEMPLATES.get(length_weeks)
        if template is None:
            continue

        week_rows = conn.execute(
            sa.text(
                "SELECT id, week_start_date FROM training_cycle_weeks "
                "WHERE training_cycle_id = :cid ORDER BY week_number"
            ),
            {"cid": cycle_id},
        ).fetchall()
        if len(week_rows) != len(template):
            continue

        for (week_id, _week_start), focus in zip(week_rows, template):
            conn.execute(
                sa.text("UPDATE training_cycle_weeks SET focus = :focus, planned_load_pct = :pct WHERE id = :wid"),
                {"focus": focus, "pct": _LOAD_PCT[focus], "wid": week_id},
            )

        if target_match_date is not None:
            target_week_id = None
            for week_id, week_start in week_rows:
                week_end = week_start + timedelta(days=6)
                if week_start <= target_match_date <= week_end:
                    target_week_id = week_id
                    break
            if target_week_id is not None:
                conn.execute(
                    sa.text(
                        "UPDATE training_cycle_weeks SET focus = 'realization', "
                        "planned_load_pct = 75.00 WHERE id = :wid"
                    ),
                    {"wid": target_week_id},
                )
                # Exactly one realization week per cycle — demote any OTHER
                # week the template reset left at realization (e.g. the
                # template's own default position, if the match falls
                # elsewhere) to intensification, matching the fixed
                # _align_realization_to_match()'s behavior.
                conn.execute(
                    sa.text(
                        "UPDATE training_cycle_weeks SET focus = 'intensification', "
                        "planned_load_pct = 90.00 "
                        "WHERE training_cycle_id = :cid AND id != :wid AND focus = 'realization'"
                    ),
                    {"cid": cycle_id, "wid": target_week_id},
                )


def downgrade() -> None:
    # The "before" state was accumulated drift, not a deterministic prior
    # formula (unlike e.g. 343d42ea3b38's LOAD_PCT_BY_FOCUS fix) — there is
    # no meaningful single state to revert to, so this is a no-op.
    pass
