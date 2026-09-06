"""Installments foundation — Epic 10, Phase 0 (T001).

Creates the three tables every later Installments phase depends on:
``installments_feature_flags`` (module gate, mirrors ``crm_feature_flags``
exactly), ``installment_sequences`` (tenant-scoped contract-number
generator, mirrors ``accounting_sequences``/``sales_sequences``' locking
pattern), and ``installment_configurations`` (tenant/branch policy).

**Partial unique indexes, not a plain UNIQUE(company_id, branch_id)**
(tasks.md T001 correction): PostgreSQL treats multiple ``NULL``s in
``branch_id`` as distinct values, so a plain composite unique constraint
would never actually block a second company-level (``branch_id IS NULL``)
row. Two explicit partial unique indexes are used instead:
``uq_installment_configurations_branch`` (branch-specific overrides —
different branches coexist, a duplicate for the same branch is rejected)
and ``uq_installment_configurations_company_default`` (at most one
company-level/default row per company) — mirrors the platform's own
``uq_subscriptions_company_active`` partial-unique-index precedent
(plan.md §2/§7.2).

Revision ID: 062
Revises: 061
Create Date: 2026-08-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "062"
down_revision = "061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- installments_feature_flags (mirrors crm_feature_flags exactly) ---
    op.create_table(
        "installments_feature_flags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "flag_key",
            sa.String(50),
            server_default=sa.text("'feature.installments.enabled'"),
            nullable=False,
        ),
        sa.Column("is_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.UniqueConstraint(
            "company_id", "flag_key", name="uq_installments_feature_flags_company_key"
        ),
        comment="Per-company feature flag overrides for the Installments module",
    )
    op.create_index(
        "ix_installments_feature_flags_flag_key",
        "installments_feature_flags",
        ["flag_key"],
    )

    # --- installment_sequences (mirrors accounting_sequences exactly) ---
    op.create_table(
        "installment_sequences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(10), nullable=False),
        sa.Column("prefix", sa.String(10), server_default="'IC'", nullable=False),
        sa.Column("current_value", sa.Integer(), server_default="0", nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("reset_yearly", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "format_pattern",
            sa.String(30),
            server_default=sa.text("'{PREFIX}-{YEAR}-{SEQ:06d}'"),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.UniqueConstraint(
            "company_id",
            "document_type",
            "year",
            name="uq_installment_sequences_company_type_year",
        ),
        sa.CheckConstraint(
            "document_type IN ('IC')", name="ck_installment_sequences_document_type"
        ),
        sa.CheckConstraint(
            "current_value >= 0", name="ck_installment_sequences_current_value"
        ),
        comment=(
            "Gap-free auto-numbering sequences for Installments contract "
            "numbers, locked with SELECT FOR UPDATE"
        ),
    )

    # --- installment_configurations ---
    op.create_table(
        "installment_configurations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("allowed_frequencies", postgresql.JSONB(), nullable=False),
        sa.Column("min_term", sa.Integer(), nullable=False),
        sa.Column("max_term", sa.Integer(), nullable=False),
        sa.Column("min_down_payment_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("min_down_payment_amount", sa.Numeric(20, 6), nullable=True),
        sa.Column("max_financed_amount", sa.Numeric(20, 6), nullable=True),
        sa.Column(
            "rounding_policy",
            sa.String(20),
            server_default=sa.text("'ROUND_HALF_UP'"),
            nullable=False,
        ),
        sa.Column(
            "grace_period_days", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("late_charge_policy", postgresql.JSONB(), nullable=True),
        sa.Column("early_settlement_policy", postgresql.JSONB(), nullable=True),
        sa.Column("approval_threshold_amount", sa.Numeric(20, 6), nullable=True),
        sa.Column(
            "backdating_allowed", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("backdating_max_days", sa.Integer(), nullable=True),
        sa.Column("cancellation_policy", postgresql.JSONB(), nullable=True),
        sa.Column("default_policy", postgresql.JSONB(), nullable=True),
        sa.Column(
            "writeoff_requires_permission",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column("cure_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("eligibility_rules", postgresql.JSONB(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
        comment="Tenant/branch-level Installments policy configuration",
    )
    # [CORRECTED — T001] Two explicit partial unique indexes replace an
    # insufficient plain UNIQUE(company_id, branch_id): PostgreSQL treats
    # multiple NULLs in branch_id as distinct, so a plain composite unique
    # constraint would never block a second company-level default row.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_installment_configurations_branch
        ON installment_configurations (company_id, branch_id)
        WHERE branch_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_installment_configurations_company_default
        ON installment_configurations (company_id)
        WHERE branch_id IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_installment_configurations_company_default")
    op.execute("DROP INDEX IF EXISTS uq_installment_configurations_branch")
    op.drop_table("installment_configurations")

    op.drop_table("installment_sequences")

    op.drop_index(
        "ix_installments_feature_flags_flag_key", "installments_feature_flags"
    )
    op.drop_table("installments_feature_flags")
