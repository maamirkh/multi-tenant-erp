"""Sales Order domain events — Phase 4.

Events published via InProcessEventBus for cross-module coordination
and future message-broker integration.

Event taxonomy:
  sales.order.created             — new SO created (DRAFT)
  sales.order.submitted           — DRAFT → PENDING_APPROVAL
  sales.order.approved            — PENDING_APPROVAL → APPROVED
  sales.order.rejected            — PENDING_APPROVAL → REJECTED
  sales.order.cancelled           — any live status → CANCELLED
  sales.order.partially_delivered — APPROVED → PARTIALLY_DELIVERED
  sales.order.delivered           — → DELIVERED
  sales.order.invoiced            — DELIVERED → INVOICED
  sales.order.closed              — INVOICED → CLOSED
  sales.order.credit_hold         — blocked by credit check

Spec ref: specs/007-sales-management/spec.md §34 Domain Events
Task: T120
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from modules.sales.events import SalesDomainEvent


@dataclass
class OrderCreated(SalesDomainEvent):
    """Raised when a new Sales Order is created in DRAFT status."""

    event_type: str = field(default="sales.order.created", init=False)
    aggregate_type: str = field(default="SalesOrder", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    order_id: UUID = field(default_factory=lambda: UUID(int=0))
    order_number: str = ""
    customer_id: str = ""
    total_amount: str = "0.00"
    currency_code: str = "USD"
    sales_rep_id: str = ""
    from_quotation: bool = False
    quotation_id: str | None = None


@dataclass
class OrderSubmitted(SalesDomainEvent):
    """Raised when a Sales Order is submitted for approval (→ PENDING_APPROVAL)."""

    event_type: str = field(default="sales.order.submitted", init=False)
    aggregate_type: str = field(default="SalesOrder", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    order_id: UUID = field(default_factory=lambda: UUID(int=0))
    order_number: str = ""
    customer_id: str = ""
    total_amount: str = "0.00"
    submitted_by: str = ""
    approval_version: int = 1


@dataclass
class OrderApproved(SalesDomainEvent):
    """Raised when a Sales Order is approved (→ APPROVED)."""

    event_type: str = field(default="sales.order.approved", init=False)
    aggregate_type: str = field(default="SalesOrder", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    order_id: UUID = field(default_factory=lambda: UUID(int=0))
    order_number: str = ""
    customer_id: str = ""
    total_amount: str = "0.00"
    approved_by: str = ""
    auto_approved: bool = False


@dataclass
class OrderRejected(SalesDomainEvent):
    """Raised when a Sales Order is rejected (→ REJECTED / back to DRAFT)."""

    event_type: str = field(default="sales.order.rejected", init=False)
    aggregate_type: str = field(default="SalesOrder", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    order_id: UUID = field(default_factory=lambda: UUID(int=0))
    order_number: str = ""
    customer_id: str = ""
    rejected_by: str = ""
    rejection_reason: str | None = None


@dataclass
class OrderCancelled(SalesDomainEvent):
    """Raised when a Sales Order is cancelled."""

    event_type: str = field(default="sales.order.cancelled", init=False)
    aggregate_type: str = field(default="SalesOrder", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    order_id: UUID = field(default_factory=lambda: UUID(int=0))
    order_number: str = ""
    customer_id: str = ""
    previous_status: str = ""
    cancellation_reason: str = ""
    cancelled_by: str = ""


@dataclass
class OrderPartiallyDelivered(SalesDomainEvent):
    """Raised when a Sales Order transitions to PARTIALLY_DELIVERED."""

    event_type: str = field(default="sales.order.partially_delivered", init=False)
    aggregate_type: str = field(default="SalesOrder", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    order_id: UUID = field(default_factory=lambda: UUID(int=0))
    order_number: str = ""
    customer_id: str = ""
    delivery_note_id: str = ""


@dataclass
class OrderDelivered(SalesDomainEvent):
    """Raised when a Sales Order is fully delivered (→ DELIVERED)."""

    event_type: str = field(default="sales.order.delivered", init=False)
    aggregate_type: str = field(default="SalesOrder", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    order_id: UUID = field(default_factory=lambda: UUID(int=0))
    order_number: str = ""
    customer_id: str = ""


@dataclass
class OrderInvoiced(SalesDomainEvent):
    """Raised when a Sales Order transitions to INVOICED."""

    event_type: str = field(default="sales.order.invoiced", init=False)
    aggregate_type: str = field(default="SalesOrder", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    order_id: UUID = field(default_factory=lambda: UUID(int=0))
    order_number: str = ""
    customer_id: str = ""
    invoice_id: str = ""


@dataclass
class OrderClosed(SalesDomainEvent):
    """Raised when a Sales Order is closed (terminal state)."""

    event_type: str = field(default="sales.order.closed", init=False)
    aggregate_type: str = field(default="SalesOrder", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    order_id: UUID = field(default_factory=lambda: UUID(int=0))
    order_number: str = ""
    customer_id: str = ""


@dataclass
class OrderCreditHold(SalesDomainEvent):
    """Raised when an order is blocked by credit check during approval."""

    event_type: str = field(default="sales.order.credit_hold", init=False)
    aggregate_type: str = field(default="SalesOrder", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    order_id: UUID = field(default_factory=lambda: UUID(int=0))
    order_number: str = ""
    customer_id: str = ""
    credit_status: str = ""
    credit_limit: str = "0.00"
    outstanding_balance: str = "0.00"
    order_total: str = "0.00"
