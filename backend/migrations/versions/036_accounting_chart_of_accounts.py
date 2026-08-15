"""Accounting Chart of Accounts — Phase 2.

Creates:
  - accounting_account_groups (self-referencing hierarchy)
  - accounting_accounts (self-referencing hierarchy; FK to account_groups)

Revision ID: 036
Revises: 035
Create Date: 2026-08-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- accounting_account_groups ---
    op.create_table(
        "accounting_account_groups",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_code", sa.String(20), nullable=False),
        sa.Column("group_name", sa.String(200), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("parent_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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
            ["parent_group_id"],
            ["accounting_account_groups.id"],
            name="fk_accounting_groups_parent",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "company_id", "group_code", name="uq_accounting_groups_company_code"
        ),
        sa.CheckConstraint(
            "account_type IN ('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE')",
            name="ck_accounting_groups_type",
        ),
        comment="Chart of Accounts group hierarchy, scoped per company",
    )
    op.create_index(
        "ix_accounting_groups_company_type",
        "accounting_account_groups",
        ["company_id", "account_type"],
    )
    op.create_index(
        "ix_accounting_groups_parent", "accounting_account_groups", ["parent_group_id"]
    )

    # --- accounting_accounts ---
    op.create_table(
        "accounting_accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_code", sa.String(20), nullable=False),
        sa.Column("account_name", sa.String(200), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("account_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_leaf", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=True),
        sa.Column(
            "requires_cost_center", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "is_bank_account", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "is_cash_account", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("tax_category", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
            ["account_group_id"],
            ["accounting_account_groups.id"],
            name="fk_accounting_accounts_group",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_account_id"],
            ["accounting_accounts.id"],
            name="fk_accounting_accounts_parent",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "company_id", "account_code", name="uq_accounting_accounts_company_code"
        ),
        sa.CheckConstraint(
            "account_type IN ('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE')",
            name="ck_accounting_accounts_type",
        ),
        comment="Chart of Accounts — individual ledger accounts, scoped per company",
    )
    op.create_index(
        "ix_accounting_accounts_company_type",
        "accounting_accounts",
        ["company_id", "account_type"],
    )
    op.create_index(
        "ix_accounting_accounts_company_active",
        "accounting_accounts",
        ["company_id", "is_active"],
    )
    op.create_index(
        "ix_accounting_accounts_parent", "accounting_accounts", ["parent_account_id"]
    )
    op.create_index(
        "ix_accounting_accounts_group", "accounting_accounts", ["account_group_id"]
    )


def downgrade() -> None:
    op.drop_table("accounting_accounts")
    op.drop_table("accounting_account_groups")
