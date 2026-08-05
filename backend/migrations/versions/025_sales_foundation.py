"""Sales foundation tables — Phase 0.

Creates all Phase 0 tables for the Sales module:
  - customer_categories
  - customer_groups
  - sales_payment_terms
  - sales_reason_codes
  - sales_sequences
  - sales_configuration
  - sales_feature_flags

Revision ID: 025
Revises: 024
Create Date: 2026-07-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- customer_categories ---
    op.create_table(
        "customer_categories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "default_payment_term_id", postgresql.UUID(as_uuid=False), nullable=True
        ),
        sa.Column(
            "default_credit_limit",
            sa.Numeric(15, 2),
            server_default="0",
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "code", name="uq_customer_categories_company_code"
        ),
        sa.CheckConstraint(
            "default_credit_limit >= 0", name="ck_customer_categories_credit_limit"
        ),
        comment="Customer classification categories, scoped per company",
    )
    op.create_index(
        "ix_customer_categories_company_active",
        "customer_categories",
        ["company_id", "is_active"],
    )

    # --- customer_groups ---
    op.create_table(
        "customer_groups",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "code", name="uq_customer_groups_company_code"
        ),
        comment="Secondary customer classification for reporting and discounts",
    )
    op.create_index(
        "ix_customer_groups_company_active",
        "customer_groups",
        ["company_id", "is_active"],
    )

    # --- sales_payment_terms ---
    op.create_table(
        "sales_payment_terms",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("due_days", sa.Integer(), nullable=False),
        sa.Column("discount_days", sa.Integer(), nullable=True),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "code", name="uq_sales_payment_terms_company_code"
        ),
        sa.CheckConstraint("due_days >= 0", name="ck_sales_payment_terms_due_days"),
        comment="Sales payment terms master data, scoped per company",
    )
    op.create_index(
        "ix_sales_payment_terms_company_active",
        "sales_payment_terms",
        ["company_id", "is_active"],
    )

    # --- sales_reason_codes ---
    op.create_table(
        "sales_reason_codes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("reason_type", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "code",
            "reason_type",
            name="uq_sales_reason_codes_company_code_type",
        ),
        sa.CheckConstraint(
            "reason_type IN ('RETURN', 'CANCELLATION', 'REJECTION', 'GENERAL')",
            name="ck_sales_reason_codes_type",
        ),
        comment="Typed reason codes for sales returns, cancellations, rejections",
    )
    op.create_index(
        "ix_sales_reason_codes_company_type",
        "sales_reason_codes",
        ["company_id", "reason_type"],
    )

    # --- sales_sequences ---
    op.create_table(
        "sales_sequences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(10), nullable=False),
        sa.Column("prefix", sa.String(10), server_default="''", nullable=False),
        sa.Column("current_value", sa.Integer(), server_default="0", nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("reset_yearly", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "format_pattern",
            sa.String(50),
            server_default="'{PREFIX}-{YEAR}-{SEQ:06d}'",
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "document_type", "year", name="uq_sales_seq_company_type_year"
        ),
        sa.CheckConstraint(
            "document_type IN ('SQ', 'SO', 'DN', 'SI', 'SR')",
            name="ck_sales_seq_document_type",
        ),
        sa.CheckConstraint("current_value >= 0", name="ck_sales_seq_current_value"),
        comment="Auto-numbering sequences for sales documents, locked with SELECT FOR UPDATE",
    )
    op.create_index("ix_sales_sequences_type", "sales_sequences", ["document_type"])

    # --- sales_configuration ---
    op.create_table(
        "sales_configuration",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "default_quotation_validity_days",
            sa.Integer(),
            server_default="30",
            nullable=False,
        ),
        sa.Column(
            "quotation_expiry_warning_days",
            sa.Integer(),
            server_default="3",
            nullable=False,
        ),
        sa.Column("auto_approve_threshold", sa.Numeric(15, 2), nullable=True),
        sa.Column("minimum_margin_percentage", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "credit_warning_threshold",
            sa.Numeric(5, 2),
            server_default="80.00",
            nullable=False,
        ),
        sa.Column(
            "reservation_expiry_hours",
            sa.Integer(),
            server_default="48",
            nullable=False,
        ),
        sa.Column(
            "require_quotation_before_order",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "tax_inclusive_pricing",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", name="uq_sales_configuration_company"),
        sa.CheckConstraint(
            "default_quotation_validity_days >= 1", name="ck_sales_config_validity_days"
        ),
        sa.CheckConstraint(
            "credit_warning_threshold >= 0 AND credit_warning_threshold <= 100",
            name="ck_sales_config_credit_threshold",
        ),
        sa.CheckConstraint(
            "reservation_expiry_hours >= 1", name="ck_sales_config_reservation_hours"
        ),
        comment="Company-level sales configuration — one row per company",
    )

    # --- sales_feature_flags ---
    op.create_table(
        "sales_feature_flags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("flag_key", sa.String(120), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "flag_key", name="uq_sales_ff_company_key"),
        comment="Per-company feature flag overrides for the Sales module",
    )
    op.create_index(
        "ix_sales_feature_flags_flag_key", "sales_feature_flags", ["flag_key"]
    )


def downgrade() -> None:
    op.drop_table("sales_feature_flags")
    op.drop_table("sales_configuration")
    op.drop_table("sales_sequences")
    op.drop_table("sales_reason_codes")
    op.drop_table("sales_payment_terms")
    op.drop_table("customer_groups")
    op.drop_table("customer_categories")
