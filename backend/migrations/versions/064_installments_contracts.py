"""Installments contracts — Epic 10, Phase 0 (T003).

Creates ``installment_contracts``, the Installments aggregate root
(spec.md §9.5, §11, ADR-INST-02). No FK on ``customer_id``/
``sales_invoice_id`` — cross-module references follow the established
``party_id``/``source_document_id`` convention (no FK across module
boundaries, plan.md §7.2).

**Deferred FK** (mirrors migration 055's ``crm_leads``/``crm_opportunities``
two-table-cycle technique): ``active_schedule_version_id`` references
``installment_schedule_versions.id``, but that table does not exist until
migration 065 (which itself has a FK back to this table's ``id`` via
``schedule_versions.contract_id``). The column is created here WITHOUT its
FK constraint; 065 adds the FK via ``op.create_foreign_key()`` once
``installment_schedule_versions`` exists.

**Partial unique index, not a plain UNIQUE** (BR-INST-042/ADR-INST-03): at
most one *non-terminal* contract may exist per originating obligation —
``CANCELLED``/``COMPLETED``/``WRITTEN_OFF`` contracts must NOT block a new
contract against the same invoice (e.g. a repeat installment sale after an
earlier one completed). Mirrors the platform's own
``uq_subscriptions_company_active`` precedent (plan.md §2).

Revision ID: 064
Revises: 063
Create Date: 2026-08-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "064"
down_revision = "063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "installment_contracts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_number", sa.String(30), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sales_invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("contract_date", sa.Date(), nullable=False),
        sa.Column("principal_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("down_payment_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column(
            "markup_amount", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column("contractual_total", sa.Numeric(20, 6), nullable=False),
        sa.Column("installment_count", sa.Integer(), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("first_due_date", sa.Date(), nullable=False),
        sa.Column("maturity_date", sa.Date(), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'DRAFT'"),
            nullable=False,
        ),
        sa.Column("terms_snapshot", postgresql.JSONB(), nullable=False),
        # FK added in migration 065 (deferred — see module docstring).
        sa.Column(
            "active_schedule_version_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("submitted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("defaulted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("written_off_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
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
            ["plan_template_id"],
            ["installment_plan_templates.id"],
            name="fk_installment_contracts_plan_template_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "company_id",
            "contract_number",
            name="uq_installment_contracts_company_number",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'ACTIVE', "
            "'DEFAULTED', 'COMPLETED', 'CANCELLED', 'WRITTEN_OFF')",
            name="ck_installment_contracts_status",
        ),
        sa.CheckConstraint(
            "principal_amount >= 0 AND contractual_total >= 0 "
            "AND installment_count > 0",
            name="ck_installment_contracts_positive_amounts",
        ),
        comment="Installments aggregate root — an installment sale agreement",
    )
    # Base tenant-scoping index (explicit — plan.md §33; contract lookups by
    # company alone, e.g. "all contracts for this tenant," are frequent
    # enough to warrant it beyond the composite indexes added in 069).
    op.create_index(
        "ix_installment_contracts_company_id",
        "installment_contracts",
        ["company_id"],
    )
    # BR-INST-042/ADR-INST-03: at most one non-terminal contract per
    # originating obligation.
    op.execute("""
        CREATE UNIQUE INDEX uq_installment_contracts_one_nonterminal_per_obligation
        ON installment_contracts (company_id, sales_invoice_id)
        WHERE status NOT IN ('CANCELLED', 'COMPLETED', 'WRITTEN_OFF')
        """)


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS uq_installment_contracts_one_nonterminal_per_obligation"
    )
    op.drop_index("ix_installment_contracts_company_id", "installment_contracts")
    op.drop_table("installment_contracts")
