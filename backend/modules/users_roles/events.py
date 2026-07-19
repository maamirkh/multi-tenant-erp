"""Domain event payload dataclasses for the users & roles module.

Each event maps to a row in the ``event_outbox`` table via
``to_outbox_record()``.  The outbox row is written in the same database
transaction as the state change that produced the event, guaranteeing
at-least-once delivery without distributed transactions.

Event type naming convention: ``member.<verb>`` / ``role.<verb>`` in past tense.

Spec reference: plan.md Section 6.3.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from core.events.outbox import OutboxRecord

_MEMBER_AGGREGATE = "CompanyMember"
_ROLE_AGGREGATE = "Role"


def _meta(correlation_id: str, actor_id: UUID | None) -> dict[str, Any]:
    return {
        "correlation_id": correlation_id,
        "actor_id": str(actor_id) if actor_id else None,
    }


# ---------------------------------------------------------------------------
# Member lifecycle events
# ---------------------------------------------------------------------------


@dataclass
class MemberCreatedEvent:
    """Emitted when a new member is added to a company."""

    company_id: UUID
    user_id: UUID
    role_id: UUID
    invited_by: UUID | None
    created_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="member.created",
            aggregate_id=str(self.user_id),
            aggregate_type=_MEMBER_AGGREGATE,
            payload={
                "company_id": str(self.company_id),
                "user_id": str(self.user_id),
                "role_id": str(self.role_id),
                "invited_by": str(self.invited_by) if self.invited_by else None,
                "created_at": self.created_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class MemberRoleChangedEvent:
    """Emitted when a member's role is changed."""

    company_id: UUID
    user_id: UUID
    old_role_id: UUID
    new_role_id: UUID
    changed_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="member.role_changed",
            aggregate_id=str(self.user_id),
            aggregate_type=_MEMBER_AGGREGATE,
            payload={
                "company_id": str(self.company_id),
                "user_id": str(self.user_id),
                "old_role_id": str(self.old_role_id),
                "new_role_id": str(self.new_role_id),
                "changed_at": self.changed_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class MemberDeactivatedEvent:
    """Emitted when a member is deactivated."""

    company_id: UUID
    user_id: UUID
    deactivated_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="member.deactivated",
            aggregate_id=str(self.user_id),
            aggregate_type=_MEMBER_AGGREGATE,
            payload={
                "company_id": str(self.company_id),
                "user_id": str(self.user_id),
                "deactivated_at": self.deactivated_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class MemberSuspendedEvent:
    """Emitted when a member is suspended."""

    company_id: UUID
    user_id: UUID
    reason: str
    suspended_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="member.suspended",
            aggregate_id=str(self.user_id),
            aggregate_type=_MEMBER_AGGREGATE,
            payload={
                "company_id": str(self.company_id),
                "user_id": str(self.user_id),
                "reason": self.reason,
                "suspended_at": self.suspended_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class MemberLockedEvent:
    """Emitted when a member is locked due to a security event."""

    company_id: UUID
    user_id: UUID
    locked_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="member.locked",
            aggregate_id=str(self.user_id),
            aggregate_type=_MEMBER_AGGREGATE,
            payload={
                "company_id": str(self.company_id),
                "user_id": str(self.user_id),
                "locked_at": self.locked_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class MemberArchivedEvent:
    """Emitted when a member is archived (soft deleted)."""

    company_id: UUID
    user_id: UUID
    reason: str
    archived_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="member.archived",
            aggregate_id=str(self.user_id),
            aggregate_type=_MEMBER_AGGREGATE,
            payload={
                "company_id": str(self.company_id),
                "user_id": str(self.user_id),
                "reason": self.reason,
                "archived_at": self.archived_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class MemberRestoredEvent:
    """Emitted when an archived member is restored."""

    company_id: UUID
    user_id: UUID
    restored_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="member.restored",
            aggregate_id=str(self.user_id),
            aggregate_type=_MEMBER_AGGREGATE,
            payload={
                "company_id": str(self.company_id),
                "user_id": str(self.user_id),
                "restored_at": self.restored_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class InvitationAcceptedEvent:
    """Emitted when a user accepts a membership invitation."""

    company_id: UUID
    user_id: UUID
    accepted_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="member.invitation_accepted",
            aggregate_id=str(self.user_id),
            aggregate_type=_MEMBER_AGGREGATE,
            payload={
                "company_id": str(self.company_id),
                "user_id": str(self.user_id),
                "accepted_at": self.accepted_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


# ---------------------------------------------------------------------------
# Ownership events
# ---------------------------------------------------------------------------


@dataclass
class OwnershipTransferredEvent:
    """Emitted when company ownership is transferred."""

    company_id: UUID
    from_user_id: UUID
    to_user_id: UUID
    transferred_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="member.ownership_transferred",
            aggregate_id=str(self.company_id),
            aggregate_type=_MEMBER_AGGREGATE,
            payload={
                "company_id": str(self.company_id),
                "from_user_id": str(self.from_user_id),
                "to_user_id": str(self.to_user_id),
                "transferred_at": self.transferred_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


# ---------------------------------------------------------------------------
# Role events
# ---------------------------------------------------------------------------


@dataclass
class RoleCreatedEvent:
    """Emitted when a custom role is created."""

    company_id: UUID
    role_id: UUID
    role_name: str
    created_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="role.created",
            aggregate_id=str(self.role_id),
            aggregate_type=_ROLE_AGGREGATE,
            payload={
                "company_id": str(self.company_id),
                "role_id": str(self.role_id),
                "role_name": self.role_name,
                "created_at": self.created_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class RoleUpdatedEvent:
    """Emitted when a custom role is updated."""

    company_id: UUID
    role_id: UUID
    updated_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="role.updated",
            aggregate_id=str(self.role_id),
            aggregate_type=_ROLE_AGGREGATE,
            payload={
                "company_id": str(self.company_id),
                "role_id": str(self.role_id),
                "updated_at": self.updated_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class RoleDeletedEvent:
    """Emitted when a custom role is deleted."""

    company_id: UUID
    role_id: UUID
    deleted_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="role.deleted",
            aggregate_id=str(self.role_id),
            aggregate_type=_ROLE_AGGREGATE,
            payload={
                "company_id": str(self.company_id),
                "role_id": str(self.role_id),
                "deleted_at": self.deleted_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


__all__ = [
    "InvitationAcceptedEvent",
    "MemberArchivedEvent",
    "MemberCreatedEvent",
    "MemberDeactivatedEvent",
    "MemberLockedEvent",
    "MemberRestoredEvent",
    "MemberRoleChangedEvent",
    "MemberSuspendedEvent",
    "OwnershipTransferredEvent",
    "RoleCreatedEvent",
    "RoleDeletedEvent",
    "RoleUpdatedEvent",
]
