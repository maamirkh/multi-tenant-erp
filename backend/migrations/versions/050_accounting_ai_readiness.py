"""AI ERP Readiness — Phase 17 (tasks.md T304-T309).

Adds ``accounting_anomaly_flags`` for the anomaly-detection stub endpoint
(``POST /accounting/ai/anomaly-report``, T307). No other schema changes are
needed for this phase — the GL event stream (T304) and P&L/cash flow
history (T305/T306) endpoints are read-only projections over existing
``accounting_journal_entries``/``accounting_journal_lines`` data, and
``accounting.ai.enabled`` (T309's gating flag) was already registered in
migration 034's ``accounting_feature_flags`` table (per-row override
storage, not a schema change).

Spec ref: specs/008-accounting-finance/tasks.md T307
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "050"
down_revision = "049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounting_anomaly_flags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "journal_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounting_journal_entries.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('OPEN','REVIEWED','DISMISSED')",
            name="ck_accounting_anomaly_flags_status",
        ),
        comment="AI-flagged journal entries pending human review (Phase 17 AI readiness stub)",
    )
    op.create_index(
        "ix_accounting_anomaly_flags_company_id",
        "accounting_anomaly_flags",
        ["company_id"],
    )
    op.create_index(
        "ix_accounting_anomaly_flags_journal_entry_id",
        "accounting_anomaly_flags",
        ["journal_entry_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_accounting_anomaly_flags_journal_entry_id",
        table_name="accounting_anomaly_flags",
    )
    op.drop_index(
        "ix_accounting_anomaly_flags_company_id", table_name="accounting_anomaly_flags"
    )
    op.drop_table("accounting_anomaly_flags")
