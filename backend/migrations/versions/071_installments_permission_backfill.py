"""Installments permission backfill — Epic 10, Phase 0 (T010).

Backfills the 16 new ``installments.*`` permissions (plan.md §16.1) and
their default role grants (plan.md §30.1) for companies created BEFORE
this epic shipped. New companies already get these via
``RoleSeedService.seed_all()`` at creation time once T015/T016 land
``installments.*`` in ``modules/users_roles/constants.py``'s
``INITIAL_PERMISSIONS``/``DEFAULT_ROLE_PERMISSIONS`` — this migration
exists only to backfill companies whose roles/permissions were seeded
before that constants.py change lands.

**Mandatory, not conditional** (plan.md §30.1's explicit correction):
`RoleSeedService.seed_all()` reads `constants.py` only at company-creation
time — there is no retroactive re-seed trigger anywhere in the codebase,
so an existing company would otherwise never receive these permissions.
This is the identical fact pattern ``056_crm_permission_backfill.py`` was
written to solve.

**Deliberate deviation from CRM's zero-grant precedent for
cashier/store-keeper**: CRM granted zero permissions to both roles.
Installments' spec explicitly names Cashier/Collector as an actor who
records collections (spec §4), so ``cashier`` receives
``contract.view``/``collection.create`` here; ``store-keeper`` remains at
zero grants (no relevance to Installments, matching CRM's own precedent
for that role).

**No app-code import** (matches every other migration in this codebase):
pure ``op.execute()`` SQL, idempotent via the existing ``permissions.id``
primary key and ``role_permissions``' ``uq_role_permissions_role_permission``
unique constraint. Scoped ``WHERE r.is_system = true`` — no custom
(tenant-defined) role receives any new grant automatically, and no
existing permission is ever removed or reset (only ever INSERTs).

Revision ID: 071
Revises: 070
Create Date: 2026-08-25
"""

from alembic import op
from sqlalchemy import text as sa_text

# revision identifiers, used by Alembic.
revision = "071"
down_revision = "070"
branch_labels = None
depends_on = None


_PERMISSIONS: tuple[tuple[str, str, str, str], ...] = (
    # (code, label, action, description)
    (
        "installments.config.manage",
        "Manage Installments Configuration",
        "manage",
        "Configure tenant-level installment policy",
    ),
    (
        "installments.plan.manage",
        "Manage Installment Plan Templates",
        "manage",
        "Create/edit/deactivate installment plan templates",
    ),
    (
        "installments.contract.view",
        "View Installment Contracts",
        "read",
        "View installment contracts and schedules",
    ),
    (
        "installments.contract.create",
        "Create Installment Contracts",
        "create",
        "Create a draft installment contract / quote",
    ),
    (
        "installments.contract.approve",
        "Approve Installment Contracts",
        "manage",
        "Approve a submitted installment contract",
    ),
    (
        "installments.contract.activate",
        "Activate Installment Contracts",
        "manage",
        "Activate an approved installment contract",
    ),
    (
        "installments.collection.create",
        "Record Installment Collections",
        "create",
        "Record an installment collection",
    ),
    (
        "installments.collection.reverse",
        "Reverse Installment Collections",
        "manage",
        "Reverse a recorded installment collection",
    ),
    (
        "installments.charge.waive",
        "Waive Late Charges",
        "manage",
        "Waive an installment late charge",
    ),
    (
        "installments.contract.reschedule",
        "Reschedule Installment Contracts",
        "manage",
        "Controlled due-date amendment of an installment schedule",
    ),
    (
        "installments.contract.cancel",
        "Cancel Installment Contracts",
        "manage",
        "Cancel an installment contract",
    ),
    (
        "installments.contract.default",
        "Mark Installment Contracts Defaulted",
        "manage",
        "Mark an installment contract as defaulted",
    ),
    (
        "installments.contract.cure",
        "Cure Defaulted Installment Contracts",
        "manage",
        "Restore a defaulted installment contract to active",
    ),
    (
        "installments.contract.writeoff",
        "Write Off Installment Contracts",
        "manage",
        "Write off a defaulted installment balance",
    ),
    (
        "installments.settlement.execute",
        "Execute Installment Settlements",
        "manage",
        "Generate/execute an early installment settlement",
    ),
    (
        "installments.report.view",
        "View Installment Reports",
        "read",
        "View installment reports/dashboards",
    ),
)

# Role-slug -> permission codes granted, per plan.md §30.1's exact table.
# store-keeper is intentionally absent (zero grants).
_ROLE_GRANTS: dict[str, tuple[str, ...]] = {
    "owner": tuple(code for code, *_ in _PERMISSIONS),
    "admin": tuple(code for code, *_ in _PERMISSIONS),
    "manager": (
        "installments.contract.view",
        "installments.contract.approve",
        "installments.contract.reschedule",
        "installments.contract.cancel",
        "installments.contract.default",
        "installments.contract.writeoff",
        "installments.charge.waive",
        "installments.settlement.execute",
        "installments.contract.cure",
        "installments.report.view",
    ),
    "accountant": (
        "installments.contract.view",
        "installments.collection.reverse",
        "installments.settlement.execute",
        "installments.report.view",
    ),
    "salesperson": (
        "installments.contract.view",
        "installments.contract.create",
        "installments.plan.manage",
    ),
    "cashier": (
        "installments.contract.view",
        "installments.collection.create",
    ),
    "viewer": (
        "installments.contract.view",
        "installments.report.view",
    ),
}


def upgrade() -> None:
    # 1. Global permission catalog — idempotent via the existing PK on
    #    permissions.id.
    for code, label, action, description in _PERMISSIONS:
        op.execute(
            sa_text(
                "INSERT INTO permissions (id, code, label, module, action, "
                "description) VALUES (:code, :code, :label, 'installments', "
                ":action, :description) ON CONFLICT (id) DO NOTHING"
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
    op.execute("DELETE FROM role_permissions WHERE permission_id LIKE 'installments.%'")
    op.execute("DELETE FROM permissions WHERE id LIKE 'installments.%'")
