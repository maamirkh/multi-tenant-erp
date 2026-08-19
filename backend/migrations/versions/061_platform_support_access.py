"""Platform support access — Epic 9A, Phase 2 (T022-T023).

Creates ``support_access_grants`` (data-model.md "Support Access") and
closes the deferred FK from migration 057: ``platform_audit_events``
already has the nullable ``support_access_grant_id`` column (added in 057
because ``support_access_grants`` didn't exist yet); this migration adds
its FK constraint now that the target table exists — same deferred-FK
technique migration 055 uses for the ``crm_leads``/``crm_opportunities``
cycle (BR-9A-022 — no parallel audit table).

**This is the final Epic 9A migration.** The frozen migration range is
`057`-`061`; no `062` exists or may be created (ADR-8 — bootstrap
credential provisioning is a separate operator command, never a
migration).

Revision ID: 061
Revises: 060
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "061"
down_revision = "060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_access_grants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "platform_administrator_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["platform_administrator_id"],
            ["platform_administrators.id"],
            name="fk_support_access_grants_admin_id",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_support_access_grants_company_id",
        ),
        sa.ForeignKeyConstraint(
            ["ended_by"],
            ["platform_administrators.id"],
            name="fk_support_access_grants_ended_by",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'expired', 'terminated')",
            name="ck_support_access_grants_status",
        ),
        sa.CheckConstraint(
            "expires_at > started_at", name="ck_support_access_grants_expiry"
        ),
        comment="Time-bounded, reason-required, inspection-only support-access "
        "grant — exactly one target tenant per grant (FR-9A-191); no "
        "indefinite grant (FR-9A-193)",
    )
    op.create_index(
        "ix_support_access_grants_admin_id",
        "support_access_grants",
        ["platform_administrator_id"],
    )
    op.create_index(
        "ix_support_access_grants_company_id",
        "support_access_grants",
        ["company_id"],
    )

    # Deferred FK closing the 057 -> 061 cycle now that support_access_grants
    # exists.
    op.create_foreign_key(
        "fk_platform_audit_events_support_access_grant_id",
        "platform_audit_events",
        "support_access_grants",
        ["support_access_grant_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_platform_audit_events_support_access_grant_id",
        "platform_audit_events",
        type_="foreignkey",
    )

    op.drop_index("ix_support_access_grants_company_id", "support_access_grants")
    op.drop_index("ix_support_access_grants_admin_id", "support_access_grants")
    op.drop_table("support_access_grants")
