"""Vendor Return (RMA) domain events — Phase 7.

Events:
  GoodsReturnInitiated  — RMA submitted (moved from DRAFT → SUBMITTED)
  GoodsReturnApproved   — RMA approved (SUBMITTED → APPROVED)
  GoodsReturned         — RMA dispatched (APPROVED → DISPATCHED), stock deducted
  GoodsReturnCompleted  — RMA completed (DISPATCHED → COMPLETED), credit_note_pending set

Each event:
  - subclasses PurchaseDomainEvent
  - provides a create() classmethod
  - provides a to_dict() method for serialisation

Spec ref: specs/006-purchase-management/spec.md §33 Domain Events
Task: T178
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from modules.purchase.events import PurchaseDomainEvent


@dataclass
class GoodsReturnInitiated(PurchaseDomainEvent):
    """Published when a Vendor Return is submitted (DRAFT → SUBMITTED)."""

    event_type: str = field(default="purchase.rma.initiated", init=False)
    aggregate_type: str = field(default="VendorReturn", init=False)

    rma_number: str = ""
    gr_id: str = ""
    supplier_id: str = ""

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: UUID,
        company_id: UUID,
        rma_number: str,
        gr_id: str,
        supplier_id: str,
        actor_id: UUID | None = None,
    ) -> GoodsReturnInitiated:
        return cls(
            aggregate_id=str(aggregate_id),
            company_id=str(company_id),
            rma_number=rma_number,
            gr_id=gr_id,
            supplier_id=supplier_id,
            actor_id=str(actor_id) if actor_id else None,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            rma_number=self.rma_number,
            gr_id=self.gr_id,
            supplier_id=self.supplier_id,
        )
        return base


@dataclass
class GoodsReturnApproved(PurchaseDomainEvent):
    """Published when a Vendor Return is approved (SUBMITTED → APPROVED)."""

    event_type: str = field(default="purchase.rma.approved", init=False)
    aggregate_type: str = field(default="VendorReturn", init=False)

    rma_number: str = ""
    gr_id: str = ""
    supplier_id: str = ""

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: UUID,
        company_id: UUID,
        rma_number: str,
        gr_id: str,
        supplier_id: str,
        actor_id: UUID | None = None,
    ) -> GoodsReturnApproved:
        return cls(
            aggregate_id=str(aggregate_id),
            company_id=str(company_id),
            rma_number=rma_number,
            gr_id=gr_id,
            supplier_id=supplier_id,
            actor_id=str(actor_id) if actor_id else None,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            rma_number=self.rma_number,
            gr_id=self.gr_id,
            supplier_id=self.supplier_id,
        )
        return base


@dataclass
class GoodsReturned(PurchaseDomainEvent):
    """Published when goods are dispatched back to the supplier (APPROVED → DISPATCHED).

    At this point the Epic 5 PURCHASE_RETURN_OUTBOUND stock movement has been created.
    """

    event_type: str = field(default="purchase.rma.dispatched", init=False)
    aggregate_type: str = field(default="VendorReturn", init=False)

    rma_number: str = ""
    gr_id: str = ""
    supplier_id: str = ""
    total_returned: str = "0.000"

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: UUID,
        company_id: UUID,
        rma_number: str,
        gr_id: str,
        supplier_id: str,
        total_returned: str = "0.000",
        actor_id: UUID | None = None,
    ) -> GoodsReturned:
        return cls(
            aggregate_id=str(aggregate_id),
            company_id=str(company_id),
            rma_number=rma_number,
            gr_id=gr_id,
            supplier_id=supplier_id,
            total_returned=total_returned,
            actor_id=str(actor_id) if actor_id else None,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            rma_number=self.rma_number,
            gr_id=self.gr_id,
            supplier_id=self.supplier_id,
            total_returned=self.total_returned,
        )
        return base


@dataclass
class GoodsReturnCompleted(PurchaseDomainEvent):
    """Published when a Vendor Return is completed (DISPATCHED → COMPLETED).

    credit_note_pending is set to True on the VendorReturn at this point.
    """

    event_type: str = field(default="purchase.rma.completed", init=False)
    aggregate_type: str = field(default="VendorReturn", init=False)

    rma_number: str = ""
    gr_id: str = ""
    supplier_id: str = ""
    credit_note_pending: bool = True

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: UUID,
        company_id: UUID,
        rma_number: str,
        gr_id: str,
        supplier_id: str,
        credit_note_pending: bool = True,
        actor_id: UUID | None = None,
    ) -> GoodsReturnCompleted:
        return cls(
            aggregate_id=str(aggregate_id),
            company_id=str(company_id),
            rma_number=rma_number,
            gr_id=gr_id,
            supplier_id=supplier_id,
            credit_note_pending=credit_note_pending,
            actor_id=str(actor_id) if actor_id else None,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            rma_number=self.rma_number,
            gr_id=self.gr_id,
            supplier_id=self.supplier_id,
            credit_note_pending=self.credit_note_pending,
        )
        return base
