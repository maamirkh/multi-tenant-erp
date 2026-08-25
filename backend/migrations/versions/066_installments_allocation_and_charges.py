"""Installments allocation references & late charges — Epic 10, Phase 0 (T005).

Creates ``installment_allocation_references`` (append-only, plain ``Base``
with explicit ``company_id`` — explains which Accounting payment/
allocation satisfied which schedule line, spec.md §13.2/BR-INST-007; never
updated or deleted, a reversal always inserts a new row) and
``installment_late_charges`` (TenantBaseModel-shaped — waiver is a
controlled, distinct-permission mutation of an otherwise stable row, not
an append-only history record).

No FK on ``accounting_payment_id``, ``accounting_payment_allocation_line_id``,
``accounting_journal_entry_id``, or ``accounting_ar_transaction_id`` —
cross-module references follow the established ``source_document_id``
convention (plan.md §7.2). ``accounting_ar_transaction_id`` links a late
charge back to the ``DEBIT_NOTE``-type ``ARTransaction`` Accounting creates
for it, so the charge remains ordinarily payment-allocatable and
reversible (plan.md §12.1).

Revision ID: 066
Revises: 065
Create Date: 2026-08-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "066"
down_revision = "065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- installment_allocation_references (append-only, plain Base) ---
    op.create_table(
        "installment_allocation_references",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "accounting_payment_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "accounting_payment_allocation_line_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("allocated_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("allocation_order", sa.Integer(), nullable=False),
        sa.Column("is_reversal", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "reverses_allocation_reference_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "allocated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["installment_contracts.id"],
            name="fk_installment_allocation_references_contract_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_line_id"],
            ["installment_schedule_lines.id"],
            name="fk_installment_allocation_references_schedule_line_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reverses_allocation_reference_id"],
            ["installment_allocation_references.id"],
            name="fk_installment_allocation_references_reverses_id",
            ondelete="RESTRICT",
        ),
        comment=(
            "Append-only explanation of which Accounting payment/allocation "
            "satisfied which schedule line — never updated or deleted"
        ),
    )

    # --- installment_late_charges ---
    op.create_table(
        "installment_late_charges",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("charge_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column(
            "charged_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("overdue_occurrence_date", sa.Date(), nullable=False),
        sa.Column(
            "accounting_journal_entry_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "accounting_ar_transaction_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("waived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("waived_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("waived_reason", sa.Text(), nullable=True),
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
            ["contract_id"],
            ["installment_contracts.id"],
            name="fk_installment_late_charges_contract_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_line_id"],
            ["installment_schedule_lines.id"],
            name="fk_installment_late_charges_schedule_line_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "schedule_line_id",
            "overdue_occurrence_date",
            name="uq_installment_late_charges_line_occurrence",
        ),
        comment=(
            "One occurrence of a policy-driven late charge — never charged "
            "twice for the same (schedule_line_id, overdue_occurrence_date)"
        ),
    )


def downgrade() -> None:
    op.drop_table("installment_late_charges")
    op.drop_table("installment_allocation_references")
