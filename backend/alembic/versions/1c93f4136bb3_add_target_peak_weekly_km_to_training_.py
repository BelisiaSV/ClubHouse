"""add target_peak_weekly_km to training_cycles

Revision ID: 1c93f4136bb3
Revises: 94386a068622
Create Date: 2026-08-13T12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '1c93f4136bb3'
down_revision: Union[str, None] = '94386a068622'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'training_cycles',
        sa.Column('target_peak_weekly_km', sa.Numeric(6, 2), nullable=False, server_default='25.00'),
    )


def downgrade() -> None:
    op.drop_column('training_cycles', 'target_peak_weekly_km')
