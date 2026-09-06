"""Installments schedule — Epic 10, Phase 0 (T004).

Creates ``installment_schedule_versions`` (TenantBaseModel-shaped, but
immutable once created — no update method exists anywhere in the
repository layer, enforced by omission not by a DB trigger) and
``installment_schedule_lines`` (append-only, plain ``Base`` with an
explicit ``company_id`` column — mirrors ``accounting_journal_lines``'
(``JournalLine``) shape: no ``updated_at``, ``is_deleted``, ``deleted_at``,
or ``created_by`` column exists at all).

Closes the deferred FK from migration 064:
``installment_contracts.active_schedule_version_id`` was created there
without its FK constraint because this table didn't exist yet — the same
two-table-cycle technique migration 055 uses for
``crm_leads``/``crm_opportunities``.

Revision ID: 065
Revises: 064
Create Date: 2026-08-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "065"
down_revision = "064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- installment_schedule_versions ---
    op.create_table(
        "installment_schedule_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'DRAFT'"),
            nullable=False,
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("generated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
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
            ["contract_id"],
            ["installment_contracts.id"],
            name="fk_installment_schedule_versions_contract_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "contract_id",
            "version_number",
            name="uq_installment_schedule_versions_contract_number",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED')",
            name="ck_installment_schedule_versions_status",
        ),
        comment=(
            "One version of a contract's payment schedule — immutable once "
            "created, no update method exists on its repository"
        ),
    )

    # Close the deferred FK from 064.
    op.create_foreign_key(
        "fk_installment_contracts_active_schedule_version_id",
        "installment_contracts",
        "installment_schedule_versions",
        ["active_schedule_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # --- installment_schedule_lines (append-only, plain Base) ---
    op.create_table(
        "installment_schedule_lines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("scheduled_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("waived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("waived_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("waived_reason", sa.Text(), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("voided_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["schedule_version_id"],
            ["installment_schedule_versions.id"],
            name="fk_installment_schedule_lines_schedule_version_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "schedule_version_id",
            "sequence",
            name="uq_installment_schedule_lines_version_sequence",
        ),
        sa.CheckConstraint(
            "scheduled_amount > 0", name="ck_installment_schedule_lines_positive_amount"
        ),
        comment=(
            "Append-only contractual due obligations — no UPDATE path exists "
            "for scheduled_amount/due_date, ever"
        ),
    )


def downgrade() -> None:
    op.drop_table("installment_schedule_lines")

    op.drop_constraint(
        "fk_installment_contracts_active_schedule_version_id",
        "installment_contracts",
        type_="foreignkey",
    )

    op.drop_table("installment_schedule_versions")
