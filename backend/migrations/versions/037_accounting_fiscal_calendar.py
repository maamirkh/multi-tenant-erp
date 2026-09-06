"""Accounting Fiscal Calendar — Phase 3.

Creates:
  - accounting_fiscal_years
  - accounting_fiscal_periods (self-scoped by fiscal_year_id)
  - accounting_opening_balances (FK to accounting_accounts, Phase 2)

Revision ID: 037
Revises: 036
Create Date: 2026-08-06
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- accounting_fiscal_years ---
    op.create_table(
        "accounting_fiscal_years",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fiscal_year_name", sa.String(50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default="SETUP", nullable=False),
        sa.Column("base_currency_code", sa.String(3), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default="false", nullable=False),
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
            "fiscal_year_name",
            name="uq_accounting_fiscal_years_company_name",
        ),
        sa.CheckConstraint(
            "status IN ('SETUP', 'OPEN', 'CLOSED')",
            name="ck_accounting_fiscal_years_status",
        ),
        sa.CheckConstraint(
            "end_date > start_date", name="ck_accounting_fiscal_years_date_range"
        ),
        comment="Fiscal year definitions, scoped per company",
    )
    op.create_index(
        "ix_accounting_fiscal_years_company_current",
        "accounting_fiscal_years",
        ["company_id", "is_current"],
    )

    # --- accounting_fiscal_periods ---
    op.create_table(
        "accounting_fiscal_periods",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fiscal_year_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_number", sa.Integer(), nullable=False),
        sa.Column("period_name", sa.String(50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default="OPEN", nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lock_reason", sa.Text(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["fiscal_year_id"],
            ["accounting_fiscal_years.id"],
            name="fk_accounting_fiscal_periods_year",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "fiscal_year_id",
            "period_number",
            name="uq_accounting_fiscal_periods_year_number",
        ),
        sa.CheckConstraint(
            "period_number >= 1 AND period_number <= 13",
            name="ck_accounting_fiscal_periods_number",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'LOCKED', 'CLOSED')",
            name="ck_accounting_fiscal_periods_status",
        ),
        sa.CheckConstraint(
            "end_date > start_date", name="ck_accounting_fiscal_periods_date_range"
        ),
        comment="Accounting periods within a fiscal year, scoped per company",
    )
    op.create_index(
        "ix_accounting_fiscal_periods_company_dates",
        "accounting_fiscal_periods",
        ["company_id", "start_date", "end_date"],
    )
    op.create_index(
        "ix_accounting_fiscal_periods_year",
        "accounting_fiscal_periods",
        ["fiscal_year_id"],
    )
    op.create_index(
        "ix_accounting_fiscal_periods_company_status",
        "accounting_fiscal_periods",
        ["company_id", "status"],
    )

    # --- accounting_opening_balances ---
    op.create_table(
        "accounting_opening_balances",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fiscal_year_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "debit_amount", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column(
            "credit_amount", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column("currency_code", sa.String(3), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["fiscal_year_id"],
            ["accounting_fiscal_years.id"],
            name="fk_accounting_opening_balances_year",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounting_accounts.id"],
            name="fk_accounting_opening_balances_account",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "fiscal_year_id",
            "account_id",
            name="uq_accounting_opening_balances_year_account",
        ),
        sa.CheckConstraint(
            "debit_amount >= 0 AND credit_amount >= 0",
            name="ck_accounting_opening_balances_non_negative",
        ),
        sa.CheckConstraint(
            "debit_amount = 0 OR credit_amount = 0",
            name="ck_accounting_opening_balances_one_sided",
        ),
        comment="Opening balances per account for a fiscal year, scoped per company",
    )
    op.create_index(
        "ix_accounting_opening_balances_year",
        "accounting_opening_balances",
        ["fiscal_year_id"],
    )


def downgrade() -> None:
    op.drop_table("accounting_opening_balances")
    op.drop_table("accounting_fiscal_periods")
    op.drop_table("accounting_fiscal_years")
