"""Unit tests for RoleService — Phase 5 (US3).

Tests: create custom role, name conflict, rank validation, system role
immutability, custom role limits, delete with active assignments,
deactivation.

Spec reference: tasks T055.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from modules.users_roles.exceptions import (
    CustomRoleLimitExceededError,
    InvalidRoleRankError,
    RoleHasActiveAssignmentsError,
    RoleNameConflictError,
    RoleNotFoundError,
    SystemRoleImmutableError,
)
from modules.users_roles.models.role import Role
from modules.users_roles.services.role_service import RoleService


@dataclass
class _ServiceMocks:
    db: MagicMock
    role_repo: MagicMock
    permission_repo: MagicMock
    role_permission_repo: MagicMock
    member_repo: MagicMock
    audit_service: MagicMock
    outbox_repo: MagicMock


def _make_settings(**overrides):
    """Create a mock Settings object."""
    settings = MagicMock()
    settings.MAX_CUSTOM_ROLES_PER_COMPANY = overrides.get("max_roles", 50)
    return settings


def _make_role(
    *,
    name: str = "Custom Role",
    slug: str = "custom-role",
    rank: int = 30,
    is_system: bool = False,
    is_active: bool = True,
    company_id: uuid.UUID | None = None,
) -> MagicMock:
    """Create a mock Role."""
    role = MagicMock(spec=Role)
    role.id = uuid.uuid4()
    role.company_id = company_id or uuid.uuid4()
    role.name = name
    role.slug = slug
    role.rank = rank
    role.is_system = is_system
    role.is_active = is_active
    role.description = None
    role.created_at = MagicMock()
    role.updated_at = MagicMock()
    return role


def _make_service(
    *,
    existing_role_by_name: MagicMock | None = None,
    existing_role_by_slug: MagicMock | None = None,
    existing_role_by_id: MagicMock | None = None,
    custom_role_count: int = 0,
    active_member_count: int = 0,
    max_roles: int = 50,
    permission_codes_valid: bool = True,
) -> tuple[RoleService, _ServiceMocks]:
    """Create a RoleService with mocked dependencies."""
    db = MagicMock()
    role_repo = MagicMock()
    permission_repo = MagicMock()
    role_permission_repo = MagicMock()
    member_repo = MagicMock()
    audit_service = MagicMock()
    outbox_repo = MagicMock()
    settings = _make_settings(max_roles=max_roles)

    role_repo.get_by_name.return_value = existing_role_by_name
    role_repo.get_by_slug.return_value = existing_role_by_slug
    role_repo.get_by_id_or_none.return_value = existing_role_by_id
    role_repo.count_custom_roles.return_value = custom_role_count
    member_repo.count_by_role.return_value = active_member_count

    if permission_codes_valid:
        # Return mock permissions matching the codes
        def _get_by_codes(codes):
            return [MagicMock(code=c) for c in codes]

        permission_repo.get_by_codes.side_effect = _get_by_codes
    else:
        permission_repo.get_by_codes.return_value = []

    service = RoleService(
        db=db,
        role_repo=role_repo,
        permission_repo=permission_repo,
        role_permission_repo=role_permission_repo,
        member_repo=member_repo,
        audit_service=audit_service,
        outbox_repo=outbox_repo,
        settings=settings,
    )
    return service, _ServiceMocks(
        db=db,
        role_repo=role_repo,
        permission_repo=permission_repo,
        role_permission_repo=role_permission_repo,
        member_repo=member_repo,
        audit_service=audit_service,
        outbox_repo=outbox_repo,
    )


class TestCreateCustomRole:
    """Test custom role creation."""

    def test_create_role_success(self):
        """create_custom_role creates a role with correct fields."""
        service, mocks = _make_service()

        service.create_custom_role(
            company_id=uuid.uuid4(),
            name="Warehouse Supervisor",
            rank=35,
            actor_user_id=uuid.uuid4(),
            permission_codes=["members.read", "roles.read"],
        )

        mocks.db.add.assert_called_once()
        added = mocks.db.add.call_args[0][0]
        assert isinstance(added, Role)
        assert added.name == "Warehouse Supervisor"
        assert added.rank == 35
        assert added.is_system is False

    def test_create_role_writes_audit_log(self):
        """create_custom_role writes ROLE_CREATED audit."""
        service, mocks = _make_service()

        service.create_custom_role(
            company_id=uuid.uuid4(),
            name="Test Role",
            rank=35,
            actor_user_id=uuid.uuid4(),
        )

        mocks.audit_service.record.assert_called_once()
        call_kwargs = mocks.audit_service.record.call_args[1]
        assert call_kwargs["action"] == "ROLE_CREATED"

    def test_create_role_publishes_event(self):
        """create_custom_role publishes a RoleCreatedEvent."""
        service, mocks = _make_service()

        service.create_custom_role(
            company_id=uuid.uuid4(),
            name="Test Role",
            rank=35,
            actor_user_id=uuid.uuid4(),
        )

        mocks.outbox_repo.create.assert_called_once()

    def test_create_role_assigns_permissions(self):
        """create_custom_role assigns permissions via bulk_set."""
        service, mocks = _make_service()
        codes = ["members.read", "roles.read"]

        service.create_custom_role(
            company_id=uuid.uuid4(),
            name="Test Role",
            rank=35,
            actor_user_id=uuid.uuid4(),
            permission_codes=codes,
        )

        mocks.role_permission_repo.bulk_set_permissions_for_role.assert_called_once()


class TestCreateRoleNameConflict:
    """Test name uniqueness enforcement (BR-031)."""

    def test_duplicate_name_raises(self):
        """create_custom_role raises RoleNameConflictError for duplicate name."""
        existing = _make_role(name="Existing Role")
        service, mocks = _make_service(existing_role_by_name=existing)

        with pytest.raises(RoleNameConflictError):
            service.create_custom_role(
                company_id=uuid.uuid4(),
                name="Existing Role",
                rank=35,
                actor_user_id=uuid.uuid4(),
            )


class TestCreateRoleRankValidation:
    """Test rank range and system rank conflict."""

    def test_rank_zero_raises(self):
        """create_custom_role raises InvalidRoleRankError for rank 0."""
        service, mocks = _make_service()

        with pytest.raises(InvalidRoleRankError):
            service.create_custom_role(
                company_id=uuid.uuid4(),
                name="Test",
                rank=0,
                actor_user_id=uuid.uuid4(),
            )

    def test_rank_100_raises(self):
        """create_custom_role raises InvalidRoleRankError for rank 100."""
        service, mocks = _make_service()

        with pytest.raises(InvalidRoleRankError):
            service.create_custom_role(
                company_id=uuid.uuid4(),
                name="Test",
                rank=100,
                actor_user_id=uuid.uuid4(),
            )

    def test_system_rank_conflict_raises(self):
        """create_custom_role raises InvalidRoleRankError for system role rank."""
        service, mocks = _make_service()

        # Rank 80 is Admin system role rank
        with pytest.raises(InvalidRoleRankError):
            service.create_custom_role(
                company_id=uuid.uuid4(),
                name="Test",
                rank=80,
                actor_user_id=uuid.uuid4(),
            )

    def test_valid_rank_succeeds(self):
        """create_custom_role succeeds with non-conflicting rank."""
        service, mocks = _make_service()

        # Rank 35 is not a system rank
        service.create_custom_role(
            company_id=uuid.uuid4(),
            name="Test",
            rank=35,
            actor_user_id=uuid.uuid4(),
        )

        mocks.db.add.assert_called_once()


class TestCreateRoleLimits:
    """Test custom role count limit (FR-048)."""

    def test_limit_exceeded_raises(self):
        """create_custom_role raises CustomRoleLimitExceededError at limit."""
        service, mocks = _make_service(custom_role_count=50, max_roles=50)

        with pytest.raises(CustomRoleLimitExceededError):
            service.create_custom_role(
                company_id=uuid.uuid4(),
                name="One Too Many",
                rank=35,
                actor_user_id=uuid.uuid4(),
            )


class TestUpdateCustomRole:
    """Test custom role update."""

    def test_update_system_role_raises(self):
        """update_custom_role raises SystemRoleImmutableError for system role."""
        system_role = _make_role(is_system=True, name="Admin", slug="admin", rank=80)
        service, mocks = _make_service(existing_role_by_id=system_role)

        with pytest.raises(SystemRoleImmutableError):
            service.update_custom_role(
                company_id=system_role.company_id,
                role_id=system_role.id,
                actor_user_id=uuid.uuid4(),
                name="Renamed Admin",
            )

    def test_update_nonexistent_role_raises(self):
        """update_custom_role raises RoleNotFoundError for unknown role."""
        service, mocks = _make_service(existing_role_by_id=None)

        with pytest.raises(RoleNotFoundError):
            service.update_custom_role(
                company_id=uuid.uuid4(),
                role_id=uuid.uuid4(),
                actor_user_id=uuid.uuid4(),
                name="New Name",
            )

    def test_update_name_changes_slug(self):
        """update_custom_role updates name and regenerates slug."""
        role = _make_role(name="Old Name", slug="old-name")
        # Need to configure slug lookup for conflict check
        service, mocks = _make_service(existing_role_by_id=role)
        mocks.role_repo.get_by_name.return_value = None
        mocks.role_repo.get_by_slug.return_value = None

        service.update_custom_role(
            company_id=role.company_id,
            role_id=role.id,
            actor_user_id=uuid.uuid4(),
            name="New Name",
        )

        assert role.name == "New Name"
        assert role.slug == "new-name"


class TestDeactivateRole:
    """Test role deactivation (FR-047)."""

    def test_deactivate_custom_role(self):
        """deactivate_role sets is_active to False."""
        role = _make_role(is_active=True)
        service, mocks = _make_service(existing_role_by_id=role)

        service.deactivate_role(
            company_id=role.company_id,
            role_id=role.id,
            actor_user_id=uuid.uuid4(),
        )

        assert role.is_active is False

    def test_deactivate_system_role_raises(self):
        """deactivate_role raises SystemRoleImmutableError for system role."""
        role = _make_role(is_system=True)
        service, mocks = _make_service(existing_role_by_id=role)

        with pytest.raises(SystemRoleImmutableError):
            service.deactivate_role(
                company_id=role.company_id,
                role_id=role.id,
                actor_user_id=uuid.uuid4(),
            )


class TestDeleteRole:
    """Test role deletion (FR-046)."""

    def test_delete_with_active_assignments_raises(self):
        """delete_role raises RoleHasActiveAssignmentsError when members assigned."""
        role = _make_role()
        service, mocks = _make_service(existing_role_by_id=role, active_member_count=3)

        with pytest.raises(RoleHasActiveAssignmentsError):
            service.delete_role(
                company_id=role.company_id,
                role_id=role.id,
                actor_user_id=uuid.uuid4(),
            )

    def test_delete_system_role_raises(self):
        """delete_role raises SystemRoleImmutableError for system role."""
        role = _make_role(is_system=True)
        service, mocks = _make_service(existing_role_by_id=role)

        with pytest.raises(SystemRoleImmutableError):
            service.delete_role(
                company_id=role.company_id,
                role_id=role.id,
                actor_user_id=uuid.uuid4(),
            )

    def test_delete_empty_role_succeeds(self):
        """delete_role soft-deletes a role with zero assignments."""
        role = _make_role()
        service, mocks = _make_service(existing_role_by_id=role, active_member_count=0)

        service.delete_role(
            company_id=role.company_id,
            role_id=role.id,
            actor_user_id=uuid.uuid4(),
        )

        assert role.is_deleted is True
        mocks.audit_service.record.assert_called_once()
        call_kwargs = mocks.audit_service.record.call_args[1]
        assert call_kwargs["action"] == "ROLE_DELETED"

    def test_delete_nonexistent_role_raises(self):
        """delete_role raises RoleNotFoundError for unknown role."""
        service, mocks = _make_service(existing_role_by_id=None)

        with pytest.raises(RoleNotFoundError):
            service.delete_role(
                company_id=uuid.uuid4(),
                role_id=uuid.uuid4(),
                actor_user_id=uuid.uuid4(),
            )
