"""Installments performance indexes — Epic 10, Phase 0 (T008).

Creates every composite/covering index from plan.md §33 not already
created inline with its owning table in migrations 062-068
(``ix_installment_contracts_company_id`` was already created inline in
064, so it is intentionally absent here).

No N+1 patterns: schedule-line + allocation-reference reads for a
contract detail page are two batch queries, never per-line queries
(Constitution §25).

Revision ID: 069
Revises: 068
Create Date: 2026-08-25
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "069"
down_revision = "068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_installment_contracts_company_customer",
        "installment_contracts",
        ["company_id", "customer_id"],
    )
    op.create_index(
        "ix_installment_contracts_company_invoice",
        "installment_contracts",
        ["company_id", "sales_invoice_id"],
    )
    op.create_index(
        "ix_installment_contracts_company_status",
        "installment_contracts",
        ["company_id", "status"],
    )
    op.create_index(
        "ix_installment_contracts_company_branch",
        "installment_contracts",
        ["company_id", "branch_id"],
    )
    op.create_index(
        "ix_installment_schedule_lines_version_due_date",
        "installment_schedule_lines",
        ["schedule_version_id", "due_date"],
    )
    op.create_index(
        "ix_installment_schedule_lines_due_date",
        "installment_schedule_lines",
        ["due_date"],
    )
    op.create_index(
        "ix_installment_allocation_references_line",
        "installment_allocation_references",
        ["schedule_line_id"],
    )
    op.create_index(
        "ix_installment_allocation_references_payment",
        "installment_allocation_references",
        ["accounting_payment_id"],
    )
    op.create_index(
        "ix_installment_audit_log_entity",
        "installment_audit_log",
        ["company_id", "entity_type", "entity_id"],
    )
    op.create_index(
        "ix_installment_audit_log_time",
        "installment_audit_log",
        ["company_id", "occurred_at"],
    )
    op.create_index(
        "ix_installment_plan_templates_active",
        "installment_plan_templates",
        ["company_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_installment_plan_templates_active", "installment_plan_templates")
    op.drop_index("ix_installment_audit_log_time", "installment_audit_log")
    op.drop_index("ix_installment_audit_log_entity", "installment_audit_log")
    op.drop_index(
        "ix_installment_allocation_references_payment",
        "installment_allocation_references",
    )
    op.drop_index(
        "ix_installment_allocation_references_line",
        "installment_allocation_references",
    )
    op.drop_index(
        "ix_installment_schedule_lines_due_date", "installment_schedule_lines"
    )
    op.drop_index(
        "ix_installment_schedule_lines_version_due_date",
        "installment_schedule_lines",
    )
    op.drop_index("ix_installment_contracts_company_branch", "installment_contracts")
    op.drop_index("ix_installment_contracts_company_status", "installment_contracts")
    op.drop_index("ix_installment_contracts_company_invoice", "installment_contracts")
    op.drop_index("ix_installment_contracts_company_customer", "installment_contracts")
