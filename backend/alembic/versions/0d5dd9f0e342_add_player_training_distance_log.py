"""add player_training_distance_log

Revision ID: 0d5dd9f0e342
Revises: 4b622adf8127
Create Date: 2026-08-16T12:15:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0d5dd9f0e342'
down_revision: Union[str, None] = '4b622adf8127'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'player_training_distance_log',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('club_id', sa.UUID(), nullable=False),
        sa.Column('player_id', sa.UUID(), nullable=False),
        sa.Column('training_session_id', sa.UUID(), nullable=False),
        sa.Column('session_date', sa.Date(), nullable=False),
        sa.Column('training_distance_km', sa.Numeric(6, 2), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['player_id'], ['players.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['training_session_id'], ['training_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'training_session_id', 'player_id', name='player_training_distance_log_session_id_player_id_key'
        ),
    )
    op.create_index(
        op.f('ix_player_training_distance_log_player_id'),
        'player_training_distance_log', ['player_id'],
    )
    op.create_index(
        op.f('ix_player_training_distance_log_session_date'),
        'player_training_distance_log', ['session_date'],
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_player_training_distance_log_session_date'), table_name='player_training_distance_log')
    op.drop_index(op.f('ix_player_training_distance_log_player_id'), table_name='player_training_distance_log')
    op.drop_table('player_training_distance_log')
