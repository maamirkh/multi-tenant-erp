"""Users & Roles test fixtures — factory functions for test data.

Used by unit and integration test suites that need members, roles,
and permissions in the test database.

Spec reference: tasks T035.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from modules.users_roles.models.company_member import CompanyMember
from modules.users_roles.models.enums import MembershipStatus
from modules.users_roles.models.permission import Permission
from modules.users_roles.models.role import Role
from modules.users_roles.models.role_permission import RolePermission
from modules.users_roles.repositories.permission_repository import (
    PermissionRepository,
)
from modules.users_roles.repositories.role_permission_repository import (
    RolePermissionRepository,
)
from modules.users_roles.repositories.role_repository import RoleRepository
from modules.users_roles.services.role_seed_service import RoleSeedService


def seed_system_roles(
    db: Session,
    company_id: UUID,
    created_by: UUID | None = None,
) -> list[Role]:
    """Seed all 8 system roles and 14 permissions for a company.

    Returns:
        List of seeded system Role records.
    """
    role_repo = RoleRepository(db)
    permission_repo = PermissionRepository(db)
    role_permission_repo = RolePermissionRepository(db)
    seed_service = RoleSeedService(
        db=db,
        role_repo=role_repo,
        permission_repo=permission_repo,
        role_permission_repo=role_permission_repo,
    )
    return seed_service.seed_all(company_id, created_by)


def create_test_role(
    db: Session,
    company_id: UUID,
    *,
    name: str = "Test Role",
    slug: str = "test-role",
    rank: int = 50,
    is_system: bool = False,
    is_active: bool = True,
    created_by: UUID | None = None,
) -> Role:
    """Create a single role in the test database."""
    role = Role(
        company_id=company_id,
        name=name,
        slug=slug,
        rank=rank,
        is_system=is_system,
        is_active=is_active,
        created_by=created_by,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def create_test_permission(
    db: Session,
    *,
    code: str = "test.permission",
    label: str = "Test Permission",
    module: str = "test",
    action: str = "read",
    description: str = "A test permission",
) -> Permission:
    """Create a single permission in the test database."""
    existing = PermissionRepository(db).get_by_code(code)
    if existing is not None:
        return existing

    permission = Permission(
        id=code,
        code=code,
        label=label,
        module=module,
        action=action,
        description=description,
    )
    db.add(permission)
    db.commit()
    db.refresh(permission)
    return permission


def create_test_member(
    db: Session,
    *,
    company_id: UUID,
    user_id: UUID,
    role_id: UUID,
    status: str = MembershipStatus.active.value,
    employee_id: str | None = None,
    job_title: str | None = None,
    department: str | None = None,
    invited_by: UUID | None = None,
    created_by: UUID | None = None,
) -> CompanyMember:
    """Create a company member in the test database.

    Idempotent: if a membership record (including soft-deleted) already exists
    for the given ``(company_id, user_id)`` pair, the existing record is returned
    after updating its ``role_id`` and ``status`` to the requested values.  This
    ensures that tests remain compatible with the T129 bootstrap that
    automatically creates an active Owner membership when a company is created.
    """
    from sqlalchemy import select

    stmt = (
        select(CompanyMember)
        .where(CompanyMember.company_id == company_id)
        .where(CompanyMember.user_id == user_id)
    )
    existing = db.execute(stmt).scalars().one_or_none()
    if existing is not None:
        # Update to the requested role/status so the caller's intent is fulfilled.
        existing.role_id = role_id
        existing.status = status
        if employee_id is not None:
            existing.employee_id = employee_id
        if job_title is not None:
            existing.job_title = job_title
        if department is not None:
            existing.department = department
        db.commit()
        db.refresh(existing)
        return existing

    member = CompanyMember(
        company_id=company_id,
        user_id=user_id,
        role_id=role_id,
        status=status,
        employee_id=employee_id,
        job_title=job_title,
        department=department,
        invited_by=invited_by,
        created_by=created_by,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def create_member_with_role(
    db: Session,
    *,
    company_id: UUID,
    user_id: UUID,
    role_slug: str = "viewer",
    status: str = MembershipStatus.active.value,
) -> tuple[CompanyMember, Role]:
    """Create a member with a specific system role.

    Assumes system roles are already seeded for the company.

    Returns:
        Tuple of (CompanyMember, Role).
    """
    role_repo = RoleRepository(db)
    role = role_repo.get_by_slug(company_id, role_slug)
    if role is None:
        raise ValueError(
            f"System role '{role_slug}' not found for company {company_id}. "
            "Did you call seed_system_roles() first?"
        )

    member = create_test_member(
        db,
        company_id=company_id,
        user_id=user_id,
        role_id=role.id,
        status=status,
    )
    return member, role


def grant_permission_to_user(
    db: Session,
    *,
    company_id: UUID,
    user_id: UUID,
    permission_code: str,
    role_slug: str = "test-approver-role",
) -> CompanyMember:
    """Create a permission + a single-permission role + an active membership
    granting ``permission_code`` to ``user_id`` in ``company_id``.

    Standalone helper for tests that need a specific accounting SoD/RBAC
    permission (e.g. ``accounting.journal.approve``) without seeding the
    full 8-role/20+-permission system-role matrix. Idempotent for repeated
    calls with the same ``role_slug`` within a test (see ``create_test_role``
    and ``create_test_member``); each call still adds a fresh
    ``RolePermission`` row when the role is newly created.
    """
    permission = create_test_permission(
        db,
        code=permission_code,
        label=permission_code,
        module=permission_code.split(".")[0],
        action=permission_code.split(".")[-1],
    )
    role = create_test_role(
        db,
        company_id,
        name=role_slug,
        slug=role_slug,
        is_system=False,
    )
    db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    db.commit()
    return create_test_member(
        db,
        company_id=company_id,
        user_id=user_id,
        role_id=role.id,
    )
