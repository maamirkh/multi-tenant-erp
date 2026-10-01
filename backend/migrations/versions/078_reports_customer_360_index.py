"""Customer 360 index — Epic 11, Phase 10 (T268, Branch B).

Adds ``ix_installment_schedule_lines_company_id``. ``EXPLAIN (ANALYZE,
BUFFERS)`` of Customer 360's four section queries at representative scale
(``tests/performance/reports/test_customer_360_explain.py``: 5 tenants,
10K contracts / 30K schedule lines each) showed every other section read
served by an existing index, but Installments' tenant-scoped schedule-line
read (``installment_schedule_lines.company_id = :c`` joined to contracts)
sequential-scanning **every tenant's** lines — 120,000 of 150,000 rows
discarded, 199 ms — because the table had no ``company_id`` index. Its
cost therefore grew with the whole platform's size, not the tenant's.
This is exactly the one index that evidence justifies.

**Renumbered**: tasks.md T268 names this ``077`` / ``down_revision="076"``,
but ``077`` is the reports audit log (Phase 6, T179) — shifted to ``078``,
the same renumbering precedent as T040/T179.

Revision ID: 078
Revises: 077
Create Date: 2026-09-28
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "078"
down_revision = "077"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_installment_schedule_lines_company_id",
        "installment_schedule_lines",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_installment_schedule_lines_company_id", "installment_schedule_lines"
    )
