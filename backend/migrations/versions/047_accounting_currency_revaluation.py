"""Currency Revaluation — Phase 12.

Creates:
  - accounting_currency_revaluations (period-end revaluation run history)

Revision ID: 047
Revises: 046
Create Date: 2026-08-10
"""

from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "047"
down_revision = "046"
branch_labels = None
depends_on = None


def _soft_delete_audit_columns() -> list[sa.Column[Any]]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "accounting_currency_revaluations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fiscal_period_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revaluation_date", sa.Date(), nullable=False),
        sa.Column(
            "currencies_revalued",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "total_unrealized_gain_base",
            sa.Numeric(20, 6),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "total_unrealized_loss_base",
            sa.Numeric(20, 6),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "net_gain_loss_base", sa.Numeric(20, 6), server_default="0", nullable=False
        ),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lines", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["fiscal_period_id"],
            ["accounting_fiscal_periods.id"],
            name="fk_accounting_currency_revaluations_period",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"],
            ["accounting_journal_entries.id"],
            name="fk_accounting_currency_revaluations_journal",
            ondelete="RESTRICT",
        ),
        comment="Period-end currency revaluation runs, scoped per company",
    )
    op.create_index(
        "ix_accounting_currency_revaluations_company",
        "accounting_currency_revaluations",
        ["company_id"],
    )
    op.create_index(
        "ix_accounting_currency_revaluations_company_date",
        "accounting_currency_revaluations",
        ["company_id", "revaluation_date"],
    )


def downgrade() -> None:
    op.drop_table("accounting_currency_revaluations")
