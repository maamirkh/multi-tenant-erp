"""Purchase Order domain events — Phase 5.

Events:
  PurchaseOrdered            — PO submitted for approval
  PurchaseOrderApproved      — PO approved (manual or auto)
  PurchaseOrderRejected      — PO rejected by approver
  PurchaseOrderAmended       — Approved PO amended
  PurchaseOrderCancelled     — PO cancelled
  PurchaseOrderClosed        — PO closed manually or after full receipt
  PurchaseOrderFullyReceived — All PO lines fully received

Each event:
  - subclasses PurchaseDomainEvent
  - provides a create() classmethod
  - provides a to_dict() method for serialisation

Spec ref: specs/006-purchase-management/spec.md §33 Domain Events
Task: T133
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from modules.purchase.events import PurchaseDomainEvent


@dataclass
class PurchaseOrdered(PurchaseDomainEvent):
    """Published when a PO is submitted for approval."""

    event_type: str = field(default="purchase.po.submitted", init=False)
    aggregate_type: str = field(default="PurchaseOrder", init=False)

    po_number: str = ""
    supplier_id: str = ""
    total: str = "0.00"
    currency_code: str = "USD"

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: UUID,
        company_id: UUID,
        po_number: str,
        supplier_id: str,
        total: str,
        currency_code: str = "USD",
        actor_id: UUID | None = None,
    ) -> PurchaseOrdered:
        return cls(
            aggregate_id=str(aggregate_id),
            company_id=str(company_id),
            po_number=po_number,
            supplier_id=supplier_id,
            total=total,
            currency_code=currency_code,
            actor_id=str(actor_id) if actor_id else None,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            po_number=self.po_number,
            supplier_id=self.supplier_id,
            total=self.total,
            currency_code=self.currency_code,
        )
        return base


@dataclass
class PurchaseOrderApproved(PurchaseDomainEvent):
    """Published when a PO is approved."""

    event_type: str = field(default="purchase.po.approved", init=False)
    aggregate_type: str = field(default="PurchaseOrder", init=False)

    po_number: str = ""
    supplier_id: str = ""
    auto_approved: bool = False

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: UUID,
        company_id: UUID,
        po_number: str,
        supplier_id: str,
        auto_approved: bool = False,
        actor_id: UUID | None = None,
    ) -> PurchaseOrderApproved:
        return cls(
            aggregate_id=str(aggregate_id),
            company_id=str(company_id),
            po_number=po_number,
            supplier_id=supplier_id,
            auto_approved=auto_approved,
            actor_id=str(actor_id) if actor_id else None,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            po_number=self.po_number,
            supplier_id=self.supplier_id,
            auto_approved=self.auto_approved,
        )
        return base


@dataclass
class PurchaseOrderRejected(PurchaseDomainEvent):
    """Published when a PO is rejected by an approver."""

    event_type: str = field(default="purchase.po.rejected", init=False)
    aggregate_type: str = field(default="PurchaseOrder", init=False)

    po_number: str = ""
    rejection_reason: str = ""
    rejected_by: str = ""

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: UUID,
        company_id: UUID,
        po_number: str,
        rejection_reason: str,
        rejected_by: str,
        actor_id: UUID | None = None,
    ) -> PurchaseOrderRejected:
        return cls(
            aggregate_id=str(aggregate_id),
            company_id=str(company_id),
            po_number=po_number,
            rejection_reason=rejection_reason,
            rejected_by=rejected_by,
            actor_id=str(actor_id) if actor_id else None,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            po_number=self.po_number,
            rejection_reason=self.rejection_reason,
            rejected_by=self.rejected_by,
        )
        return base


@dataclass
class PurchaseOrderAmended(PurchaseDomainEvent):
    """Published when an approved PO is amended."""

    event_type: str = field(default="purchase.po.amended", init=False)
    aggregate_type: str = field(default="PurchaseOrder", init=False)

    po_number: str = ""
    amendment_number: int = 0
    reason: str = ""

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: UUID,
        company_id: UUID,
        po_number: str,
        amendment_number: int,
        reason: str,
        actor_id: UUID | None = None,
    ) -> PurchaseOrderAmended:
        return cls(
            aggregate_id=str(aggregate_id),
            company_id=str(company_id),
            po_number=po_number,
            amendment_number=amendment_number,
            reason=reason,
            actor_id=str(actor_id) if actor_id else None,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            po_number=self.po_number,
            amendment_number=self.amendment_number,
            reason=self.reason,
        )
        return base


@dataclass
class PurchaseOrderCancelled(PurchaseDomainEvent):
    """Published when a PO is cancelled."""

    event_type: str = field(default="purchase.po.cancelled", init=False)
    aggregate_type: str = field(default="PurchaseOrder", init=False)

    po_number: str = ""
    cancellation_reason: str | None = None

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: UUID,
        company_id: UUID,
        po_number: str,
        cancellation_reason: str | None = None,
        actor_id: UUID | None = None,
    ) -> PurchaseOrderCancelled:
        return cls(
            aggregate_id=str(aggregate_id),
            company_id=str(company_id),
            po_number=po_number,
            cancellation_reason=cancellation_reason,
            actor_id=str(actor_id) if actor_id else None,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            po_number=self.po_number,
            cancellation_reason=self.cancellation_reason,
        )
        return base


@dataclass
class PurchaseOrderClosed(PurchaseDomainEvent):
    """Published when a PO is closed."""

    event_type: str = field(default="purchase.po.closed", init=False)
    aggregate_type: str = field(default="PurchaseOrder", init=False)

    po_number: str = ""
    final_status_before_close: str = ""

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: UUID,
        company_id: UUID,
        po_number: str,
        final_status_before_close: str,
        actor_id: UUID | None = None,
    ) -> PurchaseOrderClosed:
        return cls(
            aggregate_id=str(aggregate_id),
            company_id=str(company_id),
            po_number=po_number,
            final_status_before_close=final_status_before_close,
            actor_id=str(actor_id) if actor_id else None,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            po_number=self.po_number,
            final_status_before_close=self.final_status_before_close,
        )
        return base


@dataclass
class PurchaseOrderFullyReceived(PurchaseDomainEvent):
    """Published when all PO lines have been fully received."""

    event_type: str = field(default="purchase.po.fully_received", init=False)
    aggregate_type: str = field(default="PurchaseOrder", init=False)

    po_number: str = ""
    supplier_id: str = ""

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: UUID,
        company_id: UUID,
        po_number: str,
        supplier_id: str,
        actor_id: UUID | None = None,
    ) -> PurchaseOrderFullyReceived:
        return cls(
            aggregate_id=str(aggregate_id),
            company_id=str(company_id),
            po_number=po_number,
            supplier_id=supplier_id,
            actor_id=str(actor_id) if actor_id else None,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            po_number=self.po_number,
            supplier_id=self.supplier_id,
        )
        return base
