"""Unit tests for RoleSeedService — Phase 3 (US1).

Tests: seeding creates 8 roles, idempotency, permission mapping.

Spec reference: tasks T037.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from modules.users_roles.constants import (
    INITIAL_PERMISSIONS,
    SYSTEM_ROLES,
)
from modules.users_roles.models.permission import Permission
from modules.users_roles.models.role import Role
from modules.users_roles.services.role_seed_service import RoleSeedService


def _make_service(
    *,
    existing_permissions: list[Permission] | None = None,
    existing_role_slugs: list[str] | None = None,
    existing_permission_codes_by_role: dict[str, set[str]] | None = None,
) -> RoleSeedService:
    """Create a RoleSeedService with mocked dependencies."""
    db = MagicMock()
    role_repo = MagicMock()
    permission_repo = MagicMock()
    role_permission_repo = MagicMock()

    # Default: no existing permissions
    existing_perms = existing_permissions or []
    perm_by_code = {p.code: p for p in existing_perms}
    permission_repo.get_by_code.side_effect = lambda code: perm_by_code.get(code)

    # Default: no existing roles
    existing_slugs = set(existing_role_slugs or [])
    role_repo.get_by_slug.side_effect = lambda cid, slug: (
        MagicMock(spec=Role, slug=slug, id=uuid.uuid4())
        if slug in existing_slugs
        else None
    )
    role_repo.get_system_roles.return_value = []

    # Default: no existing role-permission mappings
    codes_by_role = existing_permission_codes_by_role or {}
    role_permission_repo.get_permission_codes_for_role.side_effect = (
        lambda role_id: codes_by_role.get(str(role_id), set())
    )

    return RoleSeedService(
        db=db,
        role_repo=role_repo,
        permission_repo=permission_repo,
        role_permission_repo=role_permission_repo,
    )


class TestSeedPermissions:
    """Test permission seeding."""

    def test_seeds_14_permissions(self):
        """seed_permissions creates every permission in INITIAL_PERMISSIONS.

        Was hardcoded to 14 (the count before Epic 8 added 20 accounting
        permissions in Phase 14, tasks.md T277) — now derived from
        INITIAL_PERMISSIONS itself so it can't go stale again.
        """
        service = _make_service()
        result = service.seed_permissions()

        assert len(result) == len(INITIAL_PERMISSIONS)
        # Verify db.add was called once per permission
        assert service._db.add.call_count == len(INITIAL_PERMISSIONS)

    def test_seed_permissions_idempotent(self):
        """seed_permissions skips existing permissions."""
        # Create mock existing permissions for all of INITIAL_PERMISSIONS
        existing = []
        for perm_def in INITIAL_PERMISSIONS:
            p = MagicMock(spec=Permission)
            p.code = perm_def.code
            p.id = perm_def.code
            existing.append(p)

        service = _make_service(existing_permissions=existing)
        result = service.seed_permissions()

        assert len(result) == len(INITIAL_PERMISSIONS)
        # No new permissions should be added
        assert service._db.add.call_count == 0


class TestSeedRolesForCompany:
    """Test system role seeding."""

    def test_seeds_8_system_roles(self):
        """seed_roles_for_company creates 8 system roles."""
        service = _make_service()
        company_id = uuid.uuid4()
        creator_id = uuid.uuid4()

        result = service.seed_roles_for_company(company_id, creator_id)

        assert len(result) == 8
        # Verify db.add was called for each role
        assert service._db.add.call_count == 8

    def test_seed_roles_idempotent(self):
        """seed_roles_for_company skips existing roles."""
        existing_slugs = [r.slug for r in SYSTEM_ROLES]
        service = _make_service(existing_role_slugs=existing_slugs)

        company_id = uuid.uuid4()
        result = service.seed_roles_for_company(company_id)

        assert len(result) == 8
        # No new roles should be added
        assert service._db.add.call_count == 0

    def test_seed_roles_sets_is_system_true(self):
        """Seeded roles have is_system=True."""
        service = _make_service()
        company_id = uuid.uuid4()

        service.seed_roles_for_company(company_id)

        for add_call in service._db.add.call_args_list:
            role = add_call[0][0]
            if isinstance(role, Role):
                assert role.is_system is True

    def test_seed_roles_correct_ranks(self):
        """Seeded roles have correct ranks from constants."""
        service = _make_service()
        company_id = uuid.uuid4()

        service.seed_roles_for_company(company_id)

        added_roles = [
            c[0][0] for c in service._db.add.call_args_list if isinstance(c[0][0], Role)
        ]
        ranks = {r.slug: r.rank for r in added_roles}
        assert ranks["owner"] == 100
        assert ranks["admin"] == 80
        assert ranks["manager"] == 60
        assert ranks["viewer"] == 20


class TestSeedRolePermissions:
    """Test role-permission mapping."""

    def test_seeds_permission_mappings(self):
        """seed_role_permissions creates mappings from the matrix."""
        service = _make_service()
        company_id = uuid.uuid4()

        # Set up system roles to be returned
        mock_roles = []
        for role_def in SYSTEM_ROLES:
            mock_role = MagicMock(spec=Role)
            mock_role.id = uuid.uuid4()
            mock_role.slug = role_def.slug
            mock_roles.append(mock_role)

        service._role_repo.get_system_roles.return_value = mock_roles

        service.seed_role_permissions(company_id)

        # Should have added permission mappings
        assert service._db.add.call_count > 0
