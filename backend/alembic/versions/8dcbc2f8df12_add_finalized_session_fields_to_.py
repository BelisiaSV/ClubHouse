"""add finalized session fields to training_sessions

Revision ID: 8dcbc2f8df12
Revises: 1c93f4136bb3
Create Date: 2026-08-13T13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8dcbc2f8df12'
down_revision: Union[str, None] = '1c93f4136bb3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('training_sessions', sa.Column('session_date', sa.Date(), nullable=True))
    op.add_column('training_sessions', sa.Column('blocks', postgresql.JSONB(), nullable=True))
    op.add_column('training_sessions', sa.Column('skipped_vormen', postgresql.JSONB(), nullable=True))
    op.add_column(
        'training_sessions',
        sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('training_sessions', 'finalized_at')
    op.drop_column('training_sessions', 'skipped_vormen')
    op.drop_column('training_sessions', 'blocks')
    op.drop_column('training_sessions', 'session_date')
