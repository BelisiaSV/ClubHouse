"""add running_groups tables

Revision ID: 55057e2f556d
Revises: 219d9347302d
Create Date: 2026-08-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '55057e2f556d'
down_revision: Union[str, None] = '219d9347302d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('running_groups',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
    sa.Column('club_id', sa.UUID(), nullable=False),
    sa.Column('label', sa.Text(), nullable=False),
    sa.Column('prescriptie_mas_kmh', sa.Numeric(4, 2), nullable=False),
    sa.Column('avg_mas_kmh', sa.Numeric(4, 2), nullable=False),
    sa.Column('min_mas_kmh', sa.Numeric(4, 2), nullable=False),
    sa.Column('max_mas_kmh', sa.Numeric(4, 2), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('running_group_players',
    sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
    sa.Column('running_group_id', sa.UUID(), nullable=False),
    sa.Column('player_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['running_group_id'], ['running_groups.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['player_id'], ['players.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_running_group_players_running_group_id'), 'running_group_players', ['running_group_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_running_group_players_running_group_id'), table_name='running_group_players')
    op.drop_table('running_group_players')
    op.drop_table('running_groups')
