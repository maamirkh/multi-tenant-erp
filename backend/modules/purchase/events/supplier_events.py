"""Supplier domain events — Phase 1.

Published by SupplierService for all Supplier lifecycle transitions.

Events:
  SupplierCreated      — new supplier record created (status=DRAFT)
  SupplierUpdated      — mutable fields updated
  SupplierActivated    — DRAFT/INACTIVE → ACTIVE
  SupplierDeactivated  — ACTIVE → INACTIVE
  SupplierBlocked      — ACTIVE → BLOCKED
  SupplierReactivated  — BLOCKED/INACTIVE → ACTIVE
  SupplierArchived     — ACTIVE/INACTIVE → ARCHIVED

All events inherit from PurchaseDomainEvent and add supplier-specific payload.

Spec ref: specs/006-purchase-management/spec.md §33 Domain Events
Task: T043
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from modules.purchase.events import PurchaseDomainEvent


@dataclass
class SupplierCreated(PurchaseDomainEvent):
    """Published when a new supplier record is created.

    The supplier starts in DRAFT status and must be activated before it
    can be used in purchase documents.
    """

    supplier_code: str = ""
    legal_name: str = ""

    @classmethod
    def create(
        cls,
        supplier_id: UUID,
        company_id: UUID,
        supplier_code: str,
        legal_name: str,
        actor_id: UUID | None = None,
    ) -> SupplierCreated:
        return cls(
            event_type="supplier.created",
            aggregate_type="Supplier",
            aggregate_id=supplier_id,
            company_id=company_id,
            supplier_code=supplier_code,
            legal_name=legal_name,
            actor_id=actor_id,
        )

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["supplier_code"] = self.supplier_code
        d["legal_name"] = self.legal_name
        return d


@dataclass
class SupplierUpdated(PurchaseDomainEvent):
    """Published when mutable supplier fields are updated."""

    changed_fields: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        supplier_id: UUID,
        company_id: UUID,
        changed_fields: list[str],
        actor_id: UUID | None = None,
    ) -> SupplierUpdated:
        return cls(
            event_type="supplier.updated",
            aggregate_type="Supplier",
            aggregate_id=supplier_id,
            company_id=company_id,
            changed_fields=changed_fields,
            actor_id=actor_id,
        )

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["changed_fields"] = self.changed_fields
        return d


@dataclass
class SupplierActivated(PurchaseDomainEvent):
    """Published when a supplier transitions to ACTIVE status.

    Covers both initial activation from DRAFT and reactivation from INACTIVE.
    """

    previous_status: str = "DRAFT"

    @classmethod
    def create(
        cls,
        supplier_id: UUID,
        company_id: UUID,
        previous_status: str,
        actor_id: UUID | None = None,
    ) -> SupplierActivated:
        return cls(
            event_type="supplier.activated",
            aggregate_type="Supplier",
            aggregate_id=supplier_id,
            company_id=company_id,
            previous_status=previous_status,
            actor_id=actor_id,
        )

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["previous_status"] = self.previous_status
        return d


@dataclass
class SupplierDeactivated(PurchaseDomainEvent):
    """Published when a supplier is moved from ACTIVE to INACTIVE."""

    reason: str | None = None

    @classmethod
    def create(
        cls,
        supplier_id: UUID,
        company_id: UUID,
        reason: str | None = None,
        actor_id: UUID | None = None,
    ) -> SupplierDeactivated:
        return cls(
            event_type="supplier.deactivated",
            aggregate_type="Supplier",
            aggregate_id=supplier_id,
            company_id=company_id,
            reason=reason,
            actor_id=actor_id,
        )

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["reason"] = self.reason
        return d


@dataclass
class SupplierBlocked(PurchaseDomainEvent):
    """Published when a supplier is placed under a compliance or dispute block."""

    reason: str = ""

    @classmethod
    def create(
        cls,
        supplier_id: UUID,
        company_id: UUID,
        reason: str,
        actor_id: UUID | None = None,
    ) -> SupplierBlocked:
        return cls(
            event_type="supplier.blocked",
            aggregate_type="Supplier",
            aggregate_id=supplier_id,
            company_id=company_id,
            reason=reason,
            actor_id=actor_id,
        )

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["reason"] = self.reason
        return d


@dataclass
class SupplierReactivated(PurchaseDomainEvent):
    """Published when a BLOCKED or INACTIVE supplier is returned to ACTIVE status."""

    previous_status: str = "BLOCKED"
    reason: str | None = None

    @classmethod
    def create(
        cls,
        supplier_id: UUID,
        company_id: UUID,
        previous_status: str,
        reason: str | None = None,
        actor_id: UUID | None = None,
    ) -> SupplierReactivated:
        return cls(
            event_type="supplier.reactivated",
            aggregate_type="Supplier",
            aggregate_id=supplier_id,
            company_id=company_id,
            previous_status=previous_status,
            reason=reason,
            actor_id=actor_id,
        )

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["previous_status"] = self.previous_status
        d["reason"] = self.reason
        return d


@dataclass
class SupplierArchived(PurchaseDomainEvent):
    """Published when a supplier is decommissioned (moved to ARCHIVED).

    Archived suppliers are permanently ineligible for new purchase documents.
    """

    previous_status: str = "ACTIVE"

    @classmethod
    def create(
        cls,
        supplier_id: UUID,
        company_id: UUID,
        previous_status: str,
        actor_id: UUID | None = None,
    ) -> SupplierArchived:
        return cls(
            event_type="supplier.archived",
            aggregate_type="Supplier",
            aggregate_id=supplier_id,
            company_id=company_id,
            previous_status=previous_status,
            actor_id=actor_id,
        )

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["previous_status"] = self.previous_status
        return d


# ---------------------------------------------------------------------------
# Phase 2 events
# ---------------------------------------------------------------------------


@dataclass
class SupplierRatingUpdated(PurchaseDomainEvent):
    """Published when a supplier's rating score is recomputed or manually overridden.

    Consumers can use this event to update caches, send notifications, or trigger
    downstream workflows that depend on supplier performance scores.
    """

    composite_score: Decimal = Decimal("0")
    gr_count_window: int = 0
    is_manual_override: bool = False

    @classmethod
    def create(
        cls,
        supplier_id: UUID,
        company_id: UUID,
        composite_score: Decimal,
        gr_count_window: int,
        is_manual_override: bool = False,
        actor_id: UUID | None = None,
    ) -> SupplierRatingUpdated:
        return cls(
            event_type="supplier.rating_updated",
            aggregate_type="Supplier",
            aggregate_id=supplier_id,
            company_id=company_id,
            composite_score=composite_score,
            gr_count_window=gr_count_window,
            is_manual_override=is_manual_override,
            actor_id=actor_id,
        )

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["composite_score"] = str(self.composite_score)
        d["gr_count_window"] = self.gr_count_window
        d["is_manual_override"] = self.is_manual_override
        return d


@dataclass
class PreferredSupplierDesignated(PurchaseDomainEvent):
    """Published when a supplier's preferred status is changed.

    Only Purchase Manager role can perform this action (enforced at service layer).
    """

    is_preferred: bool = False
    previous_preferred: bool = False

    @classmethod
    def create(
        cls,
        supplier_id: UUID,
        company_id: UUID,
        is_preferred: bool,
        previous_preferred: bool,
        actor_id: UUID | None = None,
    ) -> PreferredSupplierDesignated:
        return cls(
            event_type="supplier.preferred_designated",
            aggregate_type="Supplier",
            aggregate_id=supplier_id,
            company_id=company_id,
            is_preferred=is_preferred,
            previous_preferred=previous_preferred,
            actor_id=actor_id,
        )

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["is_preferred"] = self.is_preferred
        d["previous_preferred"] = self.previous_preferred
        return d


__all__ = [
    "PreferredSupplierDesignated",
    "SupplierActivated",
    "SupplierArchived",
    "SupplierBlocked",
    "SupplierCreated",
    "SupplierDeactivated",
    "SupplierRatingUpdated",
    "SupplierReactivated",
    "SupplierUpdated",
]
