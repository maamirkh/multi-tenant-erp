"""Unit tests for MemberService — Phase 3 (US1), Phase 4 (US2), Phase 7 (US5).

Tests: add_member happy path, duplicate membership, limit exceeded,
archived reactivation, rank enforcement.
Tests: change_role happy path, rank enforcement, self-change prevention,
last Owner protection, role not found.
Tests: lifecycle state machine (deactivate, reactivate, suspend, lock,
archive, restore), invalid transitions, last Owner protection, session
revocation.

Spec reference: tasks T036, T046, T073.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from modules.users_roles.exceptions import (
    CannotModifyOwnRoleError,
    InsufficientRankError,
    InvalidStatusTransitionError,
    LastOwnerProtectionError,
    MemberAlreadyExistsError,
    MemberLimitExceededError,
    MemberNotFoundError,
    RoleNotFoundError,
)
from modules.users_roles.models.company_member import CompanyMember
from modules.users_roles.models.enums import MembershipStatus
from modules.users_roles.models.role import Role
from modules.users_roles.services.member_service import MemberService


def _make_settings(**overrides):
    """Create a mock Settings object."""
    settings = MagicMock()
    settings.COMPANY_MAX_MEMBERS = overrides.get("max_members", 100)
    settings.INVITATION_EXPIRY_DAYS = overrides.get("invitation_expiry_days", 7)
    return settings


def _make_role(rank: int = 50, name: str = "Viewer", slug: str = "viewer") -> MagicMock:
    """Create a mock Role."""
    role = MagicMock(spec=Role)
    role.id = uuid.uuid4()
    role.rank = rank
    role.name = name
    role.slug = slug
    role.is_system = True
    role.is_active = True
    return role


def _make_service(
    *,
    member_count: int = 0,
    existing_member: CompanyMember | None = None,
    role: MagicMock | None = None,
    max_members: int = 100,
) -> MemberService:
    """Create a MemberService with mocked dependencies."""
    db = MagicMock()
    member_repo = MagicMock()
    role_repo = MagicMock()
    audit_service = MagicMock()
    outbox_repo = MagicMock()
    settings = _make_settings(max_members=max_members)

    member_repo.count_by_company.return_value = member_count
    member_repo.get_by_company_and_user.return_value = existing_member

    if role is not None:
        role_repo.get_by_id_or_none.return_value = role
    else:
        role_repo.get_by_id_or_none.return_value = None

    service = MemberService(
        db=db,
        member_repo=member_repo,
        role_repo=role_repo,
        audit_service=audit_service,
        outbox_repo=outbox_repo,
        settings=settings,
    )
    return service


class TestAddMemberHappyPath:
    """Test successful member creation."""

    def test_add_member_creates_record(self):
        """add_member creates a CompanyMember with correct fields."""
        role = _make_role(rank=20)
        service = _make_service(role=role)

        company_id = uuid.uuid4()
        user_id = uuid.uuid4()
        actor_id = uuid.uuid4()

        member = service.add_member(
            company_id=company_id,
            user_id=user_id,
            role_id=role.id,
            actor_user_id=actor_id,
            actor_role_rank=80,  # Admin rank
        )

        # Verify db.add was called with a CompanyMember
        service._db.add.assert_called_once()
        added_entity = service._db.add.call_args[0][0]
        assert isinstance(added_entity, CompanyMember)
        assert added_entity.company_id == company_id
        assert added_entity.user_id == user_id
        assert added_entity.role_id == role.id
        assert added_entity.status == MembershipStatus.pending_invitation.value

    def test_add_member_writes_audit_log(self):
        """add_member calls audit_service.record with MEMBER_CREATED."""
        role = _make_role(rank=20)
        service = _make_service(role=role)

        service.add_member(
            company_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role_id=role.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=80,
        )

        service._audit_service.record.assert_called_once()
        call_kwargs = service._audit_service.record.call_args[1]
        assert call_kwargs["action"] == "MEMBER_CREATED"

    def test_add_member_publishes_event(self):
        """add_member writes a MemberCreatedEvent to the outbox."""
        role = _make_role(rank=20)
        service = _make_service(role=role)

        service.add_member(
            company_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role_id=role.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=80,
        )

        service._outbox_repo.create.assert_called_once()

    def test_add_member_commits_transaction(self):
        """add_member commits the database transaction."""
        role = _make_role(rank=20)
        service = _make_service(role=role)

        service.add_member(
            company_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role_id=role.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=80,
        )

        service._db.commit.assert_called()

    def test_add_member_with_employee_fields(self):
        """add_member passes employee fields to the CompanyMember."""
        role = _make_role(rank=20)
        service = _make_service(role=role)

        service.add_member(
            company_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role_id=role.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=80,
            employee_id="EMP-001",
            job_title="Developer",
            department="Engineering",
        )

        added_entity = service._db.add.call_args[0][0]
        assert added_entity.employee_id == "EMP-001"
        assert added_entity.job_title == "Developer"
        assert added_entity.department == "Engineering"


class TestAddMemberDuplicate:
    """Test duplicate membership prevention."""

    def test_duplicate_active_member_raises(self):
        """add_member raises MemberAlreadyExistsError for active duplicate."""
        existing = MagicMock(spec=CompanyMember)
        existing.status = MembershipStatus.active.value
        existing.is_deleted = False

        service = _make_service(existing_member=existing)

        with pytest.raises(MemberAlreadyExistsError):
            service.add_member(
                company_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                role_id=uuid.uuid4(),
                actor_user_id=uuid.uuid4(),
                actor_role_rank=80,
            )

    def test_duplicate_pending_member_raises(self):
        """add_member raises MemberAlreadyExistsError for pending duplicate."""
        existing = MagicMock(spec=CompanyMember)
        existing.status = MembershipStatus.pending_invitation.value
        existing.is_deleted = False

        service = _make_service(existing_member=existing)

        with pytest.raises(MemberAlreadyExistsError):
            service.add_member(
                company_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                role_id=uuid.uuid4(),
                actor_user_id=uuid.uuid4(),
                actor_role_rank=80,
            )


class TestAddMemberLimitExceeded:
    """Test membership count limit enforcement."""

    def test_limit_exceeded_raises(self):
        """add_member raises MemberLimitExceededError at limit."""
        service = _make_service(member_count=100, max_members=100)

        with pytest.raises(MemberLimitExceededError):
            service.add_member(
                company_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                role_id=uuid.uuid4(),
                actor_user_id=uuid.uuid4(),
                actor_role_rank=80,
            )


class TestAddMemberArchivedReactivation:
    """Test archived member reactivation (BR-044)."""

    def test_archived_member_reactivated(self):
        """add_member reactivates an archived membership."""
        role = _make_role(rank=20)
        existing = MagicMock(spec=CompanyMember)
        existing.status = MembershipStatus.archived.value
        existing.is_deleted = True
        existing.company_id = uuid.uuid4()
        existing.user_id = uuid.uuid4()
        existing.id = uuid.uuid4()

        service = _make_service(existing_member=existing, role=role)

        result = service.add_member(
            company_id=existing.company_id,
            user_id=existing.user_id,
            role_id=role.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=80,
        )

        # Verify the archived member was reactivated
        assert existing.status == MembershipStatus.pending_invitation.value
        assert existing.is_deleted is False
        assert existing.deleted_at is None
        assert existing.role_id == role.id


class TestAddMemberRankEnforcement:
    """Test rank hierarchy enforcement (BR-011)."""

    def test_equal_rank_raises(self):
        """add_member raises InsufficientRankError when actor rank == target rank."""
        role = _make_role(rank=80)
        service = _make_service(role=role)

        with pytest.raises(InsufficientRankError):
            service.add_member(
                company_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                role_id=role.id,
                actor_user_id=uuid.uuid4(),
                actor_role_rank=80,  # Same as target role
            )

    def test_lower_rank_raises(self):
        """add_member raises InsufficientRankError when actor rank < target rank."""
        role = _make_role(rank=80)
        service = _make_service(role=role)

        with pytest.raises(InsufficientRankError):
            service.add_member(
                company_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                role_id=role.id,
                actor_user_id=uuid.uuid4(),
                actor_role_rank=60,  # Lower than target
            )

    def test_higher_rank_succeeds(self):
        """add_member succeeds when actor rank > target rank."""
        role = _make_role(rank=20)
        service = _make_service(role=role)

        # Should not raise
        service.add_member(
            company_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role_id=role.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=80,
        )


class TestAddMemberRoleNotFound:
    """Test role validation."""

    def test_invalid_role_raises(self):
        """add_member raises RoleNotFoundError for non-existent role."""
        service = _make_service(role=None)

        with pytest.raises(RoleNotFoundError):
            service.add_member(
                company_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                role_id=uuid.uuid4(),
                actor_user_id=uuid.uuid4(),
                actor_role_rank=80,
            )


# ═══════════════════════════════════════════════════════════════════════════
# Phase 4 (US2): change_role tests — T046
# ═══════════════════════════════════════════════════════════════════════════


def _make_member(
    *,
    company_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    role_id: uuid.UUID | None = None,
    status: str = "active",
) -> MagicMock:
    """Create a mock CompanyMember."""
    member = MagicMock(spec=CompanyMember)
    member.id = uuid.uuid4()
    member.company_id = company_id or uuid.uuid4()
    member.user_id = user_id or uuid.uuid4()
    member.role_id = role_id or uuid.uuid4()
    member.status = status
    return member


def _make_change_role_service(
    *,
    target_member: MagicMock | None = None,
    current_role: MagicMock | None = None,
    new_role: MagicMock | None = None,
    owner_count: int = 2,
) -> MemberService:
    """Create a MemberService wired for change_role tests."""
    db = MagicMock()
    member_repo = MagicMock()
    role_repo = MagicMock()
    audit_service = MagicMock()
    outbox_repo = MagicMock()
    settings = _make_settings()

    member_repo.get_by_id_or_none.return_value = target_member
    member_repo.count_owners.return_value = owner_count

    # role_repo.get_by_id_or_none returns current_role for the first call
    # and new_role for the second call
    def _role_lookup(id, company_id):
        if target_member and id == target_member.role_id:
            return current_role
        return new_role

    role_repo.get_by_id_or_none.side_effect = _role_lookup

    return MemberService(
        db=db,
        member_repo=member_repo,
        role_repo=role_repo,
        audit_service=audit_service,
        outbox_repo=outbox_repo,
        settings=settings,
    )


class TestChangeRoleHappyPath:
    """Test successful role change."""

    def test_change_role_updates_role_id(self):
        """change_role updates the member's role_id."""
        current_role = _make_role(rank=20, name="Viewer", slug="viewer")
        new_role = _make_role(rank=60, name="Manager", slug="manager")
        member = _make_member(role_id=current_role.id)

        service = _make_change_role_service(
            target_member=member,
            current_role=current_role,
            new_role=new_role,
        )

        service.change_role(
            company_id=member.company_id,
            member_id=member.id,
            new_role_id=new_role.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=100,  # Owner rank
        )

        assert member.role_id == new_role.id

    def test_change_role_writes_audit_log(self):
        """change_role writes MEMBER_ROLE_CHANGED audit with before/after."""
        current_role = _make_role(rank=20, name="Viewer", slug="viewer")
        new_role = _make_role(rank=50, name="Salesperson", slug="salesperson")
        member = _make_member(role_id=current_role.id)

        service = _make_change_role_service(
            target_member=member,
            current_role=current_role,
            new_role=new_role,
        )

        service.change_role(
            company_id=member.company_id,
            member_id=member.id,
            new_role_id=new_role.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=100,
        )

        service._audit_service.record.assert_called_once()
        call_kwargs = service._audit_service.record.call_args[1]
        assert call_kwargs["action"] == "MEMBER_ROLE_CHANGED"
        assert call_kwargs["before_state"]["role_id"] == str(current_role.id)
        assert call_kwargs["after_state"]["role_id"] == str(new_role.id)

    def test_change_role_publishes_event(self):
        """change_role publishes a MemberRoleChangedEvent."""
        current_role = _make_role(rank=20, name="Viewer", slug="viewer")
        new_role = _make_role(rank=50, name="Salesperson", slug="salesperson")
        member = _make_member(role_id=current_role.id)

        service = _make_change_role_service(
            target_member=member,
            current_role=current_role,
            new_role=new_role,
        )

        service.change_role(
            company_id=member.company_id,
            member_id=member.id,
            new_role_id=new_role.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=100,
        )

        service._outbox_repo.create.assert_called_once()

    def test_change_role_commits(self):
        """change_role commits the transaction."""
        current_role = _make_role(rank=20, name="Viewer", slug="viewer")
        new_role = _make_role(rank=50, name="Salesperson", slug="salesperson")
        member = _make_member(role_id=current_role.id)

        service = _make_change_role_service(
            target_member=member,
            current_role=current_role,
            new_role=new_role,
        )

        service.change_role(
            company_id=member.company_id,
            member_id=member.id,
            new_role_id=new_role.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=100,
        )

        service._db.commit.assert_called()


class TestChangeRoleSelfPrevention:
    """Test self-role-change prevention (BR-013)."""

    def test_self_role_change_raises(self):
        """change_role raises CannotModifyOwnRoleError for self-change."""
        actor_id = uuid.uuid4()
        current_role = _make_role(rank=80, name="Admin", slug="admin")
        new_role = _make_role(rank=60, name="Manager", slug="manager")
        member = _make_member(user_id=actor_id, role_id=current_role.id)

        service = _make_change_role_service(
            target_member=member,
            current_role=current_role,
            new_role=new_role,
        )

        with pytest.raises(CannotModifyOwnRoleError):
            service.change_role(
                company_id=member.company_id,
                member_id=member.id,
                new_role_id=new_role.id,
                actor_user_id=actor_id,
                actor_role_rank=80,
            )


class TestChangeRoleRankEnforcement:
    """Test rank hierarchy enforcement for role change (BR-011)."""

    def test_actor_rank_below_target_current_rank_raises(self):
        """change_role raises InsufficientRankError when actor rank <= target's current rank."""
        current_role = _make_role(rank=80, name="Admin", slug="admin")
        new_role = _make_role(rank=20, name="Viewer", slug="viewer")
        member = _make_member(role_id=current_role.id)

        service = _make_change_role_service(
            target_member=member,
            current_role=current_role,
            new_role=new_role,
        )

        with pytest.raises(InsufficientRankError):
            service.change_role(
                company_id=member.company_id,
                member_id=member.id,
                new_role_id=new_role.id,
                actor_user_id=uuid.uuid4(),
                actor_role_rank=60,  # Lower than target's 80
            )

    def test_actor_rank_below_new_role_rank_raises(self):
        """change_role raises InsufficientRankError when actor rank <= new role rank."""
        current_role = _make_role(rank=20, name="Viewer", slug="viewer")
        new_role = _make_role(rank=80, name="Admin", slug="admin")
        member = _make_member(role_id=current_role.id)

        service = _make_change_role_service(
            target_member=member,
            current_role=current_role,
            new_role=new_role,
        )

        with pytest.raises(InsufficientRankError):
            service.change_role(
                company_id=member.company_id,
                member_id=member.id,
                new_role_id=new_role.id,
                actor_user_id=uuid.uuid4(),
                actor_role_rank=60,  # Lower than new role's 80
            )

    def test_equal_rank_to_target_raises(self):
        """change_role raises InsufficientRankError when actor rank == target's rank."""
        current_role = _make_role(rank=60, name="Manager", slug="manager")
        new_role = _make_role(rank=20, name="Viewer", slug="viewer")
        member = _make_member(role_id=current_role.id)

        service = _make_change_role_service(
            target_member=member,
            current_role=current_role,
            new_role=new_role,
        )

        with pytest.raises(InsufficientRankError):
            service.change_role(
                company_id=member.company_id,
                member_id=member.id,
                new_role_id=new_role.id,
                actor_user_id=uuid.uuid4(),
                actor_role_rank=60,  # Equal to target's current rank
            )


class TestChangeRoleLastOwnerProtection:
    """Test last Owner protection (BR-001)."""

    def test_demoting_last_owner_raises(self):
        """change_role raises LastOwnerProtectionError when demoting the only Owner."""
        current_role = _make_role(rank=100, name="Owner", slug="owner")
        new_role = _make_role(rank=80, name="Admin", slug="admin")
        member = _make_member(role_id=current_role.id)

        service = _make_change_role_service(
            target_member=member,
            current_role=current_role,
            new_role=new_role,
            owner_count=1,  # Last Owner
        )

        with pytest.raises(LastOwnerProtectionError):
            service.change_role(
                company_id=member.company_id,
                member_id=member.id,
                new_role_id=new_role.id,
                actor_user_id=uuid.uuid4(),
                actor_role_rank=100,  # Must be Owner to change Owner
            )

    def test_demoting_non_last_owner_succeeds(self):
        """change_role succeeds when demoting an Owner but another Owner exists."""
        current_role = _make_role(rank=100, name="Owner", slug="owner")
        new_role = _make_role(rank=80, name="Admin", slug="admin")
        member = _make_member(role_id=current_role.id)

        service = _make_change_role_service(
            target_member=member,
            current_role=current_role,
            new_role=new_role,
            owner_count=2,  # Multiple Owners
        )

        # Should not raise — there's another Owner
        service.change_role(
            company_id=member.company_id,
            member_id=member.id,
            new_role_id=new_role.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=100,
        )

        assert member.role_id == new_role.id


class TestChangeRoleMemberNotFound:
    """Test member not found."""

    def test_nonexistent_member_raises(self):
        """change_role raises MemberNotFoundError for unknown member_id."""
        service = _make_change_role_service(target_member=None)

        with pytest.raises(MemberNotFoundError):
            service.change_role(
                company_id=uuid.uuid4(),
                member_id=uuid.uuid4(),
                new_role_id=uuid.uuid4(),
                actor_user_id=uuid.uuid4(),
                actor_role_rank=100,
            )


class TestChangeRoleRoleNotFound:
    """Test role not found during role change."""

    def test_invalid_new_role_raises(self):
        """change_role raises RoleNotFoundError when new role doesn't exist."""
        current_role = _make_role(rank=20, name="Viewer", slug="viewer")
        member = _make_member(role_id=current_role.id)

        service = _make_change_role_service(
            target_member=member,
            current_role=current_role,
            new_role=None,  # New role does not exist
        )

        with pytest.raises(RoleNotFoundError):
            service.change_role(
                company_id=member.company_id,
                member_id=member.id,
                new_role_id=uuid.uuid4(),
                actor_user_id=uuid.uuid4(),
                actor_role_rank=100,
            )


# =============================================================================
# Phase 7 (US5): Lifecycle state machine tests — T073
# =============================================================================


def _make_lifecycle_member(
    *,
    status: str = MembershipStatus.active.value,
    role_id: uuid.UUID | None = None,
) -> MagicMock:
    """Create a mock CompanyMember for lifecycle tests."""
    member = MagicMock(spec=CompanyMember)
    member.id = uuid.uuid4()
    member.company_id = uuid.uuid4()
    member.user_id = uuid.uuid4()
    member.role_id = role_id or uuid.uuid4()
    member.status = status
    member.suspended_reason = None
    member.deletion_reason = None
    member.is_deleted = False
    member.deleted_at = None
    return member


def _make_lifecycle_service(
    *,
    member: MagicMock | None = None,
    deleted_member: MagicMock | None = None,
    role_slug: str = "viewer",
    role_rank: int = 20,
    owner_count: int = 2,
    with_session_repo: bool = True,
) -> MemberService:
    """Create a MemberService wired for lifecycle tests."""
    db = MagicMock()
    member_repo = MagicMock()
    role_repo = MagicMock()
    audit_service = MagicMock()
    outbox_repo = MagicMock()
    settings = _make_settings()
    session_repo = MagicMock() if with_session_repo else None

    # get_by_id_or_none returns the non-deleted member (or None if deleted)
    member_repo.get_by_id_or_none.return_value = member
    # get_deleted_by_id returns the soft-deleted member for restore
    member_repo.get_deleted_by_id.return_value = deleted_member
    member_repo.count_owners.return_value = owner_count

    role = _make_role(rank=role_rank, slug=role_slug)
    if member is not None:
        role.id = member.role_id
    role_repo.get_by_id_or_none.return_value = role

    return MemberService(
        db=db,
        member_repo=member_repo,
        role_repo=role_repo,
        audit_service=audit_service,
        outbox_repo=outbox_repo,
        settings=settings,
        session_repo=session_repo,
    )


# ---------------------------------------------------------------------------
# deactivate_member
# ---------------------------------------------------------------------------


class TestDeactivateMember:
    """Happy-path and guard tests for deactivate_member."""

    def test_deactivate_active_member_succeeds(self):
        """deactivate_member transitions active → inactive."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member)

        result = service.deactivate_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        assert member.status == MembershipStatus.inactive.value

    def test_deactivate_writes_audit_log(self):
        """deactivate_member records MEMBER_DEACTIVATED audit action."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member)

        service.deactivate_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        service._audit_service.record.assert_called_once()
        kwargs = service._audit_service.record.call_args[1]
        assert kwargs["action"] == "MEMBER_DEACTIVATED"

    def test_deactivate_revokes_sessions(self):
        """deactivate_member calls session_repo.revoke_all_by_user."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member)

        service.deactivate_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        service._session_repo.revoke_all_by_user.assert_called_once_with(member.user_id)

    def test_deactivate_publishes_event(self):
        """deactivate_member writes a MemberDeactivatedEvent to the outbox."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member)

        service.deactivate_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        service._outbox_repo.create.assert_called_once()

    def test_deactivate_invalid_transition_from_inactive_raises(self):
        """deactivate_member raises InvalidStatusTransitionError from inactive."""
        member = _make_lifecycle_member(status=MembershipStatus.inactive.value)
        service = _make_lifecycle_service(member=member)

        with pytest.raises(InvalidStatusTransitionError):
            service.deactivate_member(
                company_id=member.company_id,
                member_id=member.id,
                actor_user_id=uuid.uuid4(),
            )

    def test_deactivate_invalid_transition_from_suspended_raises(self):
        """deactivate_member raises InvalidStatusTransitionError from suspended."""
        member = _make_lifecycle_member(status=MembershipStatus.suspended.value)
        service = _make_lifecycle_service(member=member)

        with pytest.raises(InvalidStatusTransitionError):
            service.deactivate_member(
                company_id=member.company_id,
                member_id=member.id,
                actor_user_id=uuid.uuid4(),
            )

    def test_deactivate_last_owner_raises(self):
        """deactivate_member raises LastOwnerProtectionError for sole Owner."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(
            member=member, role_slug="owner", owner_count=1
        )

        with pytest.raises(LastOwnerProtectionError):
            service.deactivate_member(
                company_id=member.company_id,
                member_id=member.id,
                actor_user_id=uuid.uuid4(),
            )

    def test_deactivate_not_last_owner_succeeds(self):
        """deactivate_member succeeds when there are multiple Owners."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(
            member=member, role_slug="owner", owner_count=2
        )

        service.deactivate_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        assert member.status == MembershipStatus.inactive.value

    def test_deactivate_member_not_found_raises(self):
        """deactivate_member raises MemberNotFoundError for unknown member."""
        service = _make_lifecycle_service(member=None)

        with pytest.raises(MemberNotFoundError):
            service.deactivate_member(
                company_id=uuid.uuid4(),
                member_id=uuid.uuid4(),
                actor_user_id=uuid.uuid4(),
            )

    def test_deactivate_without_session_repo_skips_revocation(self):
        """deactivate_member proceeds without error when session_repo is None."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member, with_session_repo=False)

        # Should not raise even without session_repo
        service.deactivate_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        assert member.status == MembershipStatus.inactive.value


# ---------------------------------------------------------------------------
# reactivate_member
# ---------------------------------------------------------------------------


class TestReactivateMember:
    """Tests for reactivate_member (inactive → active, suspended → active, locked → active)."""

    def test_reactivate_from_inactive_succeeds(self):
        """reactivate_member transitions inactive → active."""
        member = _make_lifecycle_member(status=MembershipStatus.inactive.value)
        service = _make_lifecycle_service(member=member)

        service.reactivate_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        assert member.status == MembershipStatus.active.value

    def test_reactivate_from_suspended_succeeds(self):
        """reactivate_member transitions suspended → active and clears reason."""
        member = _make_lifecycle_member(status=MembershipStatus.suspended.value)
        member.suspended_reason = "Policy violation"
        service = _make_lifecycle_service(member=member)

        service.reactivate_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        assert member.status == MembershipStatus.active.value
        assert member.suspended_reason is None

    def test_reactivate_from_locked_succeeds(self):
        """reactivate_member transitions locked → active."""
        member = _make_lifecycle_member(status=MembershipStatus.locked.value)
        service = _make_lifecycle_service(member=member)

        service.reactivate_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        assert member.status == MembershipStatus.active.value

    def test_reactivate_from_inactive_uses_reactivated_action(self):
        """reactivate_member records MEMBER_REACTIVATED when coming from inactive."""
        member = _make_lifecycle_member(status=MembershipStatus.inactive.value)
        service = _make_lifecycle_service(member=member)

        service.reactivate_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        kwargs = service._audit_service.record.call_args[1]
        assert kwargs["action"] == "MEMBER_REACTIVATED"

    def test_reactivate_from_suspended_uses_unsuspended_action(self):
        """reactivate_member records MEMBER_UNSUSPENDED when coming from suspended."""
        member = _make_lifecycle_member(status=MembershipStatus.suspended.value)
        service = _make_lifecycle_service(member=member)

        service.reactivate_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        kwargs = service._audit_service.record.call_args[1]
        assert kwargs["action"] == "MEMBER_UNSUSPENDED"

    def test_reactivate_from_locked_uses_unlocked_action(self):
        """reactivate_member records MEMBER_UNLOCKED when coming from locked."""
        member = _make_lifecycle_member(status=MembershipStatus.locked.value)
        service = _make_lifecycle_service(member=member)

        service.reactivate_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        kwargs = service._audit_service.record.call_args[1]
        assert kwargs["action"] == "MEMBER_UNLOCKED"

    def test_reactivate_invalid_transition_from_active_raises(self):
        """reactivate_member raises InvalidStatusTransitionError from active."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member)

        with pytest.raises(InvalidStatusTransitionError):
            service.reactivate_member(
                company_id=member.company_id,
                member_id=member.id,
                actor_user_id=uuid.uuid4(),
            )

    def test_reactivate_member_not_found_raises(self):
        """reactivate_member raises MemberNotFoundError for unknown member."""
        service = _make_lifecycle_service(member=None)

        with pytest.raises(MemberNotFoundError):
            service.reactivate_member(
                company_id=uuid.uuid4(),
                member_id=uuid.uuid4(),
                actor_user_id=uuid.uuid4(),
            )


# ---------------------------------------------------------------------------
# suspend_member
# ---------------------------------------------------------------------------


class TestSuspendMember:
    """Tests for suspend_member."""

    def test_suspend_active_member_succeeds(self):
        """suspend_member transitions active → suspended and stores reason."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member)

        service.suspend_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            reason="Violation of conduct policy",
        )

        assert member.status == MembershipStatus.suspended.value
        assert member.suspended_reason == "Violation of conduct policy"

    def test_suspend_locked_member_succeeds(self):
        """suspend_member transitions locked → suspended."""
        member = _make_lifecycle_member(status=MembershipStatus.locked.value)
        service = _make_lifecycle_service(member=member)

        service.suspend_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            reason="Security review",
        )

        assert member.status == MembershipStatus.suspended.value

    def test_suspend_writes_audit_log(self):
        """suspend_member records MEMBER_SUSPENDED with reason."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member)

        service.suspend_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            reason="Misconduct",
        )

        kwargs = service._audit_service.record.call_args[1]
        assert kwargs["action"] == "MEMBER_SUSPENDED"
        assert kwargs["after_state"]["reason"] == "Misconduct"

    def test_suspend_revokes_sessions(self):
        """suspend_member calls session_repo.revoke_all_by_user."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member)

        service.suspend_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            reason="Reason",
        )

        service._session_repo.revoke_all_by_user.assert_called_once_with(member.user_id)

    def test_suspend_publishes_event(self):
        """suspend_member writes a MemberSuspendedEvent to the outbox."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member)

        service.suspend_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            reason="Testing",
        )

        service._outbox_repo.create.assert_called_once()

    def test_suspend_invalid_transition_from_inactive_raises(self):
        """suspend_member raises InvalidStatusTransitionError from inactive."""
        member = _make_lifecycle_member(status=MembershipStatus.inactive.value)
        service = _make_lifecycle_service(member=member)

        with pytest.raises(InvalidStatusTransitionError):
            service.suspend_member(
                company_id=member.company_id,
                member_id=member.id,
                actor_user_id=uuid.uuid4(),
                reason="N/A",
            )

    def test_suspend_invalid_transition_from_archived_raises(self):
        """suspend_member raises InvalidStatusTransitionError from archived."""
        member = _make_lifecycle_member(status=MembershipStatus.archived.value)
        service = _make_lifecycle_service(member=member)

        with pytest.raises(InvalidStatusTransitionError):
            service.suspend_member(
                company_id=member.company_id,
                member_id=member.id,
                actor_user_id=uuid.uuid4(),
                reason="N/A",
            )

    def test_suspend_last_owner_raises(self):
        """suspend_member raises LastOwnerProtectionError for sole Owner."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(
            member=member, role_slug="owner", owner_count=1
        )

        with pytest.raises(LastOwnerProtectionError):
            service.suspend_member(
                company_id=member.company_id,
                member_id=member.id,
                actor_user_id=uuid.uuid4(),
                reason="Testing last owner",
            )


# ---------------------------------------------------------------------------
# lock_member
# ---------------------------------------------------------------------------


class TestLockMember:
    """Tests for lock_member."""

    def test_lock_active_member_succeeds(self):
        """lock_member transitions active → locked."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member)

        service.lock_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        assert member.status == MembershipStatus.locked.value

    def test_lock_writes_audit_log(self):
        """lock_member records MEMBER_LOCKED audit action."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member)

        service.lock_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        kwargs = service._audit_service.record.call_args[1]
        assert kwargs["action"] == "MEMBER_LOCKED"

    def test_lock_revokes_sessions(self):
        """lock_member calls session_repo.revoke_all_by_user."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member)

        service.lock_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        service._session_repo.revoke_all_by_user.assert_called_once_with(member.user_id)

    def test_lock_publishes_event(self):
        """lock_member writes a MemberLockedEvent to the outbox."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member)

        service.lock_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        service._outbox_repo.create.assert_called_once()

    def test_lock_invalid_transition_from_inactive_raises(self):
        """lock_member raises InvalidStatusTransitionError from inactive."""
        member = _make_lifecycle_member(status=MembershipStatus.inactive.value)
        service = _make_lifecycle_service(member=member)

        with pytest.raises(InvalidStatusTransitionError):
            service.lock_member(
                company_id=member.company_id,
                member_id=member.id,
                actor_user_id=uuid.uuid4(),
            )

    def test_lock_invalid_transition_from_suspended_raises(self):
        """lock_member raises InvalidStatusTransitionError from suspended."""
        member = _make_lifecycle_member(status=MembershipStatus.suspended.value)
        service = _make_lifecycle_service(member=member)

        with pytest.raises(InvalidStatusTransitionError):
            service.lock_member(
                company_id=member.company_id,
                member_id=member.id,
                actor_user_id=uuid.uuid4(),
            )

    def test_lock_member_not_found_raises(self):
        """lock_member raises MemberNotFoundError for unknown member."""
        service = _make_lifecycle_service(member=None)

        with pytest.raises(MemberNotFoundError):
            service.lock_member(
                company_id=uuid.uuid4(),
                member_id=uuid.uuid4(),
                actor_user_id=uuid.uuid4(),
            )


# ---------------------------------------------------------------------------
# archive_member
# ---------------------------------------------------------------------------


class TestArchiveMember:
    """Tests for archive_member (soft-delete)."""

    def test_archive_active_member_succeeds(self):
        """archive_member transitions active → archived and sets deletion fields."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member)

        service.archive_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            reason="Left company",
        )

        assert member.status == MembershipStatus.archived.value
        assert member.deletion_reason == "Left company"
        assert member.is_deleted is True
        assert member.deleted_at is not None

    def test_archive_inactive_member_succeeds(self):
        """archive_member transitions inactive → archived."""
        member = _make_lifecycle_member(status=MembershipStatus.inactive.value)
        service = _make_lifecycle_service(member=member)

        service.archive_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            reason="Purge",
        )

        assert member.status == MembershipStatus.archived.value

    def test_archive_suspended_member_succeeds(self):
        """archive_member transitions suspended → archived."""
        member = _make_lifecycle_member(status=MembershipStatus.suspended.value)
        service = _make_lifecycle_service(member=member)

        service.archive_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            reason="Terminated",
        )

        assert member.status == MembershipStatus.archived.value

    def test_archive_locked_member_succeeds(self):
        """archive_member transitions locked → archived."""
        member = _make_lifecycle_member(status=MembershipStatus.locked.value)
        service = _make_lifecycle_service(member=member)

        service.archive_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            reason="Security breach",
        )

        assert member.status == MembershipStatus.archived.value

    def test_archive_writes_audit_log(self):
        """archive_member records MEMBER_ARCHIVED with reason."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member)

        service.archive_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            reason="Voluntary exit",
        )

        kwargs = service._audit_service.record.call_args[1]
        assert kwargs["action"] == "MEMBER_ARCHIVED"
        assert kwargs["after_state"]["reason"] == "Voluntary exit"

    def test_archive_revokes_sessions(self):
        """archive_member calls session_repo.revoke_all_by_user."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member)

        service.archive_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            reason="Reason",
        )

        service._session_repo.revoke_all_by_user.assert_called_once_with(member.user_id)

    def test_archive_publishes_event(self):
        """archive_member writes a MemberArchivedEvent to the outbox."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member)

        service.archive_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            reason="Reason",
        )

        service._outbox_repo.create.assert_called_once()

    def test_archive_invalid_transition_from_archived_raises(self):
        """archive_member raises InvalidStatusTransitionError from archived."""
        member = _make_lifecycle_member(status=MembershipStatus.archived.value)
        service = _make_lifecycle_service(member=member)

        with pytest.raises(InvalidStatusTransitionError):
            service.archive_member(
                company_id=member.company_id,
                member_id=member.id,
                actor_user_id=uuid.uuid4(),
                reason="N/A",
            )

    def test_archive_last_owner_raises(self):
        """archive_member raises LastOwnerProtectionError for sole Owner."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(
            member=member, role_slug="owner", owner_count=1
        )

        with pytest.raises(LastOwnerProtectionError):
            service.archive_member(
                company_id=member.company_id,
                member_id=member.id,
                actor_user_id=uuid.uuid4(),
                reason="Trying to remove last owner",
            )

    def test_archive_not_last_owner_succeeds(self):
        """archive_member succeeds when multiple Owners exist."""
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(
            member=member, role_slug="owner", owner_count=2
        )

        service.archive_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            reason="Resigned",
        )

        assert member.status == MembershipStatus.archived.value


# ---------------------------------------------------------------------------
# restore_member
# ---------------------------------------------------------------------------


class TestRestoreMember:
    """Tests for restore_member (archived → active)."""

    def test_restore_archived_member_succeeds(self):
        """restore_member transitions archived → active and clears deletion fields."""
        member = _make_lifecycle_member(status=MembershipStatus.archived.value)
        member.is_deleted = True
        member.deletion_reason = "Left company"

        # restore_member tries get_by_id_or_none first (returns None for archived),
        # then get_deleted_by_id
        service = _make_lifecycle_service(member=None, deleted_member=member)

        service.restore_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        assert member.status == MembershipStatus.active.value
        assert member.is_deleted is False
        assert member.deleted_at is None
        assert member.deletion_reason is None

    def test_restore_found_by_primary_lookup_succeeds(self):
        """restore_member succeeds when get_by_id_or_none returns archived member."""
        member = _make_lifecycle_member(status=MembershipStatus.archived.value)
        member.is_deleted = True

        # Sometimes the primary lookup may include archived records
        service = _make_lifecycle_service(member=member, deleted_member=None)

        service.restore_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        assert member.status == MembershipStatus.active.value

    def test_restore_writes_audit_log(self):
        """restore_member records MEMBER_RESTORED audit action."""
        member = _make_lifecycle_member(status=MembershipStatus.archived.value)
        service = _make_lifecycle_service(member=None, deleted_member=member)

        service.restore_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        kwargs = service._audit_service.record.call_args[1]
        assert kwargs["action"] == "MEMBER_RESTORED"

    def test_restore_publishes_event(self):
        """restore_member writes a MemberRestoredEvent to the outbox."""
        member = _make_lifecycle_member(status=MembershipStatus.archived.value)
        service = _make_lifecycle_service(member=None, deleted_member=member)

        service.restore_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
        )

        service._outbox_repo.create.assert_called_once()

    def test_restore_member_not_found_raises(self):
        """restore_member raises MemberNotFoundError when neither lookup finds a member."""
        service = _make_lifecycle_service(member=None, deleted_member=None)

        with pytest.raises(MemberNotFoundError):
            service.restore_member(
                company_id=uuid.uuid4(),
                member_id=uuid.uuid4(),
                actor_user_id=uuid.uuid4(),
            )

    def test_restore_invalid_transition_from_active_raises(self):
        """restore_member raises InvalidStatusTransitionError from active status.

        active → active is not a valid state machine transition (BR-020).
        """
        member = _make_lifecycle_member(status=MembershipStatus.active.value)
        service = _make_lifecycle_service(member=member, deleted_member=None)

        with pytest.raises(InvalidStatusTransitionError):
            service.restore_member(
                company_id=member.company_id,
                member_id=member.id,
                actor_user_id=uuid.uuid4(),
            )


# ---------------------------------------------------------------------------
# State machine — cross-cutting transition matrix
# ---------------------------------------------------------------------------


class TestLifecycleStateTransitionMatrix:
    """Verify the full BR-020 transition matrix systematically."""

    # Each entry: (from_status, to_status, method_name, should_succeed, kwargs)
    _CASES = [
        # Valid transitions
        ("active", "inactive", "deactivate_member", True, {}),
        ("active", "suspended", "suspend_member", True, {"reason": "R"}),
        ("active", "locked", "lock_member", True, {}),
        ("inactive", "active", "reactivate_member", True, {}),
        ("suspended", "active", "reactivate_member", True, {}),
        ("locked", "active", "reactivate_member", True, {}),
        ("locked", "suspended", "suspend_member", True, {"reason": "R"}),
        # Invalid transitions (sample)
        ("inactive", "suspended", "suspend_member", False, {"reason": "R"}),
        ("inactive", "locked", "lock_member", False, {}),
        ("suspended", "inactive", "deactivate_member", False, {}),
        ("locked", "inactive", "deactivate_member", False, {}),
    ]

    @pytest.mark.parametrize("from_status,to_status,method,ok,kwargs", _CASES)
    def test_transition(self, from_status, to_status, method, ok, kwargs):
        """Parametric BR-020 transition matrix check."""
        member = _make_lifecycle_member(status=from_status)
        service = _make_lifecycle_service(member=member)

        call = getattr(service, method)
        call_kwargs = {
            "company_id": member.company_id,
            "member_id": member.id,
            "actor_user_id": uuid.uuid4(),
            **kwargs,
        }

        if ok:
            call(**call_kwargs)
            assert member.status == to_status
        else:
            with pytest.raises(InvalidStatusTransitionError):
                call(**call_kwargs)


# ---------------------------------------------------------------------------
# T082 — Unit tests: employee info update (US7)
# ---------------------------------------------------------------------------


from datetime import date, timedelta

from modules.users_roles.exceptions import (
    EmployeeIdConflictError,
    HireDateInFutureError,
)


def _make_update_service(
    *,
    target_member: MagicMock | None = None,
    employee_id_conflict: MagicMock | None = None,
) -> MemberService:
    """Create a MemberService wired for update_member tests."""
    db = MagicMock()
    member_repo = MagicMock()
    role_repo = MagicMock()
    audit_service = MagicMock()
    outbox_repo = MagicMock()
    settings = _make_settings()

    member_repo.get_by_id_or_none.return_value = target_member
    # get_by_employee_id returns the conflict mock (or None if no conflict)
    member_repo.get_by_employee_id.return_value = employee_id_conflict

    return MemberService(
        db=db,
        member_repo=member_repo,
        role_repo=role_repo,
        audit_service=audit_service,
        outbox_repo=outbox_repo,
        settings=settings,
    )


def _make_update_member(
    *,
    employee_id: str | None = None,
    hire_date=None,
    notes: str | None = None,
) -> MagicMock:
    """Create a mock CompanyMember for update_member tests."""
    member = MagicMock(spec=CompanyMember)
    member.id = uuid.uuid4()
    member.company_id = uuid.uuid4()
    member.user_id = uuid.uuid4()
    member.role_id = uuid.uuid4()
    member.status = "active"
    member.employee_id = employee_id
    member.job_title = None
    member.department = None
    member.work_phone = None
    member.hire_date = hire_date
    member.notes = notes
    return member


class TestUpdateMemberEmployeeId:
    """BR-032: employee_id uniqueness within company."""

    def test_set_new_unique_employee_id_succeeds(self):
        """Setting an employee_id not used by any other member succeeds."""
        member = _make_update_member()
        service = _make_update_service(
            target_member=member,
            employee_id_conflict=None,
        )
        service.update_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=80,
            employee_id="EMP-001",
        )
        assert member.employee_id == "EMP-001"

    def test_set_same_employee_id_on_self_succeeds(self):
        """Re-assigning the same employee_id to the same member does not raise."""
        member = _make_update_member(employee_id="EMP-001")
        # get_by_employee_id returns the same member (self-conflict)
        service = _make_update_service(
            target_member=member,
            employee_id_conflict=member,
        )
        # Should not raise — same member
        service.update_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=80,
            employee_id="EMP-001",
        )

    def test_duplicate_employee_id_across_members_raises(self):
        """Setting employee_id already used by another member raises EmployeeIdConflictError."""
        member = _make_update_member()
        other_member = _make_update_member(employee_id="EMP-999")
        service = _make_update_service(
            target_member=member,
            employee_id_conflict=other_member,
        )
        with pytest.raises(EmployeeIdConflictError):
            service.update_member(
                company_id=member.company_id,
                member_id=member.id,
                actor_user_id=uuid.uuid4(),
                actor_role_rank=80,
                employee_id="EMP-999",
            )

    def test_clear_employee_id_to_none_skips_uniqueness_check(self):
        """Clearing employee_id (setting to None) does not trigger uniqueness check."""
        member = _make_update_member(employee_id="EMP-001")
        conflict = _make_update_member()
        service = _make_update_service(
            target_member=member,
            employee_id_conflict=conflict,
        )
        # employee_id=None means clear — should not call get_by_employee_id
        service.update_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=80,
            employee_id=None,
        )
        service._member_repo.get_by_employee_id.assert_not_called()

    def test_employee_id_not_provided_skips_uniqueness_check(self):
        """Omitting employee_id (sentinel) does not trigger uniqueness check."""
        member = _make_update_member()
        service = _make_update_service(target_member=member)
        # Not passing employee_id at all (uses sentinel ...)
        service.update_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=80,
        )
        service._member_repo.get_by_employee_id.assert_not_called()


class TestUpdateMemberHireDate:
    """Hire date must not be in the future."""

    def test_today_hire_date_succeeds(self):
        """Hire date equal to today is valid."""
        member = _make_update_member()
        service = _make_update_service(target_member=member)
        service.update_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=80,
            hire_date=date.today(),
        )
        assert member.hire_date == date.today()

    def test_past_hire_date_succeeds(self):
        """Hire date in the past is valid."""
        member = _make_update_member()
        service = _make_update_service(target_member=member)
        past = date.today() - timedelta(days=365)
        service.update_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=80,
            hire_date=past,
        )
        assert member.hire_date == past

    def test_future_hire_date_raises(self):
        """Hire date in the future raises HireDateInFutureError."""
        member = _make_update_member()
        service = _make_update_service(target_member=member)
        future = date.today() + timedelta(days=1)
        with pytest.raises(HireDateInFutureError):
            service.update_member(
                company_id=member.company_id,
                member_id=member.id,
                actor_user_id=uuid.uuid4(),
                actor_role_rank=80,
                hire_date=future,
            )

    def test_clear_hire_date_to_none_does_not_validate(self):
        """Clearing hire_date to None does not trigger date validation."""
        member = _make_update_member(hire_date=date.today())
        service = _make_update_service(target_member=member)
        service.update_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=80,
            hire_date=None,
        )
        assert member.hire_date is None

    def test_hire_date_not_provided_skips_validation(self):
        """Omitting hire_date (sentinel) does not trigger date validation."""
        member = _make_update_member()
        service = _make_update_service(target_member=member)
        # Not passing hire_date at all (uses sentinel ...)
        service.update_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=80,
        )


class TestUpdateMemberAuditLog:
    """update_member writes audit log with before/after state."""

    def test_update_writes_audit_log_with_before_and_after(self):
        """update_member records before/after state in audit log."""
        member = _make_update_member(notes="old notes")
        service = _make_update_service(target_member=member)

        service.update_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=80,
            notes="new notes",
        )

        service._audit_service.record.assert_called_once()
        call_kwargs = service._audit_service.record.call_args[1]
        assert call_kwargs["action"] == "MEMBER_UPDATED"
        assert "before_state" in call_kwargs
        assert call_kwargs["before_state"]["updated_fields"]["notes"] == "old notes"
        assert call_kwargs["after_state"]["updated_fields"]["notes"] == "new notes"

    def test_no_update_skips_audit_log(self):
        """When no fields are provided, no audit log is written."""
        member = _make_update_member()
        service = _make_update_service(target_member=member)

        service.update_member(
            company_id=member.company_id,
            member_id=member.id,
            actor_user_id=uuid.uuid4(),
            actor_role_rank=80,
            # No fields provided (all sentinel)
        )

        service._audit_service.record.assert_not_called()
