"""add rpe_wellness module

Revision ID: 4b622adf8127
Revises: 343d42ea3b38
Create Date: 2026-08-16T12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4b622adf8127'
down_revision: Union[str, None] = '343d42ea3b38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot be used in the same transaction as code
    # that USES the new value (a hard Postgres restriction, not lifted by
    # newer versions) — commit immediately so the backfill INSERT below can
    # actually reference 'rpe_wellness'.
    op.execute("ALTER TYPE module_key ADD VALUE IF NOT EXISTS 'rpe_wellness'")
    op.execute("COMMIT")

    # Backfill: RPE & Wellness ships in_base_package=True (see
    # services/platform_admin.py), same as every other base-package module —
    # every existing club gets it enabled by default, exactly like the
    # original club_modules backfill (6cea37cb8bb9) did for the first batch.
    # Without this, is_module_enabled_for_club()'s default-deny-on-missing-row
    # behavior would silently lock every existing club out of the RPE/wellness
    # questionnaire the moment the module-gating dependency on that router
    # goes live.
    conn = op.get_bind()
    club_ids = [row[0] for row in conn.execute(sa.text("SELECT id FROM clubs")).fetchall()]
    for club_id in club_ids:
        conn.execute(
            sa.text(
                "INSERT INTO club_modules (club_id, module_key, enabled, changed_by) "
                "VALUES (:club_id, 'rpe_wellness', true, :changed_by) "
                "ON CONFLICT (club_id, module_key) DO NOTHING"
            ),
            {"club_id": club_id, "changed_by": "migratie: RPE & Wellness module backfill"},
        )


def downgrade() -> None:
    # Postgres has no native DROP VALUE for enum labels — removing the
    # club_modules rows is sufficient to fully disable the module again;
    # leaving the unused enum label behind is inert and the standard,
    # safe approach for this situation.
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM club_modules WHERE module_key = 'rpe_wellness'"))
