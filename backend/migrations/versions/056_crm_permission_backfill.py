"""CRM permission backfill — Epic 9, Phase 8 (T062).

Backfills the 19 new ``crm.*`` permissions (spec.md §31.1) and their
default role grants (spec.md §31.2) for companies created BEFORE this
epic shipped. New companies already get these via
``RoleSeedService.seed_all()`` at creation time (it reads
``INITIAL_PERMISSIONS``/``DEFAULT_ROLE_PERMISSIONS`` from
``modules/users_roles/constants.py``, which T060/T061 already extended
additively) — this migration exists only to backfill companies whose
roles/permissions were seeded before that constants.py change landed.

**Implementation choice** (tasks.md T062 explicitly asks this to be
documented): a separate, additive ``056`` migration rather than amending
``055``. ``055`` is an already-created, already-reviewed migration from
this epic's own earlier phases (Phase 1/2) — amending a migration file
after the fact, even within the same epic/branch, risks silent drift for
any environment that already applied it. A new additive migration is the
safer choice, matching this codebase's own established convention of
never editing a past migration to fix/extend behavior (e.g. migrations
051-054 each fixed an earlier migration's defect via a NEW migration,
never by editing the original).

**No app-code import** (matches every other migration in this codebase):
this file is pure ``op.execute()`` SQL, not a ``RoleSeedService`` call
from inside the migration — no existing migration in
``migrations/versions/`` imports application modules, and this one
doesn't either. The SQL below is the direct, idempotent equivalent of
what ``RoleSeedService.seed_permissions()``/``seed_role_permissions()``
already do at company-creation time (same target tables, same
``ON CONFLICT DO NOTHING`` idempotency guarantee via the existing
``permissions.id`` primary key and ``role_permissions``'s
``uq_role_permissions_role_permission`` unique constraint — both already
enforce "running this twice produces no duplicate rows" without any
extra guard logic needed here).

``cashier``/``store-keeper`` receive zero grants across all 19 codes
(spec.md §31.2) — no INSERT statements target those two role slugs.

Revision ID: 056
Revises: 055
Create Date: 2026-08-17
"""

from alembic import op
from sqlalchemy import text as sa_text

# revision identifiers, used by Alembic.
revision = "056"
down_revision = "055"
branch_labels = None
depends_on = None


_PERMISSIONS: tuple[tuple[str, str, str, str], ...] = (
    # (code, label, action, description)
    ("crm.leads.view", "View Leads", "read", "View leads"),
    ("crm.leads.create", "Create Leads", "create", "Create leads"),
    (
        "crm.leads.update",
        "Update Leads",
        "update",
        "Update leads, including qualify/disqualify",
    ),
    ("crm.leads.delete", "Delete Leads", "delete", "Soft-delete leads"),
    ("crm.leads.assign", "Assign Leads", "manage", "Reassign lead ownership"),
    ("crm.leads.convert", "Convert Leads", "update", "Convert a qualified lead"),
    (
        "crm.opportunities.view",
        "View Opportunities",
        "read",
        "View opportunities",
    ),
    (
        "crm.opportunities.create",
        "Create Opportunities",
        "create",
        "Create opportunities",
    ),
    (
        "crm.opportunities.update",
        "Update Opportunities",
        "update",
        "Update opportunities, including stage changes",
    ),
    (
        "crm.opportunities.delete",
        "Delete Opportunities",
        "delete",
        "Soft-delete opportunities",
    ),
    (
        "crm.opportunities.assign",
        "Assign Opportunities",
        "manage",
        "Reassign opportunity ownership",
    ),
    (
        "crm.opportunities.close",
        "Close Opportunities",
        "manage",
        "Mark an opportunity WON or LOST",
    ),
    ("crm.activities.view", "View Activities", "read", "View activities"),
    (
        "crm.activities.create",
        "Create Activities",
        "create",
        "Create activities",
    ),
    (
        "crm.activities.update",
        "Update Activities",
        "update",
        "Update/complete activities",
    ),
    (
        "crm.activities.delete",
        "Delete Activities",
        "delete",
        "Soft-delete activities",
    ),
    ("crm.pipeline.view", "View Pipelines", "read", "View pipelines/stages"),
    (
        "crm.pipeline.manage",
        "Manage Pipelines",
        "manage",
        "Create/update/deactivate pipelines and stages",
    ),
    (
        "crm.reports.view",
        "View CRM Reports",
        "read",
        "View CRM reports/KPIs/dashboard",
    ),
)

# Role-slug -> permission codes granted, per spec.md §31.2's Role Access
# Matrix. cashier/store-keeper are intentionally absent (zero grants).
_ROLE_GRANTS: dict[str, tuple[str, ...]] = {
    "owner": tuple(code for code, *_ in _PERMISSIONS),
    "admin": tuple(code for code, *_ in _PERMISSIONS),
    "manager": tuple(
        code for code, *_ in _PERMISSIONS if code != "crm.pipeline.manage"
    ),
    "accountant": (
        "crm.leads.view",
        "crm.opportunities.view",
        "crm.activities.view",
        "crm.pipeline.view",
        "crm.reports.view",
    ),
    "salesperson": (
        "crm.leads.view",
        "crm.leads.create",
        "crm.leads.update",
        "crm.leads.convert",
        "crm.opportunities.view",
        "crm.opportunities.create",
        "crm.opportunities.update",
        "crm.activities.view",
        "crm.activities.create",
        "crm.activities.update",
        "crm.pipeline.view",
    ),
    "viewer": (
        "crm.leads.view",
        "crm.opportunities.view",
        "crm.activities.view",
        "crm.pipeline.view",
        "crm.reports.view",
    ),
}


def upgrade() -> None:
    # 1. Global permission catalog — idempotent via the existing PK on
    #    permissions.id.
    for code, label, action, description in _PERMISSIONS:
        op.execute(
            sa_text(
                "INSERT INTO permissions (id, code, label, module, action, "
                "description) VALUES (:code, :code, :label, 'crm', :action, "
                ":description) ON CONFLICT (id) DO NOTHING"
            ).bindparams(code=code, label=label, action=action, description=description)
        )

    # 2. Per-company role grants — idempotent via the existing unique
    #    constraint uq_role_permissions_role_permission(role_id, permission_id).
    #    Scoped to system roles only (is_system = true), matching
    #    RoleSeedService.seed_role_permissions()'s own scope.
    for role_slug, codes in _ROLE_GRANTS.items():
        for code in codes:
            op.execute(
                sa_text(
                    "INSERT INTO role_permissions (id, role_id, permission_id) "
                    "SELECT gen_random_uuid(), r.id, :code FROM roles r "
                    "WHERE r.slug = :role_slug AND r.is_system = true "
                    "AND r.is_deleted = false "
                    "ON CONFLICT (role_id, permission_id) DO NOTHING"
                ).bindparams(code=code, role_slug=role_slug)
            )


def downgrade() -> None:
    # Reverse order: role grants first (permissions.id has ON DELETE
    # RESTRICT from role_permissions.permission_id).
    op.execute("DELETE FROM role_permissions WHERE permission_id LIKE 'crm.%'")
    op.execute("DELETE FROM permissions WHERE id LIKE 'crm.%'")
