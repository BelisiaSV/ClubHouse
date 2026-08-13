"""add session-day context fields to rpe_wellness_data + club.training_weekdays

Revision ID: 94386a068622
Revises: 6cea37cb8bb9
Create Date: 2026-08-13T12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '94386a068622'
down_revision: Union[str, None] = '6cea37cb8bb9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    external_load_category = postgresql.ENUM(
        'none', 'light', 'physical', name='external_load_category'
    )
    external_load_category.create(op.get_bind())

    op.add_column(
        'rpe_wellness_data',
        sa.Column('external_load_category', external_load_category, nullable=True),
    )
    op.add_column(
        'rpe_wellness_data',
        sa.Column('extra_activity_today', sa.Boolean(), nullable=True),
    )
    op.add_column(
        'rpe_wellness_data',
        sa.Column('extra_activity_note', sa.Text(), nullable=True),
    )
    op.add_column(
        'clubs',
        sa.Column('training_weekdays', postgresql.ARRAY(sa.Integer()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('clubs', 'training_weekdays')
    op.drop_column('rpe_wellness_data', 'extra_activity_note')
    op.drop_column('rpe_wellness_data', 'extra_activity_today')
    op.drop_column('rpe_wellness_data', 'external_load_category')
    postgresql.ENUM(name='external_load_category').drop(op.get_bind())
