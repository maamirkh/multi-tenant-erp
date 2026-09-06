"""GL report performance indexes — Phase 13.

Adds indexes needed by ``FinancialStatementService``/``ReportService``'s
aggregation queries (Trial Balance, Balance Sheet, P&L, Cash Flow, GL
detail report) to scale to hundreds of thousands of GL lines (tasks.md
T270's "500K GL entries -> trial balance < 10s; financial statements <
15s" acceptance criterion):

  - ``accounting_journal_lines.account_id`` had NO index at all — every
    report query that joins ``JournalLine`` to ``Account`` (balance sheet,
    P&L, cost-center P&L, working-capital, GL cursor report) paid a full
    scan for that join. Measured impact: Balance Sheet over 500K lines
    took 81.9s without this index (target: 15s).
  - ``accounting_journal_entries(company_id, posting_date)`` — every
    date-range filter (the majority of report queries) scanned the full
    per-company row set without this composite index.

Purely additive — no data changes, no risk to existing Epics.

Phase 18 (T315) fix: this migration originally also re-created
``ix_accounting_journal_lines_cost_center`` — but migration 038 already
creates that exact index (same name, same column) when
``accounting_journal_lines`` is first created. On the ALREADY-migrated
persistent dev database this went unnoticed (each migration was applied
incrementally as its own phase landed, and the duplicate ``CREATE INDEX``
was never re-run against a database that already had it — Alembic only
runs the delta from ``alembic_version``'s current revision forward). It
was only caught running the full 001->050 chain against a genuinely fresh,
empty database (Docker/Postgres full validation, T315) — this is EXACTLY
the class of bug that validation exists to catch. Fixed by dropping the
duplicate create/drop pair; the other two (genuinely new) indexes are
unchanged.

Spec ref: specs/008-accounting-finance/tasks.md T270, T315
Plan ref: specs/008-accounting-finance/plan.md Phase 13 Exit Criteria
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "048"
down_revision = "047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_accounting_journal_lines_account",
        "accounting_journal_lines",
        ["account_id"],
    )
    op.create_index(
        "ix_accounting_journal_entries_company_posting_date",
        "accounting_journal_entries",
        ["company_id", "posting_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_accounting_journal_entries_company_posting_date",
        table_name="accounting_journal_entries",
    )
    op.drop_index(
        "ix_accounting_journal_lines_account", table_name="accounting_journal_lines"
    )
