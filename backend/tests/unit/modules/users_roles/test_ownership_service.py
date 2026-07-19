"""Unit tests for OwnershipService — Phase 15 (T132).

Tests:
- Successful ownership transfer: roles swapped, owner_id updated, audit + event written.
- Actor not found / not active → InsufficientRankError.
- Actor not Owner (insufficient rank) → InsufficientRankError.
- Target member not found → MemberNotFoundError.
- Self-transfer → LastOwnerProtectionError.
- Target not active → MemberNotFoundError.
- Owner or Admin system role missing → RoleNotFoundError.

Spec reference: Epic 4, Phase 15 (T132).
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from modules.users_roles.constants import ADMIN_RANK, OWNER_RANK
from modules.users_roles.exceptions import (
    InsufficientRankError,
    LastOwnerProtectionError,
    MemberNotFoundError,
    RoleNotFoundError,
)
from modules.users_roles.models.company_member import CompanyMember
from modules.users_roles.models.enums import MembershipStatus
from modules.users_roles.models.role import Role
from modules.users_roles.services.ownership_service import OwnershipService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_role(rank: int, slug: str, name: str | None = None) -> MagicMock:
    role = MagicMock(spec=Role)
    role.id = uuid.uuid4()
    role.rank = rank
    role.slug = slug
    role.name = name or slug.capitalize()
    return role


def _make_member(
    *,
    user_id: uuid.UUID | None = None,
    role_id: uuid.UUID | None = None,
    status: str = MembershipStatus.active.value,
    company_id: uuid.UUID | None = None,
) -> MagicMock:
    m = MagicMock(spec=CompanyMember)
    m.id = uuid.uuid4()
    m.user_id = user_id or uuid.uuid4()
    m.role_id = role_id or uuid.uuid4()
    m.status = status
    m.company_id = company_id or uuid.uuid4()
    return m


def _make_service(
    *,
    actor_member: CompanyMember | None = None,
    actor_role: MagicMock | None = None,
    target_member: CompanyMember | None = None,
    owner_role: MagicMock | None = None,
    admin_role: MagicMock | None = None,
    company: MagicMock | None = None,
) -> OwnershipService:
    """Build an OwnershipService with mocked dependencies."""
    db = MagicMock()
    member_repo = MagicMock()
    role_repo = MagicMock()
    company_repo = MagicMock()
    audit_service = MagicMock()
    outbox_repo = MagicMock()

    # member_repo.get_by_user_id → actor_member
    member_repo.get_by_user_id.return_value = actor_member

    # member_repo.get_by_id_or_none → target_member
    member_repo.get_by_id_or_none.return_value = target_member

    # role_repo.get_by_id_or_none → actor_role
    role_repo.get_by_id_or_none.return_value = actor_role

    # role_repo.get_by_slug: "owner" → owner_role, "admin" → admin_role
    def _slug_lookup(company_id: uuid.UUID, slug: str) -> MagicMock | None:
        if slug == "owner":
            return owner_role
        if slug == "admin":
            return admin_role
        return None

    role_repo.get_by_slug.side_effect = _slug_lookup

    # company_repo.get_by_id → company
    company_mock = company or MagicMock()
    company_repo.get_by_id.return_value = company_mock

    return OwnershipService(
        db=db,
        member_repo=member_repo,
        role_repo=role_repo,
        company_repo=company_repo,
        audit_service=audit_service,
        outbox_repo=outbox_repo,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTransferOwnership:
    """Tests for OwnershipService.transfer_ownership."""

    def test_successful_transfer(self) -> None:
        """Happy path: roles swapped, company.owner_id updated, audit + event written."""
        company_id = uuid.uuid4()
        actor_user_id = uuid.uuid4()
        target_user_id = uuid.uuid4()

        owner_role = _make_role(OWNER_RANK, "owner")
        admin_role = _make_role(ADMIN_RANK, "admin")

        actor_member = _make_member(
            user_id=actor_user_id,
            role_id=owner_role.id,
            company_id=company_id,
        )
        target_member = _make_member(
            user_id=target_user_id,
            company_id=company_id,
        )
        company_mock = MagicMock()
        company_mock.owner_id = actor_user_id

        service = _make_service(
            actor_member=actor_member,
            actor_role=owner_role,
            target_member=target_member,
            owner_role=owner_role,
            admin_role=admin_role,
            company=company_mock,
        )

        service.transfer_ownership(
            company_id=company_id,
            actor_user_id=actor_user_id,
            target_member_id=target_member.id,
        )

        # Roles swapped
        assert target_member.role_id == owner_role.id
        assert actor_member.role_id == admin_role.id
        # company.owner_id updated
        assert company_mock.owner_id == target_user_id
        # Audit log written
        service._audit_service.record.assert_called_once()
        call_kwargs = service._audit_service.record.call_args.kwargs
        assert call_kwargs["action"] == "OWNERSHIP_TRANSFERRED"
        assert call_kwargs["company_id"] == company_id
        assert call_kwargs["actor_user_id"] == actor_user_id
        # Outbox event written
        service._outbox_repo.create.assert_called_once()
        # DB committed
        service._db.commit.assert_called_once()

    def test_actor_not_found_raises(self) -> None:
        """Actor has no active membership → InsufficientRankError."""
        service = _make_service(actor_member=None)

        with pytest.raises(InsufficientRankError):
            service.transfer_ownership(
                company_id=uuid.uuid4(),
                actor_user_id=uuid.uuid4(),
                target_member_id=uuid.uuid4(),
            )

    def test_actor_inactive_raises(self) -> None:
        """Actor membership is inactive → InsufficientRankError."""
        actor_member = _make_member(status=MembershipStatus.inactive.value)
        service = _make_service(actor_member=actor_member)

        with pytest.raises(InsufficientRankError):
            service.transfer_ownership(
                company_id=uuid.uuid4(),
                actor_user_id=uuid.uuid4(),
                target_member_id=uuid.uuid4(),
            )

    def test_actor_not_owner_raises(self) -> None:
        """Actor is not Owner (rank < OWNER_RANK) → InsufficientRankError."""
        admin_role = _make_role(ADMIN_RANK, "admin")
        actor_member = _make_member(role_id=admin_role.id)
        service = _make_service(actor_member=actor_member, actor_role=admin_role)

        with pytest.raises(InsufficientRankError):
            service.transfer_ownership(
                company_id=uuid.uuid4(),
                actor_user_id=actor_member.user_id,
                target_member_id=uuid.uuid4(),
            )

    def test_target_not_found_raises(self) -> None:
        """Target member does not exist → MemberNotFoundError."""
        owner_role = _make_role(OWNER_RANK, "owner")
        actor_member = _make_member(role_id=owner_role.id)
        service = _make_service(
            actor_member=actor_member,
            actor_role=owner_role,
            target_member=None,
        )

        with pytest.raises(MemberNotFoundError):
            service.transfer_ownership(
                company_id=uuid.uuid4(),
                actor_user_id=actor_member.user_id,
                target_member_id=uuid.uuid4(),
            )

    def test_self_transfer_raises(self) -> None:
        """Actor tries to transfer ownership to themselves → LastOwnerProtectionError."""
        owner_role = _make_role(OWNER_RANK, "owner")
        actor_user_id = uuid.uuid4()
        actor_member = _make_member(user_id=actor_user_id, role_id=owner_role.id)
        # Target is the same user
        target_member = _make_member(user_id=actor_user_id)
        service = _make_service(
            actor_member=actor_member,
            actor_role=owner_role,
            target_member=target_member,
        )

        with pytest.raises(LastOwnerProtectionError):
            service.transfer_ownership(
                company_id=uuid.uuid4(),
                actor_user_id=actor_user_id,
                target_member_id=target_member.id,
            )

    def test_target_not_active_raises(self) -> None:
        """Target member is suspended (not active) → MemberNotFoundError."""
        owner_role = _make_role(OWNER_RANK, "owner")
        actor_member = _make_member(role_id=owner_role.id)
        target_member = _make_member(status=MembershipStatus.suspended.value)
        service = _make_service(
            actor_member=actor_member,
            actor_role=owner_role,
            target_member=target_member,
        )

        with pytest.raises(MemberNotFoundError):
            service.transfer_ownership(
                company_id=uuid.uuid4(),
                actor_user_id=actor_member.user_id,
                target_member_id=target_member.id,
            )

    def test_owner_role_missing_raises(self) -> None:
        """Owner system role not found (seeding failure) → RoleNotFoundError."""
        owner_role = _make_role(OWNER_RANK, "owner")
        actor_member = _make_member(role_id=owner_role.id)
        target_member = _make_member()
        service = _make_service(
            actor_member=actor_member,
            actor_role=owner_role,
            target_member=target_member,
            owner_role=None,  # missing
            admin_role=_make_role(ADMIN_RANK, "admin"),
        )

        with pytest.raises(RoleNotFoundError):
            service.transfer_ownership(
                company_id=uuid.uuid4(),
                actor_user_id=actor_member.user_id,
                target_member_id=target_member.id,
            )

    def test_admin_role_missing_raises(self) -> None:
        """Admin system role not found (seeding failure) → RoleNotFoundError."""
        owner_role = _make_role(OWNER_RANK, "owner")
        actor_member = _make_member(role_id=owner_role.id)
        target_member = _make_member()
        service = _make_service(
            actor_member=actor_member,
            actor_role=owner_role,
            target_member=target_member,
            owner_role=owner_role,
            admin_role=None,  # missing
        )

        with pytest.raises(RoleNotFoundError):
            service.transfer_ownership(
                company_id=uuid.uuid4(),
                actor_user_id=actor_member.user_id,
                target_member_id=target_member.id,
            )
