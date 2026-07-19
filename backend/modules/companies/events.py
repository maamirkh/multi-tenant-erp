"""Domain event payload dataclasses for the companies module.

Each event maps to a row in the ``event_outbox`` table via
``to_outbox_record()``.  The outbox row is written in the same database
transaction as the state change that produced the event, guaranteeing
at-least-once delivery without distributed transactions.

Event type naming convention: ``company.<verb>`` in past tense.

Spec reference: §14.1 Domain Events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from core.events.outbox import OutboxRecord

_AGGREGATE_TYPE = "Company"


def _meta(correlation_id: str, actor_id: UUID | None) -> dict[str, Any]:
    return {
        "correlation_id": correlation_id,
        "actor_id": str(actor_id) if actor_id else None,
    }


# ---------------------------------------------------------------------------
# Company lifecycle events
# ---------------------------------------------------------------------------


@dataclass
class CompanyCreatedEvent:
    """Emitted when a new company record is persisted for the first time."""

    company_id: UUID
    legal_name: str
    slug: str
    owner_id: UUID
    status: str
    created_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="company.created",
            aggregate_id=str(self.company_id),
            aggregate_type=_AGGREGATE_TYPE,
            payload={
                "company_id": str(self.company_id),
                "legal_name": self.legal_name,
                "slug": self.slug,
                "owner_id": str(self.owner_id),
                "status": self.status,
                "created_at": self.created_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class CompanyUpdatedEvent:
    """Emitted when a company's profile or settings fields are updated."""

    company_id: UUID
    changed_fields: list[str]
    updated_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="company.updated",
            aggregate_id=str(self.company_id),
            aggregate_type=_AGGREGATE_TYPE,
            payload={
                "company_id": str(self.company_id),
                "changed_fields": self.changed_fields,
                "updated_at": self.updated_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class CompanyActivatedEvent:
    """Emitted when a company transitions to the ``active`` status."""

    company_id: UUID
    activated_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="company.activated",
            aggregate_id=str(self.company_id),
            aggregate_type=_AGGREGATE_TYPE,
            payload={
                "company_id": str(self.company_id),
                "activated_at": self.activated_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class CompanyDeactivatedEvent:
    """Emitted when an owner deactivates a company (active → inactive)."""

    company_id: UUID
    reason: str
    deactivated_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="company.deactivated",
            aggregate_id=str(self.company_id),
            aggregate_type=_AGGREGATE_TYPE,
            payload={
                "company_id": str(self.company_id),
                "reason": self.reason,
                "deactivated_at": self.deactivated_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class CompanySuspendedEvent:
    """Emitted when a SuperAdmin suspends a company."""

    company_id: UUID
    reason: str
    suspended_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="company.suspended",
            aggregate_id=str(self.company_id),
            aggregate_type=_AGGREGATE_TYPE,
            payload={
                "company_id": str(self.company_id),
                "reason": self.reason,
                "suspended_at": self.suspended_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class CompanySuspensionLiftedEvent:
    """Emitted when a SuperAdmin lifts a suspension (suspended → active)."""

    company_id: UUID
    lifted_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="company.suspension_lifted",
            aggregate_id=str(self.company_id),
            aggregate_type=_AGGREGATE_TYPE,
            payload={
                "company_id": str(self.company_id),
                "lifted_at": self.lifted_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class CompanyDeletedEvent:
    """Emitted when an owner soft-deletes a company (active/inactive → deleted)."""

    company_id: UUID
    reason: str
    deleted_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="company.deleted",
            aggregate_id=str(self.company_id),
            aggregate_type=_AGGREGATE_TYPE,
            payload={
                "company_id": str(self.company_id),
                "reason": self.reason,
                "deleted_at": self.deleted_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class CompanyRestoredEvent:
    """Emitted when an owner restores a soft-deleted company (deleted → inactive)."""

    company_id: UUID
    restored_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="company.restored",
            aggregate_id=str(self.company_id),
            aggregate_type=_AGGREGATE_TYPE,
            payload={
                "company_id": str(self.company_id),
                "restored_at": self.restored_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class CompanyPermanentlyPurgedEvent:
    """Emitted when the background purge job permanently removes a company record."""

    company_id: UUID
    purged_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="company.permanently_purged",
            aggregate_id=str(self.company_id),
            aggregate_type=_AGGREGATE_TYPE,
            payload={
                "company_id": str(self.company_id),
                "purged_at": self.purged_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class CompanyLogoUploadedEvent:
    """Emitted when a new logo is successfully uploaded to object storage."""

    company_id: UUID
    logo_url: str
    previous_logo_url: str | None
    uploaded_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="company.logo_uploaded",
            aggregate_id=str(self.company_id),
            aggregate_type=_AGGREGATE_TYPE,
            payload={
                "company_id": str(self.company_id),
                "logo_url": self.logo_url,
                "previous_logo_url": self.previous_logo_url,
                "uploaded_at": self.uploaded_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


@dataclass
class CompanyAdminChangedEvent:
    """Emitted when the primary admin of a company is changed by the owner."""

    company_id: UUID
    previous_admin_id: UUID | None
    new_admin_id: UUID | None
    changed_at: datetime

    def to_outbox_record(
        self, correlation_id: str, actor_id: UUID | None
    ) -> OutboxRecord:
        return OutboxRecord(
            event_type="company.admin_changed",
            aggregate_id=str(self.company_id),
            aggregate_type=_AGGREGATE_TYPE,
            payload={
                "company_id": str(self.company_id),
                "previous_admin_id": (
                    str(self.previous_admin_id) if self.previous_admin_id else None
                ),
                "new_admin_id": str(self.new_admin_id) if self.new_admin_id else None,
                "changed_at": self.changed_at.isoformat(),
            },
            metadata_=_meta(correlation_id, actor_id),
        )


# Convenience re-export for wildcard imports
__all__ = [
    "CompanyActivatedEvent",
    "CompanyAdminChangedEvent",
    "CompanyCreatedEvent",
    "CompanyDeactivatedEvent",
    "CompanyDeletedEvent",
    "CompanyLogoUploadedEvent",
    "CompanyPermanentlyPurgedEvent",
    "CompanyRestoredEvent",
    "CompanySuspendedEvent",
    "CompanySuspensionLiftedEvent",
    "CompanyUpdatedEvent",
]
