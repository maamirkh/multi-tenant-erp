"""Installments idempotency primitive — Epic 10, Phase 0 (T006).

Creates ``installment_idempotency_keys`` — the new, module-local,
race-safe idempotency mechanism required before any high-risk financial
command (activation, collection, settlement, reversal, rescheduling,
cancellation, default, write-off) can be implemented safely (plan.md §20,
Phase 5.5). No reusable idempotency-key infrastructure exists anywhere
else in the repository (plan.md §2).

``status`` is ``'IN_PROGRESS'`` (transient — never durably observable by
another transaction under READ COMMITTED isolation) or ``'COMPLETED'``
(the only durably-persisted value) — **no ``'FAILED'`` value**: a failed
business operation rolls back its whole transaction, including this row,
so ``'FAILED'`` could never actually be committed and would be dead schema
(plan.md §20.1's explicit correction).

Plain ``Base`` with an explicit ``company_id`` column — matches the exact
field list in plan.md §20.1, no soft-delete/``created_by``/``updated_at``
columns.

Revision ID: 067
Revises: 066
Create Date: 2026-08-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "067"
down_revision = "066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "installment_idempotency_keys",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(15), nullable=False),
        sa.Column("result_payload", postgresql.JSONB(), nullable=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "operation",
            "idempotency_key",
            name="uq_installment_idempotency_company_op_key",
        ),
        sa.CheckConstraint(
            "status IN ('IN_PROGRESS', 'COMPLETED')",
            name="ck_installment_idempotency_status",
        ),
        comment=(
            "Race-safe idempotency reservations for high-risk Installments "
            "commands — INSERT...ON CONFLICT DO NOTHING targets the unique "
            "constraint above, never a bare INSERT + caught IntegrityError"
        ),
    )


def downgrade() -> None:
    op.drop_table("installment_idempotency_keys")
