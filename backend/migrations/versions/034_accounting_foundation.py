"""Accounting foundation tables — Phase 1.

Creates all Phase 1 foundation tables for the Accounting module:
  - accounting_configurations
  - accounting_sequences
  - accounting_feature_flags

Revision ID: 034
Revises: 033_sales_index_audit
Create Date: 2026-08-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "034"
down_revision = "033_sales_index_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- accounting_configurations ---
    op.create_table(
        "accounting_configurations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "base_currency_code", sa.String(3), server_default="USD", nullable=False
        ),
        sa.Column("journal_approval_threshold", sa.Numeric(20, 6), nullable=True),
        sa.Column("payment_approval_threshold", sa.Numeric(20, 6), nullable=True),
        sa.Column(
            "credit_warning_threshold_pct",
            sa.Numeric(5, 2),
            server_default="80.00",
            nullable=False,
        ),
        sa.Column(
            "cheque_stale_days", sa.Integer(), server_default="180", nullable=False
        ),
        sa.Column(
            "default_ar_account_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "default_ap_account_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "default_retained_earnings_account_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "default_exchange_gain_account_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "default_exchange_loss_account_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "default_bad_debt_account_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "default_revenue_account_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "default_expense_account_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "default_tax_liability_account_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "default_input_tax_account_id", postgresql.UUID(as_uuid=True), nullable=True
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
        sa.UniqueConstraint("company_id", name="uq_accounting_configuration_company"),
        sa.CheckConstraint(
            "credit_warning_threshold_pct >= 0 AND credit_warning_threshold_pct <= 100",
            name="ck_accounting_config_credit_threshold",
        ),
        sa.CheckConstraint(
            "cheque_stale_days >= 1", name="ck_accounting_config_cheque_stale_days"
        ),
        comment="Company-level accounting configuration — one row per company",
    )

    # --- accounting_sequences ---
    op.create_table(
        "accounting_sequences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_type", sa.String(20), nullable=False),
        sa.Column("prefix", sa.String(10), server_default="'JE'", nullable=False),
        sa.Column("current_value", sa.Integer(), server_default="0", nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column(
            "format_pattern",
            sa.String(50),
            server_default="'{PREFIX}-{YEAR}-{SEQ:06d}'",
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
            "sequence_type",
            "year",
            name="uq_accounting_seq_company_type_year",
        ),
        sa.CheckConstraint(
            "sequence_type IN ('JOURNAL')", name="ck_accounting_seq_type"
        ),
        sa.CheckConstraint(
            "current_value >= 0", name="ck_accounting_seq_current_value"
        ),
        comment="Gap-free auto-numbering sequences for accounting documents, "
        "locked with SELECT FOR UPDATE",
    )

    # --- accounting_feature_flags ---
    op.create_table(
        "accounting_feature_flags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("flag_key", sa.String(120), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
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
            "company_id", "flag_key", name="uq_accounting_ff_company_key"
        ),
        comment="Per-company feature flag overrides for the Accounting module",
    )
    op.create_index(
        "ix_accounting_feature_flags_flag_key",
        "accounting_feature_flags",
        ["flag_key"],
    )


def downgrade() -> None:
    op.drop_table("accounting_feature_flags")
    op.drop_table("accounting_sequences")
    op.drop_table("accounting_configurations")
