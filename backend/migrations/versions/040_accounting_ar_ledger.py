"""Accounts Receivable Ledger — Phase 6.

Creates:
  - accounting_customer_ledgers      (AR subsidiary ledger root)
  - accounting_ar_transactions       (invoice/credit-note/adjustment/write-off)
  - accounting_ar_allocations        (payment allocations, Phase 9 populates)
  - accounting_customer_credit_history (credit limit/status audit trail)

Revision ID: 040
Revises: 039
Create Date: 2026-08-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "040"
down_revision = "039"
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
    # --- accounting_customer_ledgers ---
    op.create_table(
        "accounting_customer_ledgers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "credit_limit", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column(
            "credit_status", sa.String(20), server_default="GOOD", nullable=False
        ),
        sa.Column("credit_hold_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("credit_hold_reason", sa.Text(), nullable=True),
        sa.Column("credit_hold_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "total_outstanding_base",
            sa.Numeric(20, 6),
            server_default="0",
            nullable=False,
        ),
        sa.Column("last_payment_date", sa.Date(), nullable=True),
        sa.Column("average_payment_days", sa.Numeric(10, 2), nullable=True),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "customer_id",
            name="uq_accounting_customer_ledgers_company_customer",
        ),
        sa.CheckConstraint(
            "credit_status IN ('GOOD', 'WARNING', 'EXCEEDED', 'HOLD')",
            name="ck_accounting_customer_ledgers_credit_status",
        ),
        sa.CheckConstraint(
            "credit_limit >= 0", name="ck_accounting_customer_ledgers_credit_limit"
        ),
        comment="AR subsidiary ledger root, one per customer per company",
    )
    op.create_index(
        "ix_accounting_customer_ledgers_company_customer",
        "accounting_customer_ledgers",
        ["company_id", "customer_id"],
    )

    # --- accounting_ar_transactions ---
    op.create_table(
        "accounting_ar_transactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_ledger_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column(
            "exchange_rate", sa.Numeric(20, 10), server_default="1", nullable=False
        ),
        sa.Column("amount_foreign", sa.Numeric(20, 6), nullable=False),
        sa.Column("amount_base", sa.Numeric(20, 6), nullable=False),
        sa.Column("outstanding_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("status", sa.String(20), server_default="OPEN", nullable=False),
        sa.Column("source_document_type", sa.String(50), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invoice_number", sa.String(50), nullable=True),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["customer_ledger_id"],
            ["accounting_customer_ledgers.id"],
            name="fk_accounting_ar_transactions_ledger",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"],
            ["accounting_journal_entries.id"],
            name="fk_accounting_ar_transactions_journal",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "transaction_type IN ('INVOICE','CREDIT_NOTE','DEBIT_NOTE','PAYMENT',"
            "'ADVANCE','ADJUSTMENT','WRITE_OFF')",
            name="ck_accounting_ar_transactions_type",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN','PARTIALLY_PAID','PAID','OVERDUE','DISPUTED','WRITTEN_OFF')",
            name="ck_accounting_ar_transactions_status",
        ),
        comment="AR subsidiary ledger transactions, scoped per company",
    )
    op.create_index(
        "ix_accounting_ar_transactions_company_customer_status_due",
        "accounting_ar_transactions",
        ["company_id", "customer_ledger_id", "status", "due_date"],
    )

    # --- accounting_ar_allocations ---
    op.create_table(
        "accounting_ar_allocations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ar_transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("allocated_amount_foreign", sa.Numeric(20, 6), nullable=False),
        sa.Column("allocated_amount_base", sa.Numeric(20, 6), nullable=False),
        sa.Column("allocated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "discount_amount", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["ar_transaction_id"],
            ["accounting_ar_transactions.id"],
            name="fk_accounting_ar_allocations_transaction",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "allocated_amount_foreign > 0", name="ck_accounting_ar_allocations_positive"
        ),
        comment="AR payment allocations, scoped per company (Phase 9 populates this)",
    )
    op.create_index(
        "ix_accounting_ar_allocations_payment",
        "accounting_ar_allocations",
        ["payment_id"],
    )
    op.create_index(
        "ix_accounting_ar_allocations_transaction",
        "accounting_ar_allocations",
        ["ar_transaction_id"],
    )

    # --- accounting_customer_credit_history ---
    op.create_table(
        "accounting_customer_credit_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_ledger_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("old_value", sa.String(100), nullable=True),
        sa.Column("new_value", sa.String(100), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["customer_ledger_id"],
            ["accounting_customer_ledgers.id"],
            name="fk_accounting_credit_history_ledger",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "event_type IN ('LIMIT_CHANGED','HOLD_PLACED','HOLD_RELEASED','STATUS_CHANGED')",
            name="ck_accounting_credit_history_event_type",
        ),
        comment="Customer credit limit/status change history, scoped per company",
    )
    op.create_index(
        "ix_accounting_credit_history_ledger",
        "accounting_customer_credit_history",
        ["customer_ledger_id"],
    )


def downgrade() -> None:
    op.drop_table("accounting_customer_credit_history")
    op.drop_table("accounting_ar_allocations")
    op.drop_table("accounting_ar_transactions")
    op.drop_table("accounting_customer_ledgers")
