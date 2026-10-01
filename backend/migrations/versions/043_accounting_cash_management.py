"""Cash Management — Phase 9.

Creates:
  - accounting_cash_accounts        (cash accounts / tills / petty cash boxes, GL-linked)
  - accounting_cash_transactions    (receipts/payments/transfers/adjustments)
  - accounting_petty_cash_vouchers  (petty cash disbursement vouchers)
  - accounting_cash_reconciliations (physical count vs GL reconciliation records)

Revision ID: 043
Revises: 042
Create Date: 2026-08-08
"""

from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def _soft_delete_audit_columns() -> list[sa.Column[Any]]:
    return [
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
    ]


def upgrade() -> None:
    # --- accounting_cash_accounts ---
    op.create_table(
        "accounting_cash_accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_name", sa.String(200), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("gl_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "current_balance", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column(
            "is_petty_cash", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "float_amount", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["gl_account_id"],
            ["accounting_accounts.id"],
            name="fk_accounting_cash_accounts_gl_account",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "company_id",
            "gl_account_id",
            name="uq_accounting_cash_accounts_company_gl_account",
        ),
        comment="Cash accounts (tills / petty cash boxes), one GL account each, scoped per company",
    )
    op.create_index(
        "ix_accounting_cash_accounts_company",
        "accounting_cash_accounts",
        ["company_id"],
    )

    # --- accounting_cash_transactions ---
    op.create_table(
        "accounting_cash_transactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cash_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("counterparty_type", sa.String(20), nullable=True),
        sa.Column("counterparty_id", postgresql.UUID(as_uuid=True), nullable=True),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["cash_account_id"],
            ["accounting_cash_accounts.id"],
            name="fk_accounting_cash_transactions_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"],
            ["accounting_journal_entries.id"],
            name="fk_accounting_cash_transactions_journal",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "transaction_type IN ('RECEIPT','PAYMENT','TRANSFER','ADJUSTMENT')",
            name="ck_accounting_cash_transactions_type",
        ),
        comment="Cash account transactions, scoped per company",
    )
    op.create_index(
        "ix_accounting_cash_transactions_account_date",
        "accounting_cash_transactions",
        ["company_id", "cash_account_id", "transaction_date"],
    )

    # --- accounting_petty_cash_vouchers ---
    op.create_table(
        "accounting_petty_cash_vouchers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cash_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("voucher_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("expense_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_name", sa.String(200), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("voucher_number", sa.String(30), nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["cash_account_id"],
            ["accounting_cash_accounts.id"],
            name="fk_accounting_petty_cash_vouchers_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["expense_account_id"],
            ["accounting_accounts.id"],
            name="fk_accounting_petty_cash_vouchers_expense_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"],
            ["accounting_journal_entries.id"],
            name="fk_accounting_petty_cash_vouchers_journal",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "company_id",
            "cash_account_id",
            "voucher_number",
            name="uq_accounting_petty_cash_vouchers_account_number",
        ),
        comment="Petty cash disbursement vouchers, scoped per company",
    )
    op.create_index(
        "ix_accounting_petty_cash_vouchers_account_journal",
        "accounting_petty_cash_vouchers",
        ["company_id", "cash_account_id", "journal_entry_id"],
    )

    # --- accounting_cash_reconciliations ---
    op.create_table(
        "accounting_cash_reconciliations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cash_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reconciliation_date", sa.Date(), nullable=False),
        sa.Column("physical_count_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("gl_balance_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("difference", sa.Numeric(20, 6), server_default="0", nullable=False),
        sa.Column(
            "difference_account_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), server_default="DRAFT", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["cash_account_id"],
            ["accounting_cash_accounts.id"],
            name="fk_accounting_cash_reconciliations_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["difference_account_id"],
            ["accounting_accounts.id"],
            name="fk_accounting_cash_reconciliations_difference_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"],
            ["accounting_journal_entries.id"],
            name="fk_accounting_cash_reconciliations_journal",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','COMPLETED')",
            name="ck_accounting_cash_reconciliations_status",
        ),
        comment="Cash reconciliation records (physical count vs GL), scoped per company",
    )
    op.create_index(
        "ix_accounting_cash_reconciliations_account",
        "accounting_cash_reconciliations",
        ["company_id", "cash_account_id"],
    )


def downgrade() -> None:
    op.drop_table("accounting_cash_reconciliations")
    op.drop_table("accounting_petty_cash_vouchers")
    op.drop_table("accounting_cash_transactions")
    op.drop_table("accounting_cash_accounts")
