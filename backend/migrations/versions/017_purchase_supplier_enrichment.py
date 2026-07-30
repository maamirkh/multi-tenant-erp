"""Purchase Supplier Enrichment — Phase 2

Creates the Supplier enrichment tables:
  - credit_limits          — per-supplier credit limits with enforcement mode
  - bank_details           — banking details (Finance Manager restricted)
  - supplier_ratings       — composite performance ratings computed from GRs
  - supplier_documents     — compliance documents with expiry tracking
  - supplier_lead_times    — per-supplier and per-product lead time overrides

All tables reference suppliers.id via FK.

Revision ID: 017
Revises: 016
Create Date: 2026-07-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # credit_limits
    # ------------------------------------------------------------------
    op.create_table(
        "credit_limits",
        sa.Column(
            "id",
            PG_UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("supplier_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column(
            "credit_limit_amount", sa.Numeric(15, 2), nullable=False, server_default="0"
        ),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="USD"),
        sa.Column(
            "enforcement_mode", sa.String(10), nullable=False, server_default="WARN"
        ),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("created_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["suppliers.id"], name="fk_credit_limits_supplier_id"
        ),
        sa.UniqueConstraint(
            "company_id", "supplier_id", name="uq_credit_limits_company_supplier"
        ),
        sa.CheckConstraint("credit_limit_amount >= 0", name="ck_credit_limits_amount"),
        sa.CheckConstraint(
            "enforcement_mode IN ('BLOCK', 'WARN', 'OFF')",
            name="ck_credit_limits_enforcement_mode",
        ),
        comment="Per-supplier credit limits with configurable enforcement mode",
    )
    op.create_index("ix_credit_limits_company_id", "credit_limits", ["company_id"])
    op.create_index("ix_credit_limits_supplier_id", "credit_limits", ["supplier_id"])

    # ------------------------------------------------------------------
    # bank_details
    # ------------------------------------------------------------------
    op.create_table(
        "bank_details",
        sa.Column(
            "id",
            PG_UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("supplier_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("bank_name", sa.String(200), nullable=False),
        sa.Column("account_name", sa.String(200), nullable=False),
        sa.Column("account_number", sa.String(50), nullable=False),
        sa.Column("iban", sa.String(34), nullable=True),
        sa.Column("swift_bic", sa.String(11), nullable=True),
        sa.Column("routing_number", sa.String(20), nullable=True),
        sa.Column("bank_country", sa.String(2), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("created_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["suppliers.id"], name="fk_bank_details_supplier_id"
        ),
        comment="Supplier banking details (Finance Manager restricted)",
    )
    op.create_index("ix_bank_details_company_id", "bank_details", ["company_id"])
    op.create_index("ix_bank_details_supplier_id", "bank_details", ["supplier_id"])

    # ------------------------------------------------------------------
    # supplier_ratings
    # ------------------------------------------------------------------
    op.create_table(
        "supplier_ratings",
        sa.Column(
            "id",
            PG_UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("supplier_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("on_time_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("fill_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column(
            "rejection_rate", sa.Numeric(5, 2), nullable=False, server_default="0"
        ),
        sa.Column(
            "composite_score", sa.Numeric(3, 1), nullable=False, server_default="0"
        ),
        sa.Column("gr_count_window", sa.Integer, nullable=False, server_default="0"),
        sa.Column("manual_override_score", sa.Numeric(3, 1), nullable=True),
        sa.Column("manual_override_reason", sa.Text, nullable=True),
        sa.Column(
            "last_computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("created_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["suppliers.id"], name="fk_supplier_ratings_supplier_id"
        ),
        sa.UniqueConstraint(
            "company_id", "supplier_id", name="uq_supplier_ratings_company_supplier"
        ),
        sa.CheckConstraint(
            "on_time_rate >= 0 AND on_time_rate <= 100",
            name="ck_supplier_ratings_on_time",
        ),
        sa.CheckConstraint(
            "fill_rate >= 0 AND fill_rate <= 100", name="ck_supplier_ratings_fill_rate"
        ),
        sa.CheckConstraint(
            "rejection_rate >= 0 AND rejection_rate <= 100",
            name="ck_supplier_ratings_rejection_rate",
        ),
        sa.CheckConstraint(
            "composite_score >= 0 AND composite_score <= 10",
            name="ck_supplier_ratings_composite",
        ),
        sa.CheckConstraint(
            "manual_override_score IS NULL OR (manual_override_score >= 0 AND manual_override_score <= 10)",
            name="ck_supplier_ratings_override",
        ),
        comment="Computed supplier performance rating — one per supplier",
    )
    op.create_index(
        "ix_supplier_ratings_company_id", "supplier_ratings", ["company_id"]
    )
    op.create_index(
        "ix_supplier_ratings_supplier_id", "supplier_ratings", ["supplier_id"]
    )

    # ------------------------------------------------------------------
    # supplier_documents
    # ------------------------------------------------------------------
    op.create_table(
        "supplier_documents",
        sa.Column(
            "id",
            PG_UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("supplier_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column("document_number", sa.String(100), nullable=True),
        sa.Column("issue_date", sa.Date, nullable=True),
        sa.Column("expiry_date", sa.Date, nullable=True),
        sa.Column("file_url", sa.String(1000), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("created_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["suppliers.id"], name="fk_supplier_documents_supplier_id"
        ),
        comment="Compliance documents for suppliers (trade license, certs, etc.)",
    )
    op.create_index(
        "ix_supplier_documents_company_id", "supplier_documents", ["company_id"]
    )
    op.create_index(
        "ix_supplier_documents_supplier_id", "supplier_documents", ["supplier_id"]
    )
    op.create_index(
        "ix_supplier_documents_expiry",
        "supplier_documents",
        ["company_id", "expiry_date"],
    )

    # ------------------------------------------------------------------
    # supplier_lead_times
    # ------------------------------------------------------------------
    op.create_table(
        "supplier_lead_times",
        sa.Column(
            "id",
            PG_UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("supplier_id", PG_UUID(as_uuid=False), nullable=False),
        sa.Column("product_id", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("lead_time_days", sa.Integer, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("created_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", PG_UUID(as_uuid=False), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["suppliers.id"], name="fk_supplier_lead_times_supplier_id"
        ),
        sa.UniqueConstraint(
            "company_id",
            "supplier_id",
            "product_id",
            name="uq_supplier_lead_times_supplier_product",
        ),
        sa.CheckConstraint("lead_time_days >= 0", name="ck_supplier_lead_times_days"),
        comment="Supplier lead times — per supplier and per product override",
    )
    op.create_index(
        "ix_supplier_lead_times_company_id", "supplier_lead_times", ["company_id"]
    )
    op.create_index(
        "ix_supplier_lead_times_supplier_id", "supplier_lead_times", ["supplier_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_supplier_lead_times_supplier_id", table_name="supplier_lead_times"
    )
    op.drop_index("ix_supplier_lead_times_company_id", table_name="supplier_lead_times")
    op.drop_table("supplier_lead_times")

    op.drop_index("ix_supplier_documents_expiry", table_name="supplier_documents")
    op.drop_index("ix_supplier_documents_supplier_id", table_name="supplier_documents")
    op.drop_index("ix_supplier_documents_company_id", table_name="supplier_documents")
    op.drop_table("supplier_documents")

    op.drop_index("ix_supplier_ratings_supplier_id", table_name="supplier_ratings")
    op.drop_index("ix_supplier_ratings_company_id", table_name="supplier_ratings")
    op.drop_table("supplier_ratings")

    op.drop_index("ix_bank_details_supplier_id", table_name="bank_details")
    op.drop_index("ix_bank_details_company_id", table_name="bank_details")
    op.drop_table("bank_details")

    op.drop_index("ix_credit_limits_supplier_id", table_name="credit_limits")
    op.drop_index("ix_credit_limits_company_id", table_name="credit_limits")
    op.drop_table("credit_limits")
