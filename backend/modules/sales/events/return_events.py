"""Sales Return domain events — Phase 7.

Events published via InProcessEventBus for cross-module coordination.

Event taxonomy:
  sales.return.created       — new SalesReturn created (DRAFT)
  sales.return.submitted     — DRAFT → PENDING_APPROVAL
  sales.return.approved      — PENDING_APPROVAL → APPROVED
  sales.return.rejected      — PENDING_APPROVAL → REJECTED (terminal)
  sales.return.received      — APPROVED → RECEIVED (goods accepted, inventory restocked)
  sales.return.completed     — RECEIVED → COMPLETED (resolution applied)
  sales.return.refund_ready  — COMPLETED with REFUND_READINESS resolution

Spec ref: specs/007-sales-management/spec.md §34.6 Return Events
Task: T194
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from modules.sales.events import SalesDomainEvent


@dataclass
class ReturnCreated(SalesDomainEvent):
    """Raised when a new SalesReturn is created in DRAFT status."""

    event_type: str = field(default="sales.return.created", init=False)
    aggregate_type: str = field(default="SalesReturn", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    return_id: UUID = field(default_factory=lambda: UUID(int=0))
    return_number: str = ""
    customer_id: str = ""
    resolution_type: str = ""


@dataclass
class ReturnSubmitted(SalesDomainEvent):
    """Raised when a SalesReturn is submitted for approval."""

    event_type: str = field(default="sales.return.submitted", init=False)
    aggregate_type: str = field(default="SalesReturn", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    return_id: UUID = field(default_factory=lambda: UUID(int=0))
    return_number: str = ""
    customer_id: str = ""
    submitted_by: str = ""


@dataclass
class ReturnApproved(SalesDomainEvent):
    """Raised when a SalesReturn is approved."""

    event_type: str = field(default="sales.return.approved", init=False)
    aggregate_type: str = field(default="SalesReturn", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    return_id: UUID = field(default_factory=lambda: UUID(int=0))
    return_number: str = ""
    customer_id: str = ""
    approved_by: str = ""
    auto_approved: bool = False


@dataclass
class ReturnRejected(SalesDomainEvent):
    """Raised when a SalesReturn is rejected."""

    event_type: str = field(default="sales.return.rejected", init=False)
    aggregate_type: str = field(default="SalesReturn", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    return_id: UUID = field(default_factory=lambda: UUID(int=0))
    return_number: str = ""
    customer_id: str = ""
    rejected_by: str = ""
    rejection_reason: str = ""


@dataclass
class ReturnReceived(SalesDomainEvent):
    """Raised when returned goods are received (APPROVED → RECEIVED).

    Triggers inventory restock for accepted items.
    """

    event_type: str = field(default="sales.return.received", init=False)
    aggregate_type: str = field(default="SalesReturn", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    return_id: UUID = field(default_factory=lambda: UUID(int=0))
    return_number: str = ""
    customer_id: str = ""
    received_by: str = ""
    total_accepted_lines: int = 0


@dataclass
class ReturnCompleted(SalesDomainEvent):
    """Raised when a SalesReturn is resolved (RECEIVED → COMPLETED)."""

    event_type: str = field(default="sales.return.completed", init=False)
    aggregate_type: str = field(default="SalesReturn", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    return_id: UUID = field(default_factory=lambda: UUID(int=0))
    return_number: str = ""
    customer_id: str = ""
    resolution_type: str = ""
    completed_by: str = ""


@dataclass
class ReturnRefundReady(SalesDomainEvent):
    """Raised when REFUND_READINESS resolution is applied.

    Notifies external systems that this return is ready for refund processing.
    """

    event_type: str = field(default="sales.return.refund_ready", init=False)
    aggregate_type: str = field(default="SalesReturn", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    return_id: UUID = field(default_factory=lambda: UUID(int=0))
    return_number: str = ""
    customer_id: str = ""
    credit_note_amount: str = "0"
