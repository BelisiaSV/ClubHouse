"""make target_match_date nullable on training_cycles

Revision ID: 2583afe44861
Revises: 48cda2da5e2f
Create Date: 2026-08-14T10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2583afe44861'
down_revision: Union[str, None] = '48cda2da5e2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('training_cycles', 'target_match_date', existing_type=sa.Date(), nullable=True)


def downgrade() -> None:
    op.alter_column('training_cycles', 'target_match_date', existing_type=sa.Date(), nullable=False)
