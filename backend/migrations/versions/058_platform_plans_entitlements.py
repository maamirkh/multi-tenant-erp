"""Platform plans & entitlements — Epic 9A, Phase 2 (T016-T017).

Creates the commercial control-plane persistence layer (data-model.md
"Entitlement"): ``capabilities``, ``plans``, ``plan_capabilities``,
``subscriptions``. Also adds a real FK constraint
(``companies.subscription_id -> subscriptions.id``) on the existing,
already-nullable, already-unused ``companies.subscription_id`` column
(plan.md ADR-9) — existing rows keep NULL, no backfill.

``status`` columns use VARCHAR+CHECK, not a PostgreSQL ENUM type, matching
``Company.status``'s own convention (data-model.md "Plan"/"Subscription").
The one-active-subscription-per-tenant invariant is enforced by a
PostgreSQL partial unique index rather than an application-only check
(plan.md §26).

Revision ID: 058
Revises: 057
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "058"
down_revision = "057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- capabilities ---
    op.create_table(
        "capabilities",
        sa.Column("key", sa.String(50), nullable=False),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("grain", sa.String(20), nullable=False),
        sa.Column("display_name", sa.String(150), nullable=False),
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
        sa.PrimaryKeyConstraint("key"),
        sa.CheckConstraint(
            "grain IN ('module', 'feature')", name="ck_capabilities_grain"
        ),
        comment="Entitlement capability catalogue — e.g. inventory, sales, "
        "purchase, accounting, crm (Assumption A7)",
    )

    # --- plans ---
    op.create_table(
        "plans",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_commercially_available",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("billing_cycle_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("pricing_metadata", postgresql.JSONB(), nullable=True),
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
        sa.UniqueConstraint("code", name="uq_plans_code"),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'retired')", name="ck_plans_status"
        ),
        comment="SaaS Plan — code is configuration data, never a hardcoded "
        "product name (FR-9A-151)",
    )

    # --- plan_capabilities ---
    op.create_table(
        "plan_capabilities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capability_key", sa.String(50), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False),
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
            ["plan_id"],
            ["plans.id"],
            name="fk_plan_capabilities_plan_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["capability_key"],
            ["capabilities.key"],
            name="fk_plan_capabilities_capability_key",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "plan_id", "capability_key", name="uq_plan_capabilities_plan_capability"
        ),
        comment="The Plan Entitlement ceiling (plan.md §17.2's resolution table)",
    )

    # --- subscriptions ---
    op.create_table(
        "subscriptions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
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
            name="fk_subscriptions_company_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["plans.id"],
            name="fk_subscriptions_plan_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["platform_administrators.id"],
            name="fk_subscriptions_actor_id",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'ended')", name="ck_subscriptions_status"
        ),
        comment="Tenant plan assignment — 'trial' deliberately excluded "
        "(resolved OQ-1); CHECK-only design means adding it later needs no "
        "schema redesign",
    )
    op.create_index("ix_subscriptions_company_id", "subscriptions", ["company_id"])
    # One active subscription per tenant — PostgreSQL-native partial unique
    # index, not an application-only check (plan.md §26).
    op.execute("""
        CREATE UNIQUE INDEX uq_subscriptions_company_active
        ON subscriptions (company_id)
        WHERE status = 'active'
        """)

    # Real FK on the existing, already-nullable, already-unused
    # companies.subscription_id column (plan.md ADR-9). Existing rows keep
    # NULL — no backfill, no default Plan/Subscription force-assigned here.
    op.create_foreign_key(
        "fk_companies_subscription_id",
        "companies",
        "subscriptions",
        ["subscription_id"],
        ["id"],
    )


def downgrade() -> None:
    # Drop the FK constraint, leaving the pre-existing nullable column
    # intact — it predates Epic 9A.
    op.drop_constraint("fk_companies_subscription_id", "companies", type_="foreignkey")

    # Reset any values this migration's own lifetime populated (via
    # Epic 9A's rollout/subscription-assignment code) back to the
    # column's pre-058 invariant of always NULL — discovered live during
    # T214's real-Postgres upgrade->seed->bulk-assign->downgrade->upgrade
    # cycle: without this, a company whose subscription_id was ever set
    # leaves a dangling UUID once `subscriptions` is dropped below, and
    # the next `upgrade head` fails re-adding `fk_companies_subscription_id`
    # (ForeignKeyViolation) since that stale value no longer resolves.
    op.execute(
        "UPDATE companies SET subscription_id = NULL WHERE subscription_id IS NOT NULL"
    )

    op.execute("DROP INDEX IF EXISTS uq_subscriptions_company_active")
    op.drop_index("ix_subscriptions_company_id", "subscriptions")
    op.drop_table("subscriptions")

    op.drop_table("plan_capabilities")
    op.drop_table("plans")
    op.drop_table("capabilities")
