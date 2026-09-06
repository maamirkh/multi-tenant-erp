"""Purchase Request domain events — Phase 4.

Events:
  PurchaseRequestCreated    — PR created in DRAFT status
  PurchaseRequestSubmitted  — PR submitted for approval
  PurchaseRequestApproved   — PR approved (by approval engine or auto-approved)
  PurchaseRequestRejected   — PR rejected by approver
  PurchaseRequestCancelled  — PR cancelled by requestor or manager
  PurchaseRequestConvertedToPO — approved PR converted to a PurchaseOrder

Spec ref: specs/006-purchase-management/spec.md §33 Domain Events
Task: T107
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from modules.purchase.events import PurchaseDomainEvent


@dataclass
class PurchaseRequestCreated(PurchaseDomainEvent):
    """Fired when a new PurchaseRequest is created in DRAFT status."""

    event_type: str = field(default="purchase_request.created", init=False)
    aggregate_type: str = field(default="PurchaseRequest", init=False)

    pr_number: str = ""
    title: str = ""
    requestor_id: str = ""
    department: str | None = None

    @classmethod
    def create(
        cls,
        aggregate_id: UUID,
        company_id: UUID,
        pr_number: str,
        title: str,
        requestor_id: str,
        department: str | None = None,
        actor_id: UUID | None = None,
    ) -> PurchaseRequestCreated:
        event = cls(aggregate_id=aggregate_id, company_id=company_id, actor_id=actor_id)
        event.pr_number = pr_number
        event.title = title
        event.requestor_id = requestor_id
        event.department = department
        return event

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update(
            {
                "pr_number": self.pr_number,
                "title": self.title,
                "requestor_id": self.requestor_id,
                "department": self.department,
            }
        )
        return base


@dataclass
class PurchaseRequestSubmitted(PurchaseDomainEvent):
    """Fired when a PR is submitted for approval review."""

    event_type: str = field(default="purchase_request.submitted", init=False)
    aggregate_type: str = field(default="PurchaseRequest", init=False)

    pr_number: str = ""
    requestor_id: str = ""

    @classmethod
    def create(
        cls,
        aggregate_id: UUID,
        company_id: UUID,
        pr_number: str,
        requestor_id: str,
        actor_id: UUID | None = None,
    ) -> PurchaseRequestSubmitted:
        event = cls(aggregate_id=aggregate_id, company_id=company_id, actor_id=actor_id)
        event.pr_number = pr_number
        event.requestor_id = requestor_id
        return event

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({"pr_number": self.pr_number, "requestor_id": self.requestor_id})
        return base


@dataclass
class PurchaseRequestApproved(PurchaseDomainEvent):
    """Fired when a PR is fully approved (final level approved or auto-approved)."""

    event_type: str = field(default="purchase_request.approved", init=False)
    aggregate_type: str = field(default="PurchaseRequest", init=False)

    pr_number: str = ""
    auto_approved: bool = False

    @classmethod
    def create(
        cls,
        aggregate_id: UUID,
        company_id: UUID,
        pr_number: str,
        auto_approved: bool = False,
        actor_id: UUID | None = None,
    ) -> PurchaseRequestApproved:
        event = cls(aggregate_id=aggregate_id, company_id=company_id, actor_id=actor_id)
        event.pr_number = pr_number
        event.auto_approved = auto_approved
        return event

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({"pr_number": self.pr_number, "auto_approved": self.auto_approved})
        return base


@dataclass
class PurchaseRequestRejected(PurchaseDomainEvent):
    """Fired when a PR is rejected by an approver."""

    event_type: str = field(default="purchase_request.rejected", init=False)
    aggregate_type: str = field(default="PurchaseRequest", init=False)

    pr_number: str = ""
    rejection_reason: str = ""
    rejected_by: str = ""

    @classmethod
    def create(
        cls,
        aggregate_id: UUID,
        company_id: UUID,
        pr_number: str,
        rejection_reason: str,
        rejected_by: str,
        actor_id: UUID | None = None,
    ) -> PurchaseRequestRejected:
        event = cls(aggregate_id=aggregate_id, company_id=company_id, actor_id=actor_id)
        event.pr_number = pr_number
        event.rejection_reason = rejection_reason
        event.rejected_by = rejected_by
        return event

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update(
            {
                "pr_number": self.pr_number,
                "rejection_reason": self.rejection_reason,
                "rejected_by": self.rejected_by,
            }
        )
        return base


@dataclass
class PurchaseRequestCancelled(PurchaseDomainEvent):
    """Fired when a PR is cancelled."""

    event_type: str = field(default="purchase_request.cancelled", init=False)
    aggregate_type: str = field(default="PurchaseRequest", init=False)

    pr_number: str = ""
    cancellation_reason: str | None = None

    @classmethod
    def create(
        cls,
        aggregate_id: UUID,
        company_id: UUID,
        pr_number: str,
        cancellation_reason: str | None = None,
        actor_id: UUID | None = None,
    ) -> PurchaseRequestCancelled:
        event = cls(aggregate_id=aggregate_id, company_id=company_id, actor_id=actor_id)
        event.pr_number = pr_number
        event.cancellation_reason = cancellation_reason
        return event

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update(
            {
                "pr_number": self.pr_number,
                "cancellation_reason": self.cancellation_reason,
            }
        )
        return base


@dataclass
class PurchaseRequestConvertedToPO(PurchaseDomainEvent):
    """Fired when an approved PR is converted to a Purchase Order."""

    event_type: str = field(default="purchase_request.converted_to_po", init=False)
    aggregate_type: str = field(default="PurchaseRequest", init=False)

    pr_number: str = ""
    po_id: str = ""
    po_number: str = ""

    @classmethod
    def create(
        cls,
        aggregate_id: UUID,
        company_id: UUID,
        pr_number: str,
        po_id: str,
        po_number: str,
        actor_id: UUID | None = None,
    ) -> PurchaseRequestConvertedToPO:
        event = cls(aggregate_id=aggregate_id, company_id=company_id, actor_id=actor_id)
        event.pr_number = pr_number
        event.po_id = po_id
        event.po_number = po_number
        return event

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update(
            {
                "pr_number": self.pr_number,
                "po_id": self.po_id,
                "po_number": self.po_number,
            }
        )
        return base
