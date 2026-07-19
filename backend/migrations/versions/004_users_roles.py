"""Epic 004 — Users & Roles: create all users_roles module tables.

Creates the following tables in FK-dependency order:
  1. permissions        — global permission catalogue (no FK dependencies)
  2. roles              — company-scoped role definitions (FK to companies)
  3. role_permissions   — join table (FK to roles + permissions)
  4. company_members    — membership records (FK to companies, users, roles)
  5. user_preferences   — user display preferences (FK to users)

Also extends the existing ``users`` table with 3 new columns:
  - avatar_url (VARCHAR 500)
  - avatar_previous_url (VARCHAR 500)
  - phone (VARCHAR 20)

No PostgreSQL ENUM types — status values use VARCHAR with CHECK constraints
for forward compatibility (same pattern as Epic 003 companies.status).

Downgrade drops in strict reverse FK-dependency order and removes
the added ``users`` columns.

Revision ID: 004
Revises:     003
Create Date: 2026-07-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ── Revision identifiers ───────────────────────────────────────────────────

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all users_roles module tables and extend users table."""

    # ── 0. Extend users table ──────────────────────────────────────────────
    op.add_column("users", sa.Column("avatar_url", sa.String(500), nullable=True))
    op.add_column(
        "users", sa.Column("avatar_previous_url", sa.String(500), nullable=True)
    )
    op.add_column("users", sa.Column("phone", sa.String(20), nullable=True))

    # ── 1. permissions (global — no company_id) ────────────────────────────
    op.create_table(
        "permissions",
        sa.Column(
            "id",
            sa.String(100),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
        sa.PrimaryKeyConstraint("id", name="pk_permissions"),
    )
    op.create_index("ix_permissions_module", "permissions", ["module"])

    # ── 2. roles (company-scoped) ──────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        # TenantBaseModel fields
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # Role-specific fields
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("slug", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_roles_company_id_companies",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "rank > 0 AND rank <= 100",
            name="ck_roles_rank_range",
        ),
        sa.UniqueConstraint("company_id", "slug", name="uq_roles_company_slug"),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
    )
    op.create_index("ix_roles_company_id", "roles", ["company_id"])
    op.create_index("ix_roles_company_is_active", "roles", ["company_id", "is_active"])
    op.create_index("ix_roles_company_rank", "roles", ["company_id", "rank"])

    # ── 3. role_permissions (join table) ───────────────────────────────────
    op.create_table(
        "role_permissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name="fk_role_permissions_role_id_roles",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name="fk_role_permissions_permission_id_permissions",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "role_id",
            "permission_id",
            name="uq_role_permissions_role_permission",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_role_permissions"),
    )
    op.create_index(
        "ix_role_permissions_permission_id", "role_permissions", ["permission_id"]
    )

    # ── 4. company_members ─────────────────────────────────────────────────
    op.create_table(
        "company_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        # TenantBaseModel fields
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # Core fields
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'pending_invitation'"),
        ),
        # Employee information
        sa.Column("employee_id", sa.String(50), nullable=True),
        sa.Column("job_title", sa.String(100), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("work_phone", sa.String(20), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # Invitation tracking
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invitation_accepted_at", sa.DateTime(timezone=True), nullable=True),
        # Status metadata
        sa.Column("suspended_reason", sa.Text(), nullable=True),
        sa.Column("deletion_reason", sa.Text(), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_company_members_company_id_companies",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_company_members_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name="fk_company_members_role_id_roles",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["users.id"],
            name="fk_company_members_invited_by_users",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('pending_invitation','active','inactive','suspended','locked','archived')",
            name="ck_company_members_status",
        ),
        sa.UniqueConstraint(
            "company_id", "user_id", name="uq_company_members_company_user"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_company_members"),
    )
    # Partial unique constraint on employee_id (only when NOT NULL)
    op.create_index(
        "uq_company_members_company_employee_id",
        "company_members",
        ["company_id", "employee_id"],
        unique=True,
        postgresql_where=sa.text("employee_id IS NOT NULL"),
    )
    op.create_index(
        "ix_company_members_company_status",
        "company_members",
        ["company_id", "status"],
    )
    op.create_index("ix_company_members_user_id", "company_members", ["user_id"])
    op.create_index("ix_company_members_role_id", "company_members", ["role_id"])
    op.create_index(
        "ix_company_members_company_department",
        "company_members",
        ["company_id", "department"],
    )

    # ── 5. user_preferences ────────────────────────────────────────────────
    op.create_table(
        "user_preferences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "language",
            sa.String(10),
            nullable=False,
            server_default=sa.text("'en'"),
        ),
        sa.Column(
            "timezone",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'UTC'"),
        ),
        sa.Column(
            "date_format",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'YYYY-MM-DD'"),
        ),
        sa.Column(
            "number_format",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'en-US'"),
        ),
        sa.Column(
            "theme",
            sa.String(10),
            nullable=False,
            server_default=sa.text("'system'"),
        ),
        sa.Column(
            "notification_preferences",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_preferences_user_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", name="uq_user_preferences_user_id"),
        sa.PrimaryKeyConstraint("id", name="pk_user_preferences"),
    )


def downgrade() -> None:
    """Drop all users_roles tables and remove users table extensions."""

    # ── 5. user_preferences ────────────────────────────────────────────────
    op.drop_table("user_preferences")

    # ── 4. company_members ─────────────────────────────────────────────────
    op.drop_index("ix_company_members_company_department", table_name="company_members")
    op.drop_index("ix_company_members_role_id", table_name="company_members")
    op.drop_index("ix_company_members_user_id", table_name="company_members")
    op.drop_index("ix_company_members_company_status", table_name="company_members")
    op.drop_index(
        "uq_company_members_company_employee_id", table_name="company_members"
    )
    op.drop_table("company_members")

    # ── 3. role_permissions ────────────────────────────────────────────────
    op.drop_index("ix_role_permissions_permission_id", table_name="role_permissions")
    op.drop_table("role_permissions")

    # ── 2. roles ───────────────────────────────────────────────────────────
    op.drop_index("ix_roles_company_rank", table_name="roles")
    op.drop_index("ix_roles_company_is_active", table_name="roles")
    op.drop_index("ix_roles_company_id", table_name="roles")
    op.drop_table("roles")

    # ── 1. permissions ─────────────────────────────────────────────────────
    op.drop_index("ix_permissions_module", table_name="permissions")
    op.drop_table("permissions")

    # ── 0. Remove users table extensions ───────────────────────────────────
    op.drop_column("users", "phone")
    op.drop_column("users", "avatar_previous_url")
    op.drop_column("users", "avatar_url")
