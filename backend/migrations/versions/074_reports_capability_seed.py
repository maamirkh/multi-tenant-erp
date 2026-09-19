"""Reports capability seed — Epic 11, Phase 1 (T035).

Registers the ``reports`` entitlement ``Capability`` row so Platform
Admin can grant/toggle it against plans (mirrors ``070``'s pure-SQL,
no-app-code-import style; schema-only otherwise since ``reports.*``
permission codes are added to ``users_roles/constants.py`` in Phase 0 and
take effect for **new** companies automatically via ``RoleSeedService`` —
see migration 075 for the backfill covering companies created before this
epic shipped).

**Renumbered per explicit correction (2026-09-12)**: Phase 0 introduced
``073_reports_foundation.py`` (the ``reports_feature_flags`` table, a
genuine cross-document gap fixed at Phase 0), which claimed revision
``073`` first. This migration — originally candidate-numbered ``073`` in
plan.md §16/tasks.md T035 — is renumbered to ``074`` accordingly, with
every subsequent Phase 1 migration shifted by the same +1 (075
permission seed, 076 saved views table).

Revision ID: 074
Revises: 073
Create Date: 2026-09-12
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "074"
down_revision = "073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO capabilities (key, module, display_name, grain, is_active)
        VALUES ('reports', 'reports', 'Reports & Analytics', 'module', true)
        ON CONFLICT (key) DO NOTHING
        """)


def downgrade() -> None:
    # Guarded: skip the delete if any plan_capabilities row still references
    # this capability (that FK is ON DELETE RESTRICT) rather than raising.
    op.execute("""
        DELETE FROM capabilities
        WHERE key = 'reports'
        AND NOT EXISTS (
            SELECT 1 FROM plan_capabilities WHERE capability_key = 'reports'
        )
        """)
