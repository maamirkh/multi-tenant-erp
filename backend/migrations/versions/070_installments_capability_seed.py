"""Installments capability seed — Epic 10, Phase 0 (T009).

Registers the ``installments`` entitlement ``Capability`` row so Platform
Admin can grant/toggle it against plans (mirrors ``056``'s pure-SQL,
no-app-code-import style; schema-only otherwise since ``installments.*``
permission codes are added to ``users_roles/constants.py`` in Phase 1 and
take effect for **new** companies automatically via ``RoleSeedService`` —
see migration 071 for the backfill covering companies created before this
epic shipped).

Revision ID: 070
Revises: 069
Create Date: 2026-08-25
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "070"
down_revision = "069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO capabilities (key, module, display_name, grain, is_active)
        VALUES ('installments', 'installments', 'Installments', 'module', true)
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    # Guarded: skip the delete if any plan_capabilities row still references
    # this capability (that FK is ON DELETE RESTRICT) rather than raising.
    op.execute(
        """
        DELETE FROM capabilities
        WHERE key = 'installments'
        AND NOT EXISTS (
            SELECT 1 FROM plan_capabilities WHERE capability_key = 'installments'
        )
        """
    )
