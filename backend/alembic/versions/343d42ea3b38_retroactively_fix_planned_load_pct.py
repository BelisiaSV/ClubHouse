"""retroactively fix planned_load_pct on existing training_cycle_weeks

Revision ID: 343d42ea3b38
Revises: 2583afe44861
Create Date: 2026-08-14T11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '343d42ea3b38'
down_revision: Union[str, None] = '2583afe44861'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # LOAD_PCT_BY_FOCUS in app/services/periodization.py is only consulted
    # at cycle-CREATION time (inside build_cycle()) — the resulting
    # percentage is then frozen into each training_cycle_weeks row forever
    # after, never recomputed on read. Correcting the constant in code (the
    # accumulation=100/intensification=90/realization=75/deload=50 taper,
    # replacing the old, inverted 75/90/100/55) therefore never touched
    # already-created cycles' stored rows — this backfills them, the same
    # way the earlier target_peak_weekly_km migration backfilled that
    # column. planned_load_pct is deterministically a function of focus
    # (there is no UI to hand-edit it per week), so this is safe to apply
    # unconditionally to every row.
    op.execute("""
        UPDATE training_cycle_weeks
        SET planned_load_pct = CASE focus
            WHEN 'accumulation' THEN 100.00
            WHEN 'intensification' THEN 90.00
            WHEN 'realization' THEN 75.00
            WHEN 'deload' THEN 50.00
            WHEN 'recovery' THEN 40.00
            ELSE planned_load_pct
        END
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE training_cycle_weeks
        SET planned_load_pct = CASE focus
            WHEN 'accumulation' THEN 75.00
            WHEN 'intensification' THEN 90.00
            WHEN 'realization' THEN 100.00
            WHEN 'deload' THEN 55.00
            WHEN 'recovery' THEN 40.00
            ELSE planned_load_pct
        END
    """)
