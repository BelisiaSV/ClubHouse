"""add is_season_start to training_cycles

Revision ID: 219d9347302d
Revises: e5a1326b57e1
Create Date: 2026-08-16T16:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '219d9347302d'
down_revision: Union[str, None] = 'e5a1326b57e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'training_cycles',
        sa.Column('is_season_start', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )

    # Backfill: for every existing club, its chronologically FIRST cycle
    # (season.cycles[0], the one originally created by POST
    # /api/periodization/seasons) is the season-start cycle — never a later
    # queued/edited one. Drives suggest_player_minutes_cap()'s squad-wide
    # minutes-buildup advice, which is only meant for a genuinely
    # undertrained squad coming off a break, not every accumulation week
    # of an ongoing season.
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE training_cycles
        SET is_season_start = true
        WHERE id IN (
            SELECT DISTINCT ON (club_id) id
            FROM training_cycles
            ORDER BY club_id, start_date
        )
    """))


def downgrade() -> None:
    op.drop_column('training_cycles', 'is_season_start')
