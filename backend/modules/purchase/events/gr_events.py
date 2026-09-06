"""Goods Receipt domain events — Phase 6.

Events:
  GoodsReceived           — GR confirmed (always published on confirmation)
  GoodsRejected           — One or more lines have rejection_qty > 0
  GoodsPartiallyReceived  — One or more lines received less than open quantity
  OverReceiptDetected     — One or more lines received more than open quantity

Each event:
  - subclasses PurchaseDomainEvent
  - provides a create() classmethod
  - provides a to_dict() method for serialisation

Spec ref: specs/006-purchase-management/spec.md §33 Domain Events
Task: T157
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from modules.purchase.events import PurchaseDomainEvent


@dataclass
class GoodsReceived(PurchaseDomainEvent):
    """Published when a Goods Receipt is confirmed."""

    event_type: str = field(default="purchase.gr.confirmed", init=False)
    aggregate_type: str = field(default="GoodsReceipt", init=False)

    gr_number: str = ""
    po_id: str = ""
    supplier_id: str = ""
    total_received: str = "0.000"

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: UUID,
        company_id: UUID,
        gr_number: str,
        po_id: str,
        supplier_id: str,
        total_received: str = "0.000",
        actor_id: UUID | None = None,
    ) -> GoodsReceived:
        return cls(
            aggregate_id=str(aggregate_id),
            company_id=str(company_id),
            gr_number=gr_number,
            po_id=po_id,
            supplier_id=supplier_id,
            total_received=total_received,
            actor_id=str(actor_id) if actor_id else None,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            gr_number=self.gr_number,
            po_id=self.po_id,
            supplier_id=self.supplier_id,
            total_received=self.total_received,
        )
        return base


@dataclass
class GoodsRejected(PurchaseDomainEvent):
    """Published when one or more GR lines have rejection quantity > 0."""

    event_type: str = field(default="purchase.gr.goods_rejected", init=False)
    aggregate_type: str = field(default="GoodsReceipt", init=False)

    gr_number: str = ""
    po_id: str = ""
    supplier_id: str = ""
    total_rejected: str = "0.000"

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: UUID,
        company_id: UUID,
        gr_number: str,
        po_id: str,
        supplier_id: str,
        total_rejected: str = "0.000",
        actor_id: UUID | None = None,
    ) -> GoodsRejected:
        return cls(
            aggregate_id=str(aggregate_id),
            company_id=str(company_id),
            gr_number=gr_number,
            po_id=po_id,
            supplier_id=supplier_id,
            total_rejected=total_rejected,
            actor_id=str(actor_id) if actor_id else None,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            gr_number=self.gr_number,
            po_id=self.po_id,
            supplier_id=self.supplier_id,
            total_rejected=self.total_rejected,
        )
        return base


@dataclass
class GoodsPartiallyReceived(PurchaseDomainEvent):
    """Published when one or more GR lines received less than open quantity."""

    event_type: str = field(default="purchase.gr.partially_received", init=False)
    aggregate_type: str = field(default="GoodsReceipt", init=False)

    gr_number: str = ""
    po_id: str = ""
    supplier_id: str = ""

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: UUID,
        company_id: UUID,
        gr_number: str,
        po_id: str,
        supplier_id: str,
        actor_id: UUID | None = None,
    ) -> GoodsPartiallyReceived:
        return cls(
            aggregate_id=str(aggregate_id),
            company_id=str(company_id),
            gr_number=gr_number,
            po_id=po_id,
            supplier_id=supplier_id,
            actor_id=str(actor_id) if actor_id else None,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            gr_number=self.gr_number,
            po_id=self.po_id,
            supplier_id=self.supplier_id,
        )
        return base


@dataclass
class OverReceiptDetected(PurchaseDomainEvent):
    """Published when one or more GR lines received more than the open quantity."""

    event_type: str = field(default="purchase.gr.over_receipt", init=False)
    aggregate_type: str = field(default="GoodsReceipt", init=False)

    gr_number: str = ""
    po_id: str = ""
    supplier_id: str = ""
    over_received_lines: int = 0

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: UUID,
        company_id: UUID,
        gr_number: str,
        po_id: str,
        supplier_id: str,
        over_received_lines: int = 0,
        actor_id: UUID | None = None,
    ) -> OverReceiptDetected:
        return cls(
            aggregate_id=str(aggregate_id),
            company_id=str(company_id),
            gr_number=gr_number,
            po_id=po_id,
            supplier_id=supplier_id,
            over_received_lines=over_received_lines,
            actor_id=str(actor_id) if actor_id else None,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            gr_number=self.gr_number,
            po_id=self.po_id,
            supplier_id=self.supplier_id,
            over_received_lines=self.over_received_lines,
        )
        return base
