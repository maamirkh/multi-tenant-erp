"""Tax Engine — Phase 11.

Creates:
  - accounting_tax_codes       (tax code definitions)
  - accounting_tax_rates       (rate history per code, effective date ranges)
  - accounting_tax_groups      (tax group definitions)
  - accounting_tax_group_lines (tax codes within each group)

Revision ID: 045
Revises: 044
Create Date: 2026-08-09
"""

from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "045"
down_revision = "044"
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
    # --- accounting_tax_codes ---
    op.create_table(
        "accounting_tax_codes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tax_code", sa.String(20), nullable=False),
        sa.Column("tax_name", sa.String(200), nullable=False),
        sa.Column("tax_type", sa.String(20), nullable=False),
        sa.Column("applicability", sa.String(20), nullable=False),
        sa.Column("gl_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "is_input_tax_recoverable",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("country_code", sa.String(2), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["gl_account_id"],
            ["accounting_accounts.id"],
            name="fk_accounting_tax_codes_gl_account",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "company_id", "tax_code", name="uq_accounting_tax_codes_company_code"
        ),
        sa.CheckConstraint(
            "tax_type IN ('SALES_TAX','VAT','GST','WITHHOLDING','COMPOUND',"
            "'EXEMPT','ZERO_RATED','OUT_OF_SCOPE')",
            name="ck_accounting_tax_codes_type",
        ),
        sa.CheckConstraint(
            "applicability IN ('SALES','PURCHASES','BOTH')",
            name="ck_accounting_tax_codes_applicability",
        ),
        comment="Tax code definitions, scoped per company",
    )
    op.create_index(
        "ix_accounting_tax_codes_company_active",
        "accounting_tax_codes",
        ["company_id", "is_active"],
    )

    # --- accounting_tax_rates ---
    op.create_table(
        "accounting_tax_rates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tax_code_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("rate", sa.Numeric(9, 6), nullable=False),
        sa.Column(
            "rounding_rule", sa.String(20), server_default="HALF_UP", nullable=False
        ),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["tax_code_id"],
            ["accounting_tax_codes.id"],
            name="fk_accounting_tax_rates_tax_code",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("rate >= 0", name="ck_accounting_tax_rates_non_negative"),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_accounting_tax_rates_date_order",
        ),
        sa.CheckConstraint(
            "rounding_rule IN ('HALF_UP','HALF_EVEN','DOWN','UP')",
            name="ck_accounting_tax_rates_rounding_rule",
        ),
        comment="Tax rate history per tax code, scoped per company",
    )
    op.create_index(
        "ix_accounting_tax_rates_tax_code_effective",
        "accounting_tax_rates",
        ["company_id", "tax_code_id", "effective_from"],
    )

    # --- accounting_tax_groups ---
    op.create_table(
        "accounting_tax_groups",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_code", sa.String(20), nullable=False),
        sa.Column("group_name", sa.String(200), nullable=False),
        sa.Column("applicability", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "group_code", name="uq_accounting_tax_groups_company_code"
        ),
        sa.CheckConstraint(
            "applicability IN ('SALES','PURCHASES','BOTH')",
            name="ck_accounting_tax_groups_applicability",
        ),
        comment="Tax group definitions, scoped per company",
    )

    # --- accounting_tax_group_lines ---
    op.create_table(
        "accounting_tax_group_lines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tax_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tax_code_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["tax_group_id"],
            ["accounting_tax_groups.id"],
            name="fk_accounting_tax_group_lines_group",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tax_code_id"],
            ["accounting_tax_codes.id"],
            name="fk_accounting_tax_group_lines_tax_code",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tax_group_id",
            "tax_code_id",
            name="uq_accounting_tax_group_lines_group_code",
        ),
        comment="Tax codes within each tax group, scoped per company",
    )
    op.create_index(
        "ix_accounting_tax_group_lines_group",
        "accounting_tax_group_lines",
        ["company_id", "tax_group_id"],
    )


def downgrade() -> None:
    op.drop_table("accounting_tax_group_lines")
    op.drop_table("accounting_tax_groups")
    op.drop_table("accounting_tax_rates")
    op.drop_table("accounting_tax_codes")
