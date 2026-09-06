"""Accounting General Ledger — Phase 4 (CRITICAL).

Creates:
  - accounting_journal_entries (aggregate root)
  - accounting_journal_lines (append-only — DB trigger blocks UPDATE/DELETE)
  - accounting_journal_approvals
  - accounting_audit_log (append-only, immutable)

Covering indexes on ``accounting_journal_lines``:
  (company_id, journal_entry_id, account_id) and
  (company_id, account_id) — used by trial-balance/GL-detail queries.
``accounting_journal_entries`` gets (company_id, fiscal_period_id) and
(company_id, posting_date) for the same reason.

Immutability (research.md Decision 1, Decision 4; tasks.md T095): a
BEFORE UPDATE OR DELETE trigger on ``accounting_journal_lines`` raises an
exception unconditionally — no row, once inserted, is ever updated or
deleted, regardless of the parent entry's status (see models/gl.py
docstring for why this phase has no draft-line-editing capability).

Revision ID: 038
Revises: 037
Create Date: 2026-08-06
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None

_TRIGGER_FUNCTION_NAME = "accounting_journal_lines_block_mutation"
_TRIGGER_NAME = "trg_accounting_journal_lines_immutable"


def upgrade() -> None:
    # --- accounting_journal_entries ---
    op.create_table(
        "accounting_journal_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("journal_number", sa.String(30), nullable=True),
        sa.Column("journal_type", sa.String(30), nullable=False),
        sa.Column("posting_source", sa.String(20), nullable=False),
        sa.Column("posting_date", sa.Date(), nullable=False),
        sa.Column("fiscal_period_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fiscal_year_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="DRAFT", nullable=False),
        sa.Column(
            "reversal_of_journal_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("is_reversal", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_document_type", sa.String(50), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column(
            "exchange_rate", sa.Numeric(20, 10), server_default="1", nullable=False
        ),
        sa.Column(
            "total_debit_base", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column(
            "total_credit_base", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column("is_balanced", sa.Boolean(), nullable=True),
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
            ["fiscal_period_id"],
            ["accounting_fiscal_periods.id"],
            name="fk_accounting_journals_period",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["fiscal_year_id"],
            ["accounting_fiscal_years.id"],
            name="fk_accounting_journals_year",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reversal_of_journal_id"],
            ["accounting_journal_entries.id"],
            name="fk_accounting_journals_reversal_of",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "company_id", "journal_number", name="uq_accounting_journals_company_number"
        ),
        sa.CheckConstraint(
            "journal_type IN ('STANDARD','ADJUSTING','REVERSING',"
            "'RECURRING_INSTANCE','OPENING_BALANCE','CLOSING','AUTOMATED')",
            name="ck_accounting_journals_type",
        ),
        sa.CheckConstraint(
            "posting_source IN ('MANUAL','SALES','PURCHASE','INVENTORY','BANK',"
            "'CASH','PAYMENT','RECURRING','SYSTEM')",
            name="ck_accounting_journals_source",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','POSTED','REJECTED','REVERSED')",
            name="ck_accounting_journals_status",
        ),
        sa.CheckConstraint(
            "is_balanced IS NULL OR is_balanced = true",
            name="ck_accounting_journals_is_balanced",
        ),
        comment="General Ledger journal entries (aggregate root), scoped per company",
    )
    op.create_index(
        "ix_accounting_journals_company_period",
        "accounting_journal_entries",
        ["company_id", "fiscal_period_id"],
    )
    op.create_index(
        "ix_accounting_journals_company_date",
        "accounting_journal_entries",
        ["company_id", "posting_date"],
    )
    op.create_index(
        "ix_accounting_journals_company_status",
        "accounting_journal_entries",
        ["company_id", "status"],
    )
    op.create_index(
        "ix_accounting_journals_source_doc",
        "accounting_journal_entries",
        ["company_id", "source_document_type", "source_document_id"],
    )

    # --- accounting_journal_lines (append-only) ---
    op.create_table(
        "accounting_journal_lines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_code", sa.String(20), nullable=False),
        sa.Column(
            "debit_amount", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column(
            "credit_amount", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column(
            "debit_amount_base", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column(
            "credit_amount_base", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column(
            "exchange_rate", sa.Numeric(20, 10), server_default="1", nullable=False
        ),
        sa.Column("cost_center_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"],
            ["accounting_journal_entries.id"],
            name="fk_accounting_journal_lines_entry",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounting_accounts.id"],
            name="fk_accounting_journal_lines_account",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "journal_entry_id",
            "line_number",
            name="uq_accounting_journal_lines_entry_number",
        ),
        sa.CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR "
            "(credit_amount > 0 AND debit_amount = 0)",
            name="ck_accounting_journal_lines_one_sided",
        ),
        sa.CheckConstraint(
            "debit_amount >= 0 AND credit_amount >= 0",
            name="ck_accounting_journal_lines_non_negative",
        ),
        comment="Append-only General Ledger lines — no UPDATE/DELETE, ever",
    )
    op.create_index(
        "ix_accounting_journal_lines_company_entry_account",
        "accounting_journal_lines",
        ["company_id", "journal_entry_id", "account_id"],
    )
    op.create_index(
        "ix_accounting_journal_lines_company_account",
        "accounting_journal_lines",
        ["company_id", "account_id"],
    )
    op.create_index(
        "ix_accounting_journal_lines_cost_center",
        "accounting_journal_lines",
        ["cost_center_id"],
    )

    # --- accounting_journal_approvals ---
    op.create_table(
        "accounting_journal_approvals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approver_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approval_status", sa.String(20), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
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
            ["journal_entry_id"],
            ["accounting_journal_entries.id"],
            name="fk_accounting_journal_approvals_entry",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "approval_status IN ('APPROVED', 'REJECTED')",
            name="ck_accounting_journal_approvals_status",
        ),
        comment="Approval/rejection decisions on journal entries, scoped per company",
    )
    op.create_index(
        "ix_accounting_journal_approvals_entry",
        "accounting_journal_approvals",
        ["journal_entry_id"],
    )

    # --- accounting_audit_log (append-only, immutable) ---
    op.create_table(
        "accounting_audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("before_state", postgresql.JSONB(), nullable=True),
        sa.Column("after_state", postgresql.JSONB(), nullable=True),
        sa.Column("session_context", postgresql.JSONB(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment="Immutable audit trail for accounting financial state changes",
    )
    op.create_index(
        "ix_accounting_audit_log_company_entity",
        "accounting_audit_log",
        ["company_id", "entity_type", "entity_id"],
    )
    op.create_index(
        "ix_accounting_audit_log_occurred_at",
        "accounting_audit_log",
        ["occurred_at"],
    )

    # --- Immutability trigger on accounting_journal_lines ---
    op.execute(f"""
        CREATE OR REPLACE FUNCTION {_TRIGGER_FUNCTION_NAME}()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'accounting_journal_lines is append-only: % is not permitted',
                TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """)
    op.execute(f"""
        CREATE TRIGGER {_TRIGGER_NAME}
        BEFORE UPDATE OR DELETE ON accounting_journal_lines
        FOR EACH ROW EXECUTE FUNCTION {_TRIGGER_FUNCTION_NAME}();
        """)


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {_TRIGGER_NAME} ON accounting_journal_lines;")
    op.execute(f"DROP FUNCTION IF EXISTS {_TRIGGER_FUNCTION_NAME}();")
    op.drop_table("accounting_audit_log")
    op.drop_table("accounting_journal_approvals")
    op.drop_table("accounting_journal_lines")
    op.drop_table("accounting_journal_entries")
