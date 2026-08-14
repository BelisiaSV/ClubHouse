"""fix target_peak_weekly_km default to 23 km

Revision ID: 48cda2da5e2f
Revises: 8dcbc2f8df12
Create Date: 2026-08-14T09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '48cda2da5e2f'
down_revision: Union[str, None] = '8dcbc2f8df12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('training_cycles', 'target_peak_weekly_km', server_default='23.00')
    # Every code path that creates a cycle now defaults to 23.0 km, but
    # existing rows still sitting on the old accidental 25.00 default were
    # never a deliberate coach choice (the app never exposed a "piekvolume"
    # input until now) — correct those specifically. A row a coach has
    # since edited to a genuinely different value is left untouched.
    op.execute("UPDATE training_cycles SET target_peak_weekly_km = 23.00 WHERE target_peak_weekly_km = 25.00")


def downgrade() -> None:
    op.alter_column('training_cycles', 'target_peak_weekly_km', server_default='25.00')
