"""Purchase Costing domain events — Phase 8.

Events:
  PurchaseCostRecorded         — emitted when a PurchaseCostEntry is created on GR confirmation
  PurchasePriceVarianceDetected — emitted when abs(PPV%) exceeds the configured alert threshold
  AdditionalChargeRecorded     — emitted when a POAdditionalCharge is added or updated

Each event:
  - subclasses PurchaseDomainEvent
  - provides a create() classmethod
  - provides a to_dict() method for serialisation

Spec ref: specs/006-purchase-management/spec.md §33 Domain Events
Task: T197
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from modules.purchase.events import PurchaseDomainEvent


@dataclass
class PurchaseCostRecorded(PurchaseDomainEvent):
    """Published when a PurchaseCostEntry is created on GR confirmation."""

    event_type: str = field(default="purchase.cost.recorded", init=False)
    aggregate_type: str = field(default="PurchaseCostEntry", init=False)

    gr_id: str = ""
    po_id: str = ""
    supplier_id: str = ""
    subtotal: str = "0.00"
    total_charges: str = "0.00"
    total_discounts: str = "0.00"
    tax_amount: str = "0.00"
    total: str = "0.00"

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: UUID,
        company_id: UUID,
        gr_id: str,
        po_id: str,
        supplier_id: str,
        subtotal: str = "0.00",
        total_charges: str = "0.00",
        total_discounts: str = "0.00",
        tax_amount: str = "0.00",
        total: str = "0.00",
        actor_id: UUID | None = None,
    ) -> PurchaseCostRecorded:
        return cls(
            aggregate_id=str(aggregate_id),
            company_id=str(company_id),
            gr_id=gr_id,
            po_id=po_id,
            supplier_id=supplier_id,
            subtotal=subtotal,
            total_charges=total_charges,
            total_discounts=total_discounts,
            tax_amount=tax_amount,
            total=total,
            actor_id=str(actor_id) if actor_id else None,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            gr_id=self.gr_id,
            po_id=self.po_id,
            supplier_id=self.supplier_id,
            subtotal=self.subtotal,
            total_charges=self.total_charges,
            total_discounts=self.total_discounts,
            tax_amount=self.tax_amount,
            total=self.total,
        )
        return base


@dataclass
class PurchasePriceVarianceDetected(PurchaseDomainEvent):
    """Published when a GR line's PPV% exceeds the configured threshold."""

    event_type: str = field(default="purchase.cost.ppv_alert", init=False)
    aggregate_type: str = field(default="GRLine", init=False)

    gr_id: str = ""
    gr_line_id: str = ""
    po_id: str = ""
    product_id: str = ""
    ppv_amount: str = "0.00"
    ppv_percentage: str = "0.0000"
    threshold_percent: str = "0.00"

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: UUID,
        company_id: UUID,
        gr_id: str,
        gr_line_id: str,
        po_id: str,
        product_id: str = "",
        ppv_amount: str = "0.00",
        ppv_percentage: str = "0.0000",
        threshold_percent: str = "0.00",
        actor_id: UUID | None = None,
    ) -> PurchasePriceVarianceDetected:
        return cls(
            aggregate_id=str(aggregate_id),
            company_id=str(company_id),
            gr_id=gr_id,
            gr_line_id=gr_line_id,
            po_id=po_id,
            product_id=product_id,
            ppv_amount=ppv_amount,
            ppv_percentage=ppv_percentage,
            threshold_percent=threshold_percent,
            actor_id=str(actor_id) if actor_id else None,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            gr_id=self.gr_id,
            gr_line_id=self.gr_line_id,
            po_id=self.po_id,
            product_id=self.product_id,
            ppv_amount=self.ppv_amount,
            ppv_percentage=self.ppv_percentage,
            threshold_percent=self.threshold_percent,
        )
        return base


@dataclass
class AdditionalChargeRecorded(PurchaseDomainEvent):
    """Published when a POAdditionalCharge is added or updated on a PO."""

    event_type: str = field(default="purchase.cost.charge_recorded", init=False)
    aggregate_type: str = field(default="POAdditionalCharge", init=False)

    po_id: str = ""
    charge_type: str = ""
    amount: str = "0.00"
    description: str = ""

    @classmethod
    def create(
        cls,
        *,
        aggregate_id: UUID,
        company_id: UUID,
        po_id: str,
        charge_type: str,
        amount: str = "0.00",
        description: str = "",
        actor_id: UUID | None = None,
    ) -> AdditionalChargeRecorded:
        return cls(
            aggregate_id=str(aggregate_id),
            company_id=str(company_id),
            po_id=po_id,
            charge_type=charge_type,
            amount=amount,
            description=description,
            actor_id=str(actor_id) if actor_id else None,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            po_id=self.po_id,
            charge_type=self.charge_type,
            amount=self.amount,
            description=self.description,
        )
        return base
