"""Payment Processing — Phase 10.

Creates:
  - accounting_payments                 (customer receipts / supplier disbursements)
  - accounting_payment_allocation_lines (payment-to-invoice/bill allocation lines)
  - accounting_payment_refunds          (refunds of a payment's unallocated balance)

Revision ID: 044
Revises: 043
Create Date: 2026-08-09
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None


def _soft_delete_audit_columns() -> list[sa.Column]:
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
    # --- accounting_payments ---
    op.create_table(
        "accounting_payments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_type", sa.String(30), nullable=False),
        sa.Column("payment_method", sa.String(20), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column(
            "exchange_rate", sa.Numeric(20, 10), server_default="1", nullable=False
        ),
        sa.Column("amount_foreign", sa.Numeric(20, 6), nullable=False),
        sa.Column("amount_base", sa.Numeric(20, 6), nullable=False),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cash_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("party_type", sa.String(20), nullable=False),
        sa.Column("party_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="POSTED", nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cheque_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "discount_amount", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column("wht_amount", sa.Numeric(20, 6), server_default="0", nullable=False),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["bank_account_id"],
            ["accounting_bank_accounts.id"],
            name="fk_accounting_payments_bank_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cash_account_id"],
            ["accounting_cash_accounts.id"],
            name="fk_accounting_payments_cash_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"],
            ["accounting_journal_entries.id"],
            name="fk_accounting_payments_journal",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cheque_id"],
            ["accounting_cheques.id"],
            name="fk_accounting_payments_cheque",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "payment_type IN ('CUSTOMER_RECEIPT','SUPPLIER_DISBURSEMENT',"
            "'ADVANCE_RECEIPT','ADVANCE_PAYMENT')",
            name="ck_accounting_payments_type",
        ),
        sa.CheckConstraint(
            "payment_method IN ('CASH','BANK_TRANSFER','CHEQUE','CARD','ONLINE')",
            name="ck_accounting_payments_method",
        ),
        sa.CheckConstraint(
            "party_type IN ('CUSTOMER','SUPPLIER')",
            name="ck_accounting_payments_party_type",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','POSTED','ALLOCATED','CANCELLED')",
            name="ck_accounting_payments_status",
        ),
        comment="Customer receipts and supplier disbursements, scoped per company",
    )
    op.create_index(
        "ix_accounting_payments_company_party",
        "accounting_payments",
        ["company_id", "party_type", "party_id"],
    )
    op.create_index(
        "ix_accounting_payments_company_status",
        "accounting_payments",
        ["company_id", "status"],
    )

    # --- accounting_payment_allocation_lines ---
    op.create_table(
        "accounting_payment_allocation_lines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ar_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ap_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("allocated_amount_foreign", sa.Numeric(20, 6), nullable=False),
        sa.Column("allocated_amount_base", sa.Numeric(20, 6), nullable=False),
        sa.Column(
            "discount_amount", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column(
            "gain_loss_amount", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column(
            "gain_loss_journal_entry_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("allocated_at", sa.DateTime(timezone=True), nullable=False),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["accounting_payments.id"],
            name="fk_accounting_payment_allocation_lines_payment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ar_transaction_id"],
            ["accounting_ar_transactions.id"],
            name="fk_accounting_payment_allocation_lines_ar_transaction",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ap_transaction_id"],
            ["accounting_ap_transactions.id"],
            name="fk_accounting_payment_allocation_lines_ap_transaction",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["gain_loss_journal_entry_id"],
            ["accounting_journal_entries.id"],
            name="fk_accounting_payment_allocation_lines_gain_loss_journal",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "allocated_amount_foreign > 0",
            name="ck_accounting_payment_allocation_lines_positive",
        ),
        comment="Payment-to-invoice/bill allocation lines, scoped per company",
    )
    op.create_index(
        "ix_accounting_payment_allocation_lines_payment",
        "accounting_payment_allocation_lines",
        ["company_id", "payment_id"],
    )
    op.create_index(
        "ix_accounting_payment_allocation_lines_ar_transaction",
        "accounting_payment_allocation_lines",
        ["company_id", "ar_transaction_id"],
    )
    op.create_index(
        "ix_accounting_payment_allocation_lines_ap_transaction",
        "accounting_payment_allocation_lines",
        ["company_id", "ap_transaction_id"],
    )

    # --- accounting_payment_refunds ---
    op.create_table(
        "accounting_payment_refunds",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("refund_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cash_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["original_payment_id"],
            ["accounting_payments.id"],
            name="fk_accounting_payment_refunds_payment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"],
            ["accounting_journal_entries.id"],
            name="fk_accounting_payment_refunds_journal",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["bank_account_id"],
            ["accounting_bank_accounts.id"],
            name="fk_accounting_payment_refunds_bank_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cash_account_id"],
            ["accounting_cash_accounts.id"],
            name="fk_accounting_payment_refunds_cash_account",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("amount > 0", name="ck_accounting_payment_refunds_positive"),
        comment="Refunds of a prior payment's unallocated balance, scoped per company",
    )
    op.create_index(
        "ix_accounting_payment_refunds_payment",
        "accounting_payment_refunds",
        ["company_id", "original_payment_id"],
    )


def downgrade() -> None:
    op.drop_table("accounting_payment_refunds")
    op.drop_table("accounting_payment_allocation_lines")
    op.drop_table("accounting_payments")
