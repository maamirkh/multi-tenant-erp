"""Cost Centers — Phase 11.

Creates:
  - accounting_departments   (department definitions, self-referencing hierarchy)
  - accounting_cost_centers  (cost center definitions, belongs to a department)
  - accounting_projects      (project definitions)

Table creation order: departments before cost_centers, since CostCenter.
department_id references Department.id.

Revision ID: 046
Revises: 045
Create Date: 2026-08-09
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


def _soft_delete_audit_columns() -> list[sa.Column]:
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
    # --- accounting_departments ---
    op.create_table(
        "accounting_departments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dept_code", sa.String(20), nullable=False),
        sa.Column("dept_name", sa.String(200), nullable=False),
        sa.Column("parent_dept_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["parent_dept_id"],
            ["accounting_departments.id"],
            name="fk_accounting_departments_parent",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "company_id", "dept_code", name="uq_accounting_departments_company_code"
        ),
        comment="Department definitions, scoped per company",
    )
    op.create_index(
        "ix_accounting_departments_company",
        "accounting_departments",
        ["company_id"],
    )

    # --- accounting_cost_centers ---
    op.create_table(
        "accounting_cost_centers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("center_code", sa.String(20), nullable=False),
        sa.Column("center_name", sa.String(200), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("responsible_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["accounting_departments.id"],
            name="fk_accounting_cost_centers_department",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "company_id", "center_code", name="uq_accounting_cost_centers_company_code"
        ),
        comment="Cost center definitions, scoped per company",
    )
    op.create_index(
        "ix_accounting_cost_centers_company",
        "accounting_cost_centers",
        ["company_id"],
    )
    op.create_index(
        "ix_accounting_cost_centers_department",
        "accounting_cost_centers",
        ["company_id", "department_id"],
    )

    # --- accounting_projects ---
    op.create_table(
        "accounting_projects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_code", sa.String(20), nullable=False),
        sa.Column("project_name", sa.String(200), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("budget_amount", sa.Numeric(20, 6), nullable=True),
        sa.Column("responsible_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_soft_delete_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "project_code", name="uq_accounting_projects_company_code"
        ),
        comment="Project definitions, scoped per company",
    )
    op.create_index(
        "ix_accounting_projects_company",
        "accounting_projects",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_table("accounting_projects")
    op.drop_table("accounting_cost_centers")
    op.drop_table("accounting_departments")
