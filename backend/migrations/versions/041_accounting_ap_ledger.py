"""Accounts Payable Ledger — Phase 7.

Creates:
  - accounting_supplier_ledgers                (AP subsidiary ledger root)
  - accounting_ap_transactions                 (bill/credit-note/adjustment)
  - accounting_ap_allocations                  (payment allocations, Phase 9 populates)
  - accounting_supplier_reconciliations         (statement reconciliation sessions)
  - accounting_supplier_reconciliation_items    (matched/unmatched lines)

Revision ID: 041
Revises: 040
Create Date: 2026-08-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "041"
down_revision = "040"
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
    # --- accounting_supplier_ledgers ---
    op.create_table(
        "accounting_supplier_ledgers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "total_outstanding_base",
            sa.Numeric(20, 6),
            server_default="0",
            nullable=False,
        ),
        sa.Column("last_payment_date", sa.Date(), nullable=True),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "supplier_id",
            name="uq_accounting_supplier_ledgers_company_supplier",
        ),
        comment="AP subsidiary ledger root, one per supplier per company",
    )
    op.create_index(
        "ix_accounting_supplier_ledgers_company_supplier",
        "accounting_supplier_ledgers",
        ["company_id", "supplier_id"],
    )

    # --- accounting_ap_transactions ---
    op.create_table(
        "accounting_ap_transactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_ledger_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column("bill_number", sa.String(50), nullable=True),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["supplier_ledger_id"],
            ["accounting_supplier_ledgers.id"],
            name="fk_accounting_ap_transactions_ledger",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"],
            ["accounting_journal_entries.id"],
            name="fk_accounting_ap_transactions_journal",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "transaction_type IN ('BILL','CREDIT_NOTE','DEBIT_NOTE','PAYMENT',"
            "'ADVANCE','ADJUSTMENT')",
            name="ck_accounting_ap_transactions_type",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN','PARTIALLY_PAID','PAID','OVERDUE','DISPUTED')",
            name="ck_accounting_ap_transactions_status",
        ),
        comment="AP subsidiary ledger transactions, scoped per company",
    )
    op.create_index(
        "ix_accounting_ap_transactions_company_supplier_status_due",
        "accounting_ap_transactions",
        ["company_id", "supplier_ledger_id", "status", "due_date"],
    )

    # --- accounting_ap_allocations ---
    op.create_table(
        "accounting_ap_allocations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ap_transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
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
            ["ap_transaction_id"],
            ["accounting_ap_transactions.id"],
            name="fk_accounting_ap_allocations_transaction",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "allocated_amount_foreign > 0", name="ck_accounting_ap_allocations_positive"
        ),
        comment="AP payment allocations, scoped per company (Phase 9 populates this)",
    )
    op.create_index(
        "ix_accounting_ap_allocations_payment",
        "accounting_ap_allocations",
        ["payment_id"],
    )
    op.create_index(
        "ix_accounting_ap_allocations_transaction",
        "accounting_ap_allocations",
        ["ap_transaction_id"],
    )

    # --- accounting_supplier_reconciliations ---
    op.create_table(
        "accounting_supplier_reconciliations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_date", sa.Date(), nullable=False),
        sa.Column("statement_total", sa.Numeric(20, 6), nullable=False),
        sa.Column("status", sa.String(20), server_default="DRAFT", nullable=False),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('DRAFT','IN_PROGRESS','COMPLETED')",
            name="ck_accounting_supplier_reconciliations_status",
        ),
        comment="Supplier statement reconciliation sessions, scoped per company",
    )
    op.create_index(
        "ix_accounting_supplier_reconciliations_supplier",
        "accounting_supplier_reconciliations",
        ["company_id", "supplier_id"],
    )

    # --- accounting_supplier_reconciliation_items ---
    op.create_table(
        "accounting_supplier_reconciliation_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reconciliation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ap_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("statement_line_reference", sa.String(100), nullable=True),
        sa.Column("statement_amount", sa.Numeric(20, 6), nullable=True),
        sa.Column("gl_amount", sa.Numeric(20, 6), nullable=True),
        sa.Column(
            "match_status",
            sa.String(20),
            server_default="UNMATCHED_STATEMENT",
            nullable=False,
        ),
        sa.Column("difference", sa.Numeric(20, 6), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["reconciliation_id"],
            ["accounting_supplier_reconciliations.id"],
            name="fk_accounting_reconciliation_items_reconciliation",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ap_transaction_id"],
            ["accounting_ap_transactions.id"],
            name="fk_accounting_reconciliation_items_transaction",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "match_status IN ('MATCHED','UNMATCHED_GL','UNMATCHED_STATEMENT','DISPUTED')",
            name="ck_accounting_reconciliation_items_match_status",
        ),
        comment="Individual matched/unmatched lines within a supplier reconciliation session",
    )
    op.create_index(
        "ix_accounting_reconciliation_items_reconciliation",
        "accounting_supplier_reconciliation_items",
        ["reconciliation_id"],
    )


def downgrade() -> None:
    op.drop_table("accounting_supplier_reconciliation_items")
    op.drop_table("accounting_supplier_reconciliations")
    op.drop_table("accounting_ap_allocations")
    op.drop_table("accounting_ap_transactions")
    op.drop_table("accounting_supplier_ledgers")
