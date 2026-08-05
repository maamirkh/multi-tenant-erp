"""Sales Invoice domain events — Phase 6.

Events published via InProcessEventBus for cross-module coordination.

Event taxonomy:
  sales.invoice.created          — new Invoice created (DRAFT)
  sales.invoice.issued           — DRAFT → ISSUED (invoice sent to customer)
  sales.invoice.cancelled        — DRAFT → CANCELLED (voided before issuance)
  sales.invoice.credit_note_issued — ISSUED → CREDIT_NOTE_ISSUED

Spec ref: specs/007-sales-management/spec.md §34 Domain Events
Task: T173
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from modules.sales.events import SalesDomainEvent


@dataclass
class InvoiceCreated(SalesDomainEvent):
    """Raised when a new Sales Invoice is created in DRAFT status."""

    event_type: str = field(default="sales.invoice.created", init=False)
    aggregate_type: str = field(default="SalesInvoice", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    invoice_id: UUID = field(default_factory=lambda: UUID(int=0))
    invoice_number: str = ""
    customer_id: str = ""
    order_id: str | None = None
    delivery_note_id: str | None = None
    total_amount: str = "0"
    currency_code: str = ""


@dataclass
class InvoiceIssued(SalesDomainEvent):
    """Raised when a Sales Invoice transitions from DRAFT to ISSUED."""

    event_type: str = field(default="sales.invoice.issued", init=False)
    aggregate_type: str = field(default="SalesInvoice", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    invoice_id: UUID = field(default_factory=lambda: UUID(int=0))
    invoice_number: str = ""
    customer_id: str = ""
    due_date: str = ""
    total_amount: str = "0"
    currency_code: str = ""
    issued_by: str = ""


@dataclass
class InvoiceCancelled(SalesDomainEvent):
    """Raised when a Sales Invoice is cancelled (voided, number retained)."""

    event_type: str = field(default="sales.invoice.cancelled", init=False)
    aggregate_type: str = field(default="SalesInvoice", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    invoice_id: UUID = field(default_factory=lambda: UUID(int=0))
    invoice_number: str = ""
    customer_id: str = ""
    previous_status: str = "DRAFT"
    cancelled_by: str = ""


@dataclass
class InvoiceCreditNoteIssued(SalesDomainEvent):
    """Raised when a credit note is issued against an ISSUED Sales Invoice."""

    event_type: str = field(default="sales.invoice.credit_note_issued", init=False)
    aggregate_type: str = field(default="SalesInvoice", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    invoice_id: UUID = field(default_factory=lambda: UUID(int=0))
    invoice_number: str = ""
    customer_id: str = ""
    credit_note_amount: str = "0"
    issued_by: str = ""
