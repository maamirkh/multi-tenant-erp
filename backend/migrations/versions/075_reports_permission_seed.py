"""Reports permission seed — Epic 11, Phase 1 (T036).

Backfills the 16 new ``reports.*`` permissions (spec §33) for companies
created BEFORE this epic shipped. New companies already get these via
``RoleSeedService.seed_all()`` at creation time once Phase 0 landed
``reports.*`` in ``modules/users_roles/constants.py``'s
``INITIAL_PERMISSIONS`` — this migration exists only to backfill the
global permission catalog for companies whose roles/permissions were
seeded before that constants.py change lands.

**No role grants** (deliberate deviation from
``071_installments_permission_backfill.py``'s precedent, which also
inserted default ``role_permissions`` rows): FR-RPT-243 requires Epic 11
to hardcode **no** default role mapping for ``reports.*`` — role-to-
permission assignment for Reports remains fully tenant-configurable via
the existing RBAC UI from day one (`modules/users_roles/constants.py`'s
``DEFAULT_ROLE_PERMISSIONS`` deliberately excludes every ``reports.*``
code for the identical reason). This migration therefore only seeds the
global ``permissions`` catalog — never ``role_permissions``.

**No app-code import** (matches every other migration in this codebase):
pure ``op.execute()`` SQL, idempotent via the existing ``permissions.id``
primary key.

**Renumbered per explicit correction (2026-09-12)**: originally candidate
``073`` in plan.md §16/tasks.md T036; shifted to ``075`` because Phase 0's
``073_reports_foundation.py`` and this epic's own ``074_reports_
capability_seed.py`` both precede it.

Revision ID: 075
Revises: 074
Create Date: 2026-09-12
"""

from alembic import op
from sqlalchemy import text as sa_text

# revision identifiers, used by Alembic.
revision = "075"
down_revision = "074"
branch_labels = None
depends_on = None


_PERMISSIONS: tuple[tuple[str, str, str, str], ...] = (
    # (code, label, action, description)
    (
        "reports.executive.view",
        "View Executive Dashboard",
        "read",
        "View the Executive Dashboard",
    ),
    (
        "reports.sales.view",
        "View Sales Analytics",
        "read",
        "View Sales analytics reports",
    ),
    (
        "reports.sales.export",
        "Export Sales Analytics",
        "export",
        "Export Sales analytics reports",
    ),
    (
        "reports.purchase.view",
        "View Purchase Analytics",
        "read",
        "View Purchase analytics reports",
    ),
    (
        "reports.purchase.export",
        "Export Purchase Analytics",
        "export",
        "Export Purchase analytics reports",
    ),
    (
        "reports.inventory.view",
        "View Inventory Analytics",
        "read",
        "View Inventory analytics reports",
    ),
    (
        "reports.inventory.export",
        "Export Inventory Analytics",
        "export",
        "Export Inventory analytics reports",
    ),
    (
        "reports.accounting.view",
        "View Financial Reports",
        "read",
        "View financial reports",
    ),
    (
        "reports.accounting.export",
        "Export Financial Reports",
        "export",
        "Export financial reports",
    ),
    (
        "reports.crm.view",
        "View CRM Analytics",
        "read",
        "View CRM analytics reports",
    ),
    (
        "reports.crm.export",
        "Export CRM Analytics",
        "export",
        "Export CRM analytics reports",
    ),
    (
        "reports.installments.view",
        "View Installment Analytics",
        "read",
        "View Installment analytics reports",
    ),
    (
        "reports.installments.export",
        "Export Installment Analytics",
        "export",
        "Export Installment analytics reports",
    ),
    (
        "reports.customer_360.view",
        "View Customer 360 Financial View",
        "read",
        "View the cross-module Customer 360 Financial View",
    ),
    (
        "reports.branch_performance.view",
        "View Branch Performance Summary",
        "read",
        "View the (deferred) Branch Performance Summary",
    ),
    (
        "reports.saved_view.manage",
        "Manage Own Saved Report Views",
        "manage",
        "Create/edit/delete one's own private saved report views",
    ),
)


def upgrade() -> None:
    for code, label, action, description in _PERMISSIONS:
        op.execute(
            sa_text(
                "INSERT INTO permissions (id, code, label, module, action, "
                "description) VALUES (:code, :code, :label, 'reports', "
                ":action, :description) ON CONFLICT (id) DO NOTHING"
            ).bindparams(code=code, label=label, action=action, description=description)
        )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission_id LIKE 'reports.%'")
    op.execute("DELETE FROM permissions WHERE id LIKE 'reports.%'")
