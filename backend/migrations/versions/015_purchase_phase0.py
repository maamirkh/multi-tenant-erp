"""Epic 006 — Purchase Management Phase 0: module scaffold tables.

Creates the following tables:
  1. purchase_feature_flags   — per-company feature flag overrides
  2. supplier_categories      — hierarchical supplier classification tree
  3. payment_terms            — company payment terms master
  4. purchase_reason_codes    — typed reason codes (RETURN/CANCEL/REJECT/GENERAL)
  5. purchase_sequences       — auto-numbering with SELECT FOR UPDATE
  6. purchase_policies        — company-level procurement policy (singleton)

No PostgreSQL ENUM types — status/type values use VARCHAR with CHECK constraints
for forward compatibility (consistent with Epics 1–5).

Revision ID: 015
Revises:     014
Create Date: 2026-07-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# ── Revision identifiers ───────────────────────────────────────────────────

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all Purchase Phase 0 tables."""

    # ── 1. purchase_feature_flags ──────────────────────────────────────────
    op.create_table(
        "purchase_feature_flags",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("flag_key", sa.String(120), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_purchase_ff_company",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "company_id",
            "flag_key",
            name="uq_purchase_ff_company_key",
        ),
        sa.CheckConstraint(
            "flag_key LIKE 'purchase.%'",
            name="ck_purchase_ff_key_prefix",
        ),
        comment="Per-company feature flag overrides for the Purchase module",
    )
    op.create_index(
        "ix_purchase_ff_company_id", "purchase_feature_flags", ["company_id"]
    )
    op.create_index("ix_purchase_ff_flag_key", "purchase_feature_flags", ["flag_key"])

    # ── 2. supplier_categories ─────────────────────────────────────────────
    op.create_table(
        "supplier_categories",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_sup_categories_company",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "company_id", "code", name="uq_sup_categories_company_code"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_sup_categories_status",
        ),
        comment="Hierarchical supplier category tree, scoped per company",
    )
    op.create_index(
        "ix_sup_categories_company_id", "supplier_categories", ["company_id"]
    )
    op.create_index("ix_sup_categories_parent_id", "supplier_categories", ["parent_id"])
    op.create_index(
        "ix_sup_categories_company_status",
        "supplier_categories",
        ["company_id", "status"],
    )

    # ── 3. payment_terms ──────────────────────────────────────────────────
    op.create_table(
        "payment_terms",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("net_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("discount_days", sa.Integer(), nullable=True),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_payment_terms_company",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("company_id", "code", name="uq_payment_terms_company_code"),
        sa.CheckConstraint("net_days >= 0", name="ck_payment_terms_net_days"),
        sa.CheckConstraint(
            "discount_days IS NULL OR discount_days >= 0",
            name="ck_payment_terms_discount_days",
        ),
        sa.CheckConstraint(
            "discount_percent IS NULL OR (discount_percent >= 0 AND discount_percent <= 100)",
            name="ck_payment_terms_discount_percent",
        ),
        comment="Company payment terms master for supplier agreements",
    )
    op.create_index("ix_payment_terms_company_id", "payment_terms", ["company_id"])

    # ── 4. purchase_reason_codes ──────────────────────────────────────────
    op.create_table(
        "purchase_reason_codes",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("reason_type", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_purchase_reason_company",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "company_id",
            "code",
            "reason_type",
            name="uq_purchase_reason_company_code_type",
        ),
        sa.CheckConstraint(
            "reason_type IN ('RETURN', 'CANCELLATION', 'REJECTION', 'GENERAL')",
            name="ck_purchase_reason_type",
        ),
        comment="Typed reason codes for returns, cancellations, and rejections",
    )
    op.create_index(
        "ix_purchase_reason_company_id", "purchase_reason_codes", ["company_id"]
    )
    op.create_index("ix_purchase_reason_type", "purchase_reason_codes", ["reason_type"])

    # ── 5. purchase_sequences ─────────────────────────────────────────────
    op.create_table(
        "purchase_sequences",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_type", sa.String(10), nullable=False),
        sa.Column("prefix", sa.String(10), nullable=False, server_default="''"),
        sa.Column("current_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("reset_yearly", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "format_pattern",
            sa.String(50),
            nullable=False,
            server_default="'{PREFIX}-{YEAR}-{SEQ:06d}'",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_purchase_seq_company",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "company_id",
            "document_type",
            "year",
            name="uq_purchase_seq_company_type_year",
        ),
        sa.CheckConstraint(
            "document_type IN ('PR', 'PO', 'GR', 'RMA')",
            name="ck_purchase_seq_document_type",
        ),
        sa.CheckConstraint(
            "current_value >= 0",
            name="ck_purchase_seq_current_value",
        ),
        comment="Auto-numbering sequences for purchase documents, locked with SELECT FOR UPDATE",
    )
    op.create_index(
        "ix_purchase_sequences_company_id", "purchase_sequences", ["company_id"]
    )
    op.create_index(
        "ix_purchase_sequences_type", "purchase_sequences", ["document_type"]
    )

    # ── 6. purchase_policies ──────────────────────────────────────────────
    op.create_table(
        "purchase_policies",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "direct_po_allowed", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "pr_approval_required", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column(
            "po_approval_required", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column(
            "over_receipt_policy", sa.String(10), nullable=False, server_default="WARN"
        ),
        sa.Column(
            "credit_limit_mode", sa.String(10), nullable=False, server_default="WARN"
        ),
        sa.Column(
            "ppv_alert_threshold_percent",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="5.00",
        ),
        sa.Column(
            "supplier_rating_window",
            sa.Integer(),
            nullable=False,
            server_default="20",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_purchase_policy_company",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("company_id", name="uq_purchase_policy_company"),
        sa.CheckConstraint(
            "over_receipt_policy IN ('BLOCK', 'WARN', 'ALLOW')",
            name="ck_purchase_policy_over_receipt",
        ),
        sa.CheckConstraint(
            "credit_limit_mode IN ('BLOCK', 'WARN', 'OFF')",
            name="ck_purchase_policy_credit_mode",
        ),
        sa.CheckConstraint(
            "ppv_alert_threshold_percent >= 0 AND ppv_alert_threshold_percent <= 100",
            name="ck_purchase_policy_ppv_threshold",
        ),
        sa.CheckConstraint(
            "supplier_rating_window >= 1",
            name="ck_purchase_policy_rating_window",
        ),
        comment="Company-level procurement policy configuration — one row per company",
    )
    op.create_index(
        "ix_purchase_policies_company_id", "purchase_policies", ["company_id"]
    )


def downgrade() -> None:
    """Drop all Purchase Phase 0 tables in reverse order."""
    op.drop_index("ix_purchase_policies_company_id", table_name="purchase_policies")
    op.drop_table("purchase_policies")

    op.drop_index("ix_purchase_sequences_type", table_name="purchase_sequences")
    op.drop_index("ix_purchase_sequences_company_id", table_name="purchase_sequences")
    op.drop_table("purchase_sequences")

    op.drop_index("ix_purchase_reason_type", table_name="purchase_reason_codes")
    op.drop_index("ix_purchase_reason_company_id", table_name="purchase_reason_codes")
    op.drop_table("purchase_reason_codes")

    op.drop_index("ix_payment_terms_company_id", table_name="payment_terms")
    op.drop_table("payment_terms")

    op.drop_index("ix_sup_categories_company_status", table_name="supplier_categories")
    op.drop_index("ix_sup_categories_parent_id", table_name="supplier_categories")
    op.drop_index("ix_sup_categories_company_id", table_name="supplier_categories")
    op.drop_table("supplier_categories")

    op.drop_index("ix_purchase_ff_flag_key", table_name="purchase_feature_flags")
    op.drop_index("ix_purchase_ff_company_id", table_name="purchase_feature_flags")
    op.drop_table("purchase_feature_flags")
