"""Installments RBAC permission check.

Resolves whether a user holds a specific ``installments.*`` permission
code in a company, via the Epic 4 chain: ``CompanyMember`` (user,
company) -> ``role_id`` -> ``RolePermission`` rows -> ``Permission.code``.
Mirrors ``user_has_accounting_permission`` exactly.

Deliberately kept independent of FastAPI's dependency-injection layer
(unlike ``get_current_company_member``) because callers need it *inside*
a service method — e.g. to compare an approver against a contract's
submitter (maker-checker, plan.md §16.2) — not just to gate a whole
route.

Spec ref: specs/010-installments/plan.md §16.1.
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


def user_has_installments_permission(
    db: Session,
    company_id: UUID,
    user_id: UUID | None,
    permission_code: str,
    *,
    user_roles: list[str] | None = None,
) -> bool:
    """Return ``True`` if ``user_id`` holds ``permission_code`` in ``company_id``.

    A platform ``super_admin`` (per ``CurrentUser.roles``) always passes.
    ``user_id=None`` (system-initiated action) never passes — a system
    actor cannot satisfy a human-approval maker-checker requirement.
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
