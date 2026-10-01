"""Reports RBAC permission check.

Resolves whether a user holds a specific ``reports.*`` permission code in
a company, via the Epic 4 chain: ``CompanyMember`` (user, company) ->
``role_id`` -> ``RolePermission`` rows -> ``Permission.code``. Mirrors
``user_has_installments_permission``/``user_has_accounting_permission``
exactly — identical shape/chain, not a shared base class (Constitution §7
DRY is satisfied at the pattern level across modules, per plan.md §11).

Each ``reports.*`` permission is checked independently — no implicit
grants (FR-RPT-240..242); ``.view`` and ``.export`` are always separate
codes, enforced structurally by ``ReportDefinition`` having genuinely
separate ``required_permission``/``export_permission`` fields.

Spec ref: specs/011-reports-analytics/plan.md §11.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)
from modules.users_roles.repositories.role_permission_repository import (
    RolePermissionRepository,
)

_ROLE_SUPER_ADMIN = "super_admin"


def user_has_reports_permission(
    db: Session,
    company_id: UUID,
    user_id: UUID | None,
    permission_code: str,
    *,
    user_roles: list[str] | None = None,
) -> bool:
    """Return ``True`` if ``user_id`` holds ``permission_code`` in ``company_id``.

    A platform ``super_admin`` (per ``CurrentUser.roles``) always passes.
    ``user_id=None`` (system-initiated action) never passes.
    """
    if user_id is None:
        return False
    if user_roles and _ROLE_SUPER_ADMIN in user_roles:
        return True

    member = CompanyMemberRepository(db).get_by_user_id(
        user_id=user_id, company_id=company_id
    )
    if member is None or member.status != "active":
        return False

    role_permissions = RolePermissionRepository(db).get_permissions_for_role(
        member.role_id
    )
    return any(rp.permission_id == permission_code for rp in role_permissions)
