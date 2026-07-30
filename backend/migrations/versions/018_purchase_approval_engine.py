"""Purchase Approval Engine — Phase 3.

Creates:
  approval_matrices   — one active matrix per document type per company
  matrix_rules        — conditions that trigger approval routing
  approval_levels     — approvers per rule level
  approval_records    — immutable append-only approval action audit trail
  approval_delegates  — time-bounded approval authority delegation

Revision ID: 018
Revises: 017
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "018"
down_revision: str = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # approval_matrices
    # ------------------------------------------------------------------
    op.create_table(
        "approval_matrices",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("document_type", sa.String(30), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.CheckConstraint(
            "document_type IN ('PURCHASE_REQUEST', 'PURCHASE_ORDER', 'VENDOR_RETURN')",
            name="ck_approval_matrices_document_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Approval matrix — one per document type per company",
    )
    op.create_index(
        "ix_approval_matrices_company_id", "approval_matrices", ["company_id"]
    )
    op.create_index(
        "ix_approval_matrices_company_doc",
        "approval_matrices",
        ["company_id", "document_type"],
    )

    # ------------------------------------------------------------------
    # matrix_rules
    # ------------------------------------------------------------------
    op.create_table(
        "matrix_rules",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("matrix_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("condition_type", sa.String(20), nullable=False),
        sa.Column("min_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("max_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column(
            "approval_level", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column(
            "approval_mode", sa.String(20), server_default="SEQUENTIAL", nullable=False
        ),
        sa.CheckConstraint(
            "condition_type IN ('AMOUNT_RANGE', 'CATEGORY', 'DEPARTMENT', 'ALWAYS')",
            name="ck_matrix_rules_condition_type",
        ),
        sa.CheckConstraint(
            "approval_mode IN ('SEQUENTIAL', 'PARALLEL')",
            name="ck_matrix_rules_approval_mode",
        ),
        sa.CheckConstraint(
            "approval_level >= 1",
            name="ck_matrix_rules_approval_level",
        ),
        sa.ForeignKeyConstraint(
            ["matrix_id"], ["approval_matrices.id"], name="fk_matrix_rules_matrix_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Approval matrix rules — conditions that trigger approval routing",
    )
    op.create_index("ix_matrix_rules_company_id", "matrix_rules", ["company_id"])
    op.create_index("ix_matrix_rules_matrix_id", "matrix_rules", ["matrix_id"])

    # ------------------------------------------------------------------
    # approval_levels
    # ------------------------------------------------------------------
    op.create_table(
        "approval_levels",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("rule_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("level_number", sa.Integer(), nullable=False),
        sa.Column("approver_type", sa.String(10), nullable=False),
        sa.Column("approver_role", sa.String(50), nullable=True),
        sa.Column("approver_user_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column(
            "escalation_days", sa.Integer(), server_default=sa.text("3"), nullable=False
        ),
        sa.CheckConstraint(
            "approver_type IN ('ROLE', 'USER')",
            name="ck_approval_levels_approver_type",
        ),
        sa.CheckConstraint(
            "level_number >= 1",
            name="ck_approval_levels_level_number",
        ),
        sa.CheckConstraint(
            "escalation_days >= 0",
            name="ck_approval_levels_escalation_days",
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"], ["matrix_rules.id"], name="fk_approval_levels_rule_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Approver assignments per rule level",
    )
    op.create_index("ix_approval_levels_company_id", "approval_levels", ["company_id"])
    op.create_index("ix_approval_levels_rule_id", "approval_levels", ["rule_id"])

    # ------------------------------------------------------------------
    # approval_records  — append-only
    # ------------------------------------------------------------------
    op.create_table(
        "approval_records",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("document_type", sa.String(30), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("level_number", sa.Integer(), nullable=False),
        sa.Column("approver_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "is_emergency_bypass",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("bypass_justification", sa.Text(), nullable=True),
        sa.Column("actioned_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('APPROVED', 'REJECTED', 'ABSTAINED')",
            name="ck_approval_records_action",
        ),
        sa.CheckConstraint(
            "document_type IN ('PURCHASE_REQUEST', 'PURCHASE_ORDER', 'VENDOR_RETURN')",
            name="ck_approval_records_document_type",
        ),
        sa.CheckConstraint(
            "level_number >= 1",
            name="ck_approval_records_level_number",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Immutable approval action audit trail — append-only",
    )
    op.create_index(
        "ix_approval_records_company_id", "approval_records", ["company_id"]
    )
    op.create_index(
        "ix_approval_records_document",
        "approval_records",
        ["company_id", "document_type", "document_id"],
    )
    op.create_index(
        "ix_approval_records_approver",
        "approval_records",
        ["company_id", "approver_id"],
    )

    # ------------------------------------------------------------------
    # approval_delegates
    # ------------------------------------------------------------------
    op.create_table(
        "approval_delegates",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("delegator_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("delegate_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_type", sa.String(30), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.CheckConstraint(
            "document_type IS NULL OR document_type IN ('PURCHASE_REQUEST', 'PURCHASE_ORDER', 'VENDOR_RETURN')",
            name="ck_approval_delegates_document_type",
        ),
        sa.UniqueConstraint(
            "company_id",
            "delegator_id",
            "delegate_id",
            "document_type",
            name="uq_approval_delegates_delegator_delegate_doc",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Approval authority delegation with time-bounded validity",
    )
    op.create_index(
        "ix_approval_delegates_company_id", "approval_delegates", ["company_id"]
    )
    op.create_index(
        "ix_approval_delegates_delegator",
        "approval_delegates",
        ["company_id", "delegator_id"],
    )
    op.create_index(
        "ix_approval_delegates_delegate",
        "approval_delegates",
        ["company_id", "delegate_id"],
    )


def downgrade() -> None:
    op.drop_table("approval_delegates")
    op.drop_table("approval_records")
    op.drop_table("approval_levels")
    op.drop_table("matrix_rules")
    op.drop_table("approval_matrices")
