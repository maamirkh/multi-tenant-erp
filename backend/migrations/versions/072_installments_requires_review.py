"""Installments requires_review flag — Epic 10, Phase 15 (T260 gap-closure).

Adds ``installment_contracts.requires_review`` (plan.md §13, line 709):
a non-terminal flag set by the new Sales-invoice-correction event
handler (``modules/installments/handlers/sales_integration_handlers.py``)
when the originating Sales invoice is corrected post-activation (credit
note issued / invoice cancelled) — Scenario H (spec.md §16.1,
FR-INST-241). Never auto-cancels or auto-adjusts the contract; an
authorized human action resolves it.

This column was specified in plan.md §13 from the start of Epic 10 but
no task in tasks.md's Phases 0-14 was ever allocated to add it — only
Phase 15's T260 (a test task) referenced the resulting behavior,
discovered when implementing T260 itself. Closing it here rather than
leaving T260 permanently un-implementable.

Revision ID: 072
Revises: 071
Create Date: 2026-09-05
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "072"
down_revision = "071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "installment_contracts",
        sa.Column(
            "requires_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("installment_contracts", "requires_review")
