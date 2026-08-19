"""Platform usage & AI readiness — Epic 9A, Phase 2 (T020-T021).

Creates the usage metering + provider-neutral AI readiness persistence
layer (data-model.md "Usage & AI Readiness"): ``usage_records``,
``ai_credit_ledger_entries``. ``provider``/``model`` are free-text
nullable — never structurally coupled to a vendor (BR-9A-026, FR-9A-234).
Both tables remain empty until a later phase/epic actually populates them
— no zero-value placeholder rows are inserted by this migration.

Revision ID: 060
Revises: 059
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "060"
down_revision = "059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- usage_records ---
    op.create_table(
        "usage_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_key", sa.String(50), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 2), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
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
            ["company_id"], ["companies.id"], name="fk_usage_records_company_id"
        ),
        sa.ForeignKeyConstraint(
            ["metric_key"],
            ["quota_definitions.key"],
            name="fk_usage_records_metric_key",
        ),
        comment="Periodic/batch usage rows, not per-event streaming (plan.md "
        "§18) — absence of a current-period row is 'unavailable', never "
        "silently zero",
    )
    op.create_index("ix_usage_records_company_id", "usage_records", ["company_id"])

    # --- ai_credit_ledger_entries ---
    op.create_table(
        "ai_credit_ledger_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delta", sa.Numeric(18, 4), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "actor_platform_administrator_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "platform_audit_event_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("provider", sa.String(100), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(18, 6), nullable=True),
        sa.Column("billable_cost", sa.Numeric(18, 6), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
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
            ["company_id"],
            ["companies.id"],
            name="fk_ai_credit_ledger_entries_company_id",
        ),
        sa.ForeignKeyConstraint(
            ["actor_platform_administrator_id"],
            ["platform_administrators.id"],
            name="fk_ai_credit_ledger_entries_actor_id",
        ),
        sa.ForeignKeyConstraint(
            ["platform_audit_event_id"],
            ["platform_audit_events.id"],
            name="fk_ai_credit_ledger_entries_audit_event_id",
        ),
        comment="Signed delta ledger — positive = credit grant, negative = "
        "usage debit. Current balance per company = SUM(delta). Empty until "
        "an AI capability epic exists (§19)",
    )
    op.create_index(
        "ix_ai_credit_ledger_entries_company_id",
        "ai_credit_ledger_entries",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_credit_ledger_entries_company_id", "ai_credit_ledger_entries")
    op.drop_table("ai_credit_ledger_entries")

    op.drop_index("ix_usage_records_company_id", "usage_records")
    op.drop_table("usage_records")
