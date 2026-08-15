"""Accounting Recurring Journals — Phase 5.

Creates:
  - accounting_recurring_templates
  - accounting_recurring_template_lines
  - accounting_recurring_instances (unique on (template_id, execution_date)
    — the DB-level idempotency backstop, tasks.md T119)

Revision ID: 039
Revises: 038
Create Date: 2026-08-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- accounting_recurring_templates ---
    op.create_table(
        "accounting_recurring_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_name", sa.String(200), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("next_run_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("auto_post", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "approval_required", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "frequency IN ('DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'ANNUALLY')",
            name="ck_accounting_recurring_templates_frequency",
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date > start_date",
            name="ck_accounting_recurring_templates_date_range",
        ),
        comment="Recurring journal templates, scoped per company",
    )
    op.create_index(
        "ix_accounting_recurring_templates_active_due",
        "accounting_recurring_templates",
        ["is_active", "next_run_date"],
    )
    op.create_index(
        "ix_accounting_recurring_templates_company",
        "accounting_recurring_templates",
        ["company_id"],
    )

    # --- accounting_recurring_template_lines ---
    op.create_table(
        "accounting_recurring_template_lines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "debit_amount", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column(
            "credit_amount", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cost_center_id", postgresql.UUID(as_uuid=True), nullable=True),
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
            ["template_id"],
            ["accounting_recurring_templates.id"],
            name="fk_accounting_recurring_lines_template",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounting_accounts.id"],
            name="fk_accounting_recurring_lines_account",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "template_id",
            "line_number",
            name="uq_accounting_recurring_lines_template_number",
        ),
        sa.CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR "
            "(credit_amount > 0 AND debit_amount = 0)",
            name="ck_accounting_recurring_lines_one_sided",
        ),
        comment="Template lines for recurring journal entries, scoped per company",
    )
    op.create_index(
        "ix_accounting_recurring_lines_template",
        "accounting_recurring_template_lines",
        ["template_id"],
    )

    # --- accounting_recurring_instances ---
    op.create_table(
        "accounting_recurring_instances",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("execution_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
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
            ["template_id"],
            ["accounting_recurring_templates.id"],
            name="fk_accounting_recurring_instances_template",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"],
            ["accounting_journal_entries.id"],
            name="fk_accounting_recurring_instances_journal",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "template_id",
            "execution_date",
            name="uq_accounting_recurring_instances_template_date",
        ),
        sa.CheckConstraint(
            "status IN ('SUCCESS', 'FAILED')",
            name="ck_accounting_recurring_instances_status",
        ),
        comment="Execution history for recurring journal templates, scoped per company",
    )
    op.create_index(
        "ix_accounting_recurring_instances_template",
        "accounting_recurring_instances",
        ["template_id"],
    )


def downgrade() -> None:
    op.drop_table("accounting_recurring_instances")
    op.drop_table("accounting_recurring_template_lines")
    op.drop_table("accounting_recurring_templates")
