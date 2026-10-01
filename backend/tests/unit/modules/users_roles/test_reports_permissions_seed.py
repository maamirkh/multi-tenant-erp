"""T013 — ``RoleSeedService.seed_permissions()`` grants exactly 16
``reports.*`` permission codes to a new company.

Spec ref: specs/011-reports-analytics/spec.md §33, plan.md §11.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from modules.users_roles.constants import REPORTS_PERMISSIONS
from modules.users_roles.repositories.permission_repository import (
    PermissionRepository,
)
from modules.users_roles.repositories.role_permission_repository import (
    RolePermissionRepository,
)
from modules.users_roles.repositories.role_repository import RoleRepository
from modules.users_roles.services.role_seed_service import RoleSeedService


def test_reports_permissions_constant_has_exactly_16_codes() -> None:
    assert len(REPORTS_PERMISSIONS) == 16
    codes = {p.code for p in REPORTS_PERMISSIONS}
    assert len(codes) == 16  # no duplicates
    assert all(code.startswith("reports.") for code in codes)


def test_seed_permissions_creates_all_16_reports_codes(db_session: Session) -> None:
    service = RoleSeedService(
        db=db_session,
        role_repo=RoleRepository(db_session),
        permission_repo=PermissionRepository(db_session),
        role_permission_repo=RolePermissionRepository(db_session),
    )

    seeded = service.seed_permissions()
    seeded_codes = {p.code for p in seeded}

    expected_codes = {p.code for p in REPORTS_PERMISSIONS}
    assert expected_codes.issubset(seeded_codes)


def test_seed_permissions_is_idempotent_for_reports_codes(
    db_session: Session,
) -> None:
    service = RoleSeedService(
        db=db_session,
        role_repo=RoleRepository(db_session),
        permission_repo=PermissionRepository(db_session),
        role_permission_repo=RolePermissionRepository(db_session),
    )

    service.seed_permissions()
    second_pass = service.seed_permissions()

    reports_codes = [p.code for p in second_pass if p.code.startswith("reports.")]
    assert len(reports_codes) == 16
    assert len(set(reports_codes)) == 16
