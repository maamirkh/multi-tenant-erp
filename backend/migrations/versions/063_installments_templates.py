"""Installments plan templates — Epic 10, Phase 0 (T002).

Creates ``installment_plan_templates`` — reusable named commercial plans
(spec.md §9.2). No FK to any external table; ``InstallmentContract`` later
references this table's ``id`` for informational lineage only (FK added in
064 once the contracts table exists), never dereferenced for financial
truth after contract creation (BR-INST-009).

Revision ID: 063
Revises: 062
Create Date: 2026-08-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "063"
down_revision = "062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "installment_plan_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("installment_count", sa.Integer(), nullable=False),
        sa.Column("down_payment_rule", postgresql.JSONB(), nullable=False),
        sa.Column("markup_rule", postgresql.JSONB(), nullable=True),
        sa.Column("grace_period_days", sa.Integer(), nullable=True),
        sa.Column("late_charge_policy", postgresql.JSONB(), nullable=True),
        sa.Column("early_settlement_rule", postgresql.JSONB(), nullable=True),
        sa.Column("applicable_product_ids", postgresql.JSONB(), nullable=True),
        sa.Column(
            "requires_approval", sa.Boolean(), server_default="false", nullable=False
        ),
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
            "installment_count > 0",
            name="ck_installment_plan_templates_installment_count",
        ),
        comment="Reusable named Installments commercial plan templates",
    )
    # Unique per company while not soft-deleted — deactivated/deleted names
    # may be reused (FR-INST-013: deactivation never affects existing
    # contracts, and a deleted template's name must not permanently block
    # re-registration).
    op.execute(
        """
        CREATE UNIQUE INDEX uq_installment_plan_templates_company_name
        ON installment_plan_templates (company_id, name)
        WHERE is_deleted = false
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_installment_plan_templates_company_name")
    op.drop_table("installment_plan_templates")
