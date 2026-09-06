"""Installments audit log — Epic 10, Phase 0 (T007).

Creates ``installment_audit_log`` — plain ``Base`` with an explicit
``company_id`` column, matching ``AccountingAuditLog``'s richer shape over
CRM's minimal one, since Installments actions are financially sensitive
and frequently carry a mandatory reason (plan.md §17). Append-only: no
``updated_at``, ``is_deleted``, ``deleted_at``, or ``created_by`` column —
``InstallmentAuditService.record()`` only ever ``db.add()``s a new row,
never updates one.

``action`` enumerates every mutation named in spec.md §21 (FR-INST-340):
CREATED, SUBMITTED, APPROVED, REJECTED, ACTIVATED, COLLECTED, ALLOCATED,
COLLECTION_REVERSED, LATE_CHARGE_APPLIED, LATE_CHARGE_WAIVED, RESCHEDULED,
SETTLEMENT_QUOTED, SETTLED, CANCELLED, DEFAULTED, CURED, WRITTEN_OFF,
CONFIGURATION_CHANGED, TEMPLATE_CHANGED — not DB-enforced via CHECK (the
set is expected to grow across later phases without a migration each
time, matching ``crm_audit_log``'s own unconstrained ``action`` column).

Revision ID: 068
Revises: 067
Create Date: 2026-08-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "068"
down_revision = "067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "installment_audit_log",
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
        comment=(
            "Append-only Installments audit trail — fail-closed: record() "
            "only flushes, callers commit business mutation + audit together"
        ),
    )


def downgrade() -> None:
    op.drop_table("installment_audit_log")
