"""Banking — Phase 8.

Creates:
  - accounting_bank_accounts               (company bank accounts, GL-linked)
  - accounting_bank_transactions            (receipts/payments/transfers/charges)
  - accounting_bank_statement_lines         (imported statement lines)
  - accounting_bank_reconciliations         (reconciliation sessions)
  - accounting_bank_reconciliation_matches  (GL-transaction <-> statement-line pairs)
  - accounting_cheques                      (issued cheque register)

Table creation order avoids a circular FK: BankTransaction/BankStatementLine's
``reconciliation_match_id`` columns are plain UUID (no FK) since
BankReconciliationMatch itself references both of those tables.

Revision ID: 042
Revises: 041
Create Date: 2026-08-08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "042"
down_revision = "041"
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
    # --- accounting_bank_accounts ---
    op.create_table(
        "accounting_bank_accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_name", sa.String(200), nullable=False),
        sa.Column("branch_name", sa.String(200), nullable=True),
        sa.Column("account_number", sa.String(50), nullable=False),
        sa.Column("iban", sa.String(50), nullable=True),
        sa.Column("swift_bic", sa.String(20), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("gl_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "opening_balance", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column("opening_balance_date", sa.Date(), nullable=True),
        sa.Column(
            "current_gl_balance", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["gl_account_id"],
            ["accounting_accounts.id"],
            name="fk_accounting_bank_accounts_gl_account",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "company_id",
            "gl_account_id",
            name="uq_accounting_bank_accounts_company_gl_account",
        ),
        comment="Company bank accounts, one GL account each, scoped per company",
    )
    op.create_index(
        "ix_accounting_bank_accounts_company",
        "accounting_bank_accounts",
        ["company_id"],
    )

    # --- accounting_bank_transactions ---
    op.create_table(
        "accounting_bank_transactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_reconciled", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "reconciliation_match_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["bank_account_id"],
            ["accounting_bank_accounts.id"],
            name="fk_accounting_bank_transactions_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"],
            ["accounting_journal_entries.id"],
            name="fk_accounting_bank_transactions_journal",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "transaction_type IN ('RECEIPT','PAYMENT','TRANSFER','BANK_CHARGE')",
            name="ck_accounting_bank_transactions_type",
        ),
        comment="Bank account transactions, scoped per company",
    )
    op.create_index(
        "ix_accounting_bank_transactions_account_reconciled",
        "accounting_bank_transactions",
        ["company_id", "bank_account_id", "is_reconciled"],
    )

    # --- accounting_bank_statement_lines ---
    op.create_table(
        "accounting_bank_statement_lines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_date", sa.Date(), nullable=False),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("transaction_type", sa.String(20), nullable=True),
        sa.Column("is_matched", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "reconciliation_match_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["bank_account_id"],
            ["accounting_bank_accounts.id"],
            name="fk_accounting_bank_statement_lines_account",
            ondelete="RESTRICT",
        ),
        comment="Imported bank statement lines, scoped per company (research.md Decision 6)",
    )
    op.create_index(
        "ix_accounting_bank_statement_lines_account_matched",
        "accounting_bank_statement_lines",
        ["company_id", "bank_account_id", "is_matched"],
    )

    # --- accounting_bank_reconciliations ---
    op.create_table(
        "accounting_bank_reconciliations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_date", sa.Date(), nullable=False),
        sa.Column("statement_closing_balance", sa.Numeric(20, 6), nullable=False),
        sa.Column("gl_balance_at_date", sa.Numeric(20, 6), nullable=True),
        sa.Column("difference", sa.Numeric(20, 6), server_default="0", nullable=False),
        sa.Column("status", sa.String(20), server_default="DRAFT", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["bank_account_id"],
            ["accounting_bank_accounts.id"],
            name="fk_accounting_bank_reconciliations_account",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','IN_PROGRESS','COMPLETED','LOCKED')",
            name="ck_accounting_bank_reconciliations_status",
        ),
        comment="Bank reconciliation sessions, scoped per company",
    )
    op.create_index(
        "ix_accounting_bank_reconciliations_account",
        "accounting_bank_reconciliations",
        ["company_id", "bank_account_id"],
    )

    # --- accounting_bank_reconciliation_matches ---
    op.create_table(
        "accounting_bank_reconciliation_matches",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reconciliation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_type", sa.String(10), nullable=False),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("matched_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["reconciliation_id"],
            ["accounting_bank_reconciliations.id"],
            name="fk_accounting_bank_reconciliation_matches_reconciliation",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["bank_transaction_id"],
            ["accounting_bank_transactions.id"],
            name="fk_accounting_bank_reconciliation_matches_transaction",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["statement_line_id"],
            ["accounting_bank_statement_lines.id"],
            name="fk_accounting_bank_reconciliation_matches_statement_line",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "match_type IN ('AUTO','MANUAL')",
            name="ck_accounting_bank_reconciliation_matches_type",
        ),
        comment="GL-transaction-to-statement-line pairs within a reconciliation session",
    )
    op.create_index(
        "ix_accounting_bank_reconciliation_matches_reconciliation",
        "accounting_bank_reconciliation_matches",
        ["reconciliation_id"],
    )

    # --- accounting_cheques ---
    op.create_table(
        "accounting_cheques",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cheque_number", sa.String(30), nullable=False),
        sa.Column("payee_name", sa.String(200), nullable=False),
        sa.Column("cheque_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("status", sa.String(20), server_default="ISSUED", nullable=False),
        sa.Column("bank_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "bank_statement_line_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["bank_account_id"],
            ["accounting_bank_accounts.id"],
            name="fk_accounting_cheques_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["bank_transaction_id"],
            ["accounting_bank_transactions.id"],
            name="fk_accounting_cheques_transaction",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["bank_statement_line_id"],
            ["accounting_bank_statement_lines.id"],
            name="fk_accounting_cheques_statement_line",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "company_id",
            "bank_account_id",
            "cheque_number",
            name="uq_accounting_cheques_account_number",
        ),
        sa.CheckConstraint(
            "status IN ('ISSUED','PRESENTED','CLEARED','CANCELLED','STALE')",
            name="ck_accounting_cheques_status",
        ),
        comment="Issued cheque register, scoped per company",
    )
    op.create_index(
        "ix_accounting_cheques_company_status",
        "accounting_cheques",
        ["company_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("accounting_cheques")
    op.drop_table("accounting_bank_reconciliation_matches")
    op.drop_table("accounting_bank_reconciliations")
    op.drop_table("accounting_bank_statement_lines")
    op.drop_table("accounting_bank_transactions")
    op.drop_table("accounting_bank_accounts")
