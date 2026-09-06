"""Platform Administration foundation — Epic 9A, Phase 2 (T010-T015).

Creates the Platform identity/session/RBAC/audit persistence layer
(data-model.md "Identity & Session"): ``platform_administrators``,
``platform_roles``, ``platform_permissions``, ``platform_role_permissions``,
``platform_admin_role_assignments``, ``platform_sessions``,
``platform_refresh_tokens``, ``platform_audit_events``. These are lean
``BaseModel``-only tables (``id``/``created_at``/``updated_at``) — never
``TenantBaseModel`` — since they are platform-scoped, not tenant-scoped
(plan.md §3, data-model.md line 3).

Also adds two additive, nullable columns to the existing ``companies``
table — ``pre_suspension_status`` and ``access_invalidated_at`` (ADR-12,
ADR-6 Layer 2, plan.md §9.1/§10.2) — plus their two CHECK constraints.

**Mandatory preflight guard** (plan.md §33.1, Correction 2): before either
CHECK constraint is created, this migration queries for pre-existing
``companies.status = 'suspended'`` rows. Such a row's true prior status is
unrecoverable — fabricating it would make ``suspended -> pre-suspension
status`` non-deterministic. Zero rows -> proceed normally. One or more ->
raise ``RuntimeError`` naming the affected slugs and the remediation
options; nothing is left partially applied because Alembic wraps each
migration's ``upgrade()`` in a single transaction (see
``migrations/env.py``'s ``run_migrations_online()``), so the raise rolls
back every DDL statement this migration has already issued.

This is the final migration to introduce new *tables*; no bootstrap
migration exists (ADR-8) — provisioning the first Platform Owner is a
separate, explicitly-invoked operator command, not schema versioning.

Revision ID: 057
Revises: 056
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "057"
down_revision = "056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- platform_administrators ---
    op.create_table(
        "platform_administrators",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_by", postgresql.UUID(as_uuid=True), nullable=True),
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
            ["user_id"], ["users.id"], name="fk_platform_administrators_user_id"
        ),
        sa.UniqueConstraint("user_id", name="uq_platform_administrators_user_id"),
        comment="Platform Administrator principal — a separate first-class Platform "
        "identity, never derived from tenant CompanyMember roles (BR-9A-001)",
    )

    # --- platform_roles ---
    op.create_table(
        "platform_roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("code", name="uq_platform_roles_code"),
        comment="Platform RBAC role — code is configuration data, not an enum "
        "(FR-9A-140, Constitution §46); new roles need no migration",
    )

    # --- platform_permissions ---
    op.create_table(
        "platform_permissions",
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("area", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("code"),
        comment="Platform permission catalogue — code-as-PK mirrors tenant "
        "Permission's convention (plan.md §3.2)",
    )

    # --- platform_role_permissions ---
    op.create_table(
        "platform_role_permissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", sa.String(100), nullable=False),
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
            ["role_id"],
            ["platform_roles.id"],
            name="fk_platform_role_permissions_role_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["platform_permissions.code"],
            name="fk_platform_role_permissions_permission_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "role_id", "permission_id", name="uq_platform_role_permissions_role_perm"
        ),
        comment="Bundle of permissions granted by a Platform Role",
    )

    # --- platform_admin_role_assignments ---
    op.create_table(
        "platform_admin_role_assignments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "platform_administrator_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
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
            ["platform_administrator_id"],
            ["platform_administrators.id"],
            name="fk_platform_admin_role_assignments_admin_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["platform_roles.id"],
            name="fk_platform_admin_role_assignments_role_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by"],
            ["platform_administrators.id"],
            name="fk_platform_admin_role_assignments_assigned_by",
        ),
        sa.UniqueConstraint(
            "platform_administrator_id",
            "role_id",
            name="uq_platform_admin_role_assignments_admin_role",
        ),
        comment="Effective permissions = union across all assigned roles' "
        "permissions (FR-9A-142); assigned_by is null only for the "
        "bootstrap-created first assignment",
    )

    # --- platform_sessions ---
    op.create_table(
        "platform_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "platform_administrator_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("is_revoked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
            ["platform_administrator_id"],
            ["platform_administrators.id"],
            name="fk_platform_sessions_admin_id",
            ondelete="CASCADE",
        ),
        comment="Platform authentication session — structurally separate from "
        "tenant sessions (BR-9A-003); one-way active->revoked, never "
        "un-revoked",
    )
    op.create_index(
        "ix_platform_sessions_admin_id",
        "platform_sessions",
        ["platform_administrator_id"],
    )

    # --- platform_refresh_tokens ---
    op.create_table(
        "platform_refresh_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
            ["session_id"],
            ["platform_sessions.id"],
            name="fk_platform_refresh_tokens_session_id",
            ondelete="CASCADE",
        ),
        comment="SHA-256 hash only — raw token never persisted, mirrors tenant "
        "refresh_tokens (plan.md §3.1)",
    )
    op.create_index(
        "ix_platform_refresh_tokens_session_id",
        "platform_refresh_tokens",
        ["session_id"],
    )

    # --- platform_audit_events ---
    # NOTE: support_access_grant_id references support_access_grants, which is
    # not created until migration 061 — the column is added here nullable
    # WITHOUT its FK, and the FK constraint is added in 061 once the target
    # table exists (same deferred-FK technique migration 055 uses for
    # crm_leads<->crm_opportunities).
    op.create_table(
        "platform_audit_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "actor_platform_administrator_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("action", sa.String(150), nullable=False),
        sa.Column("target_type", sa.String(100), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("before_state", postgresql.JSONB(), nullable=True),
        sa.Column("after_state", postgresql.JSONB(), nullable=True),
        sa.Column("context", postgresql.JSONB(), nullable=True),
        sa.Column(
            "support_access_grant_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
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
            ["actor_platform_administrator_id"],
            ["platform_administrators.id"],
            name="fk_platform_audit_events_actor_id",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_platform_audit_events_company_id",
        ),
        comment="Append-only Platform audit trail (BR-9A-023) — no UPDATE/DELETE "
        "route exists in the router; fail-closed with its mutation (ADR-5)",
    )

    # T014 — FR-9A-200's filter set must not table-scan.
    op.create_index(
        "ix_platform_audit_events_actor_id",
        "platform_audit_events",
        ["actor_platform_administrator_id"],
    )
    op.create_index(
        "ix_platform_audit_events_company_id",
        "platform_audit_events",
        ["company_id"],
    )
    op.create_index(
        "ix_platform_audit_events_action",
        "platform_audit_events",
        ["action"],
    )
    op.create_index(
        "ix_platform_audit_events_created_at",
        "platform_audit_events",
        ["created_at"],
    )

    # --- companies: two additive nullable lifecycle columns (T011) ---
    op.add_column(
        "companies",
        sa.Column("pre_suspension_status", sa.String(20), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("access_invalidated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- T012: mandatory suspended-company preflight guard ---
    # Must run before either CHECK constraint below is created. A
    # pre-existing status='suspended' row has an unrecoverable prior status;
    # fabricating pre_suspension_status for it would make
    # "suspended -> pre-suspension status" non-deterministic (plan.md §33.1).
    conn = op.get_bind()
    suspended = conn.execute(
        sa.text("SELECT id, slug FROM companies WHERE status = 'suspended'")
    ).fetchall()

    if suspended:
        raise RuntimeError(
            f"Migration 057 cannot proceed: {len(suspended)} company row(s) are "
            f"already status='suspended' and have no recoverable "
            f"pre_suspension_status.\n"
            f"Affected: {[row.slug for row in suspended]}\n"
            f"The correct prior lifecycle state cannot be inferred from current "
            f"state and MUST NOT be guessed. Remediate explicitly before "
            f"re-running, e.g. set each row's status back to its true prior "
            f"value ('active' or 'inactive'), or set pre_suspension_status "
            f"explicitly for each row, then re-run this migration."
        )

    # --- T013: the two CHECK constraints on companies ---
    op.create_check_constraint(
        "ck_companies_pre_suspension_status_presence",
        "companies",
        "(status = 'suspended' AND pre_suspension_status IS NOT NULL) OR "
        "(status <> 'suspended' AND pre_suspension_status IS NULL)",
    )
    op.create_check_constraint(
        "ck_companies_pre_suspension_status_domain",
        "companies",
        "pre_suspension_status IS NULL OR pre_suspension_status IN "
        "('active', 'inactive')",
    )


def downgrade() -> None:
    # Preflight has no downgrade counterpart (upgrade-time guard only).
    op.drop_constraint(
        "ck_companies_pre_suspension_status_domain", "companies", type_="check"
    )
    op.drop_constraint(
        "ck_companies_pre_suspension_status_presence", "companies", type_="check"
    )
    op.drop_column("companies", "access_invalidated_at")
    op.drop_column("companies", "pre_suspension_status")

    op.drop_index("ix_platform_audit_events_created_at", "platform_audit_events")
    op.drop_index("ix_platform_audit_events_action", "platform_audit_events")
    op.drop_index("ix_platform_audit_events_company_id", "platform_audit_events")
    op.drop_index("ix_platform_audit_events_actor_id", "platform_audit_events")
    op.drop_table("platform_audit_events")

    op.drop_index("ix_platform_refresh_tokens_session_id", "platform_refresh_tokens")
    op.drop_table("platform_refresh_tokens")

    op.drop_index("ix_platform_sessions_admin_id", "platform_sessions")
    op.drop_table("platform_sessions")

    op.drop_table("platform_admin_role_assignments")
    op.drop_table("platform_role_permissions")
    op.drop_table("platform_permissions")
    op.drop_table("platform_roles")
    op.drop_table("platform_administrators")
