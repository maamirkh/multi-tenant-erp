"""Platform quotas & overrides — Epic 9A, Phase 2 (T018-T019).

Creates the quota + override persistence layer (data-model.md
"Quotas & Overrides"): ``quota_definitions``, ``plan_quotas``,
``tenant_quota_overrides``, ``entitlement_overrides``. Consumed by the
Phase 8 quota foundation.

NULL ``limit_value``/``override_limit`` means unlimited (FR-9A-182) —
never a large sentinel number. "No duplicate active override" is enforced
by PostgreSQL partial unique indexes on both override tables (plan.md §26),
matching migration 058's ``subscriptions`` pattern.

Revision ID: 059
Revises: 058
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "059"
down_revision = "058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- quota_definitions ---
    op.create_table(
        "quota_definitions",
        sa.Column("key", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(150), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("enforcement_style", sa.String(20), nullable=False),
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
        sa.PrimaryKeyConstraint("key"),
        sa.CheckConstraint(
            "enforcement_style IN ('hard', 'soft', 'informational')",
            name="ck_quota_definitions_enforcement_style",
        ),
        comment="Quota category catalogue — users, branches, transactions, "
        "storage, api_calls, ai_credits; enforcement_style is declared "
        "explicitly, never defaults silently (BR-9A-030)",
    )

    # --- plan_quotas ---
    op.create_table(
        "plan_quotas",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quota_key", sa.String(50), nullable=False),
        sa.Column("limit_value", sa.Numeric(18, 2), nullable=True),
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
            ["plan_id"], ["plans.id"], name="fk_plan_quotas_plan_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["quota_key"],
            ["quota_definitions.key"],
            name="fk_plan_quotas_quota_key",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("plan_id", "quota_key", name="uq_plan_quotas_plan_quota"),
        sa.CheckConstraint(
            "limit_value IS NULL OR limit_value >= 0", name="ck_plan_quotas_limit_value"
        ),
        comment="NULL limit_value means unlimited (FR-9A-182) — never a large "
        "sentinel number",
    )

    # --- tenant_quota_overrides ---
    op.create_table(
        "tenant_quota_overrides",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quota_key", sa.String(50), nullable=False),
        sa.Column("override_limit", sa.Numeric(18, 2), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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
            ["company_id"],
            ["companies.id"],
            name="fk_tenant_quota_overrides_company_id",
        ),
        sa.ForeignKeyConstraint(
            ["quota_key"],
            ["quota_definitions.key"],
            name="fk_tenant_quota_overrides_quota_key",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["platform_administrators.id"],
            name="fk_tenant_quota_overrides_actor_id",
        ),
        sa.CheckConstraint(
            "override_limit IS NULL OR override_limit >= 0",
            name="ck_tenant_quota_overrides_override_limit",
        ),
        sa.CheckConstraint(
            "expires_at IS NULL OR expires_at > granted_at",
            name="ck_tenant_quota_overrides_expiry",
        ),
        comment="Null expires_at = permanent, explicitly distinguishable "
        "(not implicit)",
    )
    op.create_index(
        "ix_tenant_quota_overrides_company_id",
        "tenant_quota_overrides",
        ["company_id"],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_tenant_quota_overrides_company_quota_active
        ON tenant_quota_overrides (company_id, quota_key)
        WHERE is_active = true
        """
    )

    # --- entitlement_overrides ---
    op.create_table(
        "entitlement_overrides",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capability_key", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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
            ["company_id"],
            ["companies.id"],
            name="fk_entitlement_overrides_company_id",
        ),
        sa.ForeignKeyConstraint(
            ["capability_key"],
            ["capabilities.key"],
            name="fk_entitlement_overrides_capability_key",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["platform_administrators.id"],
            name="fk_entitlement_overrides_actor_id",
        ),
        sa.CheckConstraint(
            "expires_at IS NULL OR expires_at > granted_at",
            name="ck_entitlement_overrides_expiry",
        ),
        comment="Time-boxed (or permanent) entitlement override — auditable, "
        "reason-bound (FR-9A-170)",
    )
    op.create_index(
        "ix_entitlement_overrides_company_id",
        "entitlement_overrides",
        ["company_id"],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_entitlement_overrides_company_capability_active
        ON entitlement_overrides (company_id, capability_key)
        WHERE is_active = true
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS uq_entitlement_overrides_company_capability_active"
    )
    op.drop_index("ix_entitlement_overrides_company_id", "entitlement_overrides")
    op.drop_table("entitlement_overrides")

    op.execute("DROP INDEX IF EXISTS uq_tenant_quota_overrides_company_quota_active")
    op.drop_index("ix_tenant_quota_overrides_company_id", "tenant_quota_overrides")
    op.drop_table("tenant_quota_overrides")

    op.drop_table("plan_quotas")
    op.drop_table("quota_definitions")
