"""Quotation domain events for Phase 3.

Events published via InProcessEventBus for cross-module coordination
and future message-broker integration.

Event taxonomy:
  quotation.created          — new quotation created (DRAFT)
  quotation.sent             — DRAFT → SENT_TO_CUSTOMER
  quotation.accepted         — SENT_TO_CUSTOMER → ACCEPTED
  quotation.rejected         — SENT_TO_CUSTOMER → REJECTED
  quotation.converted        — ACCEPTED → CONVERTED (Sales Order created)
  quotation.expired          — SENT_TO_CUSTOMER → EXPIRED (validity date passed)
  quotation.cancelled        — any live status → CANCELLED
  quotation.expiring_soon    — validity_date approaching (warning event)

Spec ref: specs/007-sales-management/spec.md §34 Domain Events
Task: T094
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from modules.sales.events import SalesDomainEvent


@dataclass
class QuotationCreated(SalesDomainEvent):
    """Raised when a new quotation is created in DRAFT status."""

    event_type: str = field(default="quotation.created", init=False)
    aggregate_type: str = field(default="SalesQuotation", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    quotation_id: UUID = field(default_factory=lambda: UUID(int=0))
    quotation_number: str = ""
    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    sales_rep_id: UUID = field(default_factory=lambda: UUID(int=0))
    validity_date: str = ""
    created_by: UUID | None = None


@dataclass
class QuotationSent(SalesDomainEvent):
    """Raised when a quotation transitions DRAFT → SENT_TO_CUSTOMER."""

    event_type: str = field(default="quotation.sent", init=False)
    aggregate_type: str = field(default="SalesQuotation", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    quotation_id: UUID = field(default_factory=lambda: UUID(int=0))
    quotation_number: str = ""
    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    validity_date: str = ""
    sent_by: UUID | None = None


@dataclass
class QuotationAccepted(SalesDomainEvent):
    """Raised when a quotation transitions SENT_TO_CUSTOMER → ACCEPTED."""

    event_type: str = field(default="quotation.accepted", init=False)
    aggregate_type: str = field(default="SalesQuotation", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    quotation_id: UUID = field(default_factory=lambda: UUID(int=0))
    quotation_number: str = ""
    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    total_amount: float = 0.0
    accepted_by: UUID | None = None


@dataclass
class QuotationRejected(SalesDomainEvent):
    """Raised when a quotation transitions SENT_TO_CUSTOMER → REJECTED."""

    event_type: str = field(default="quotation.rejected", init=False)
    aggregate_type: str = field(default="SalesQuotation", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    quotation_id: UUID = field(default_factory=lambda: UUID(int=0))
    quotation_number: str = ""
    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    reason: str = ""
    rejected_by: UUID | None = None


@dataclass
class QuotationConverted(SalesDomainEvent):
    """Raised when ACCEPTED quotation is converted to a Sales Order."""

    event_type: str = field(default="quotation.converted", init=False)
    aggregate_type: str = field(default="SalesQuotation", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    quotation_id: UUID = field(default_factory=lambda: UUID(int=0))
    quotation_number: str = ""
    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    order_id: UUID = field(default_factory=lambda: UUID(int=0))
    order_number: str = ""
    converted_by: UUID | None = None


@dataclass
class QuotationExpired(SalesDomainEvent):
    """Raised when a quotation transitions SENT_TO_CUSTOMER → EXPIRED."""

    event_type: str = field(default="quotation.expired", init=False)
    aggregate_type: str = field(default="SalesQuotation", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    quotation_id: UUID = field(default_factory=lambda: UUID(int=0))
    quotation_number: str = ""
    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    validity_date: str = ""


@dataclass
class QuotationCancelled(SalesDomainEvent):
    """Raised when a quotation is cancelled from any live status."""

    event_type: str = field(default="quotation.cancelled", init=False)
    aggregate_type: str = field(default="SalesQuotation", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    quotation_id: UUID = field(default_factory=lambda: UUID(int=0))
    quotation_number: str = ""
    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    previous_status: str = ""
    reason: str = ""
    cancelled_by: UUID | None = None


@dataclass
class QuotationExpiringSoon(SalesDomainEvent):
    """Warning event raised when quotation validity date is approaching.

    Raised when validity_date <= today + quotation_expiry_warning_days
    (from SalesConfiguration). Not a state transition event.
    """

    event_type: str = field(default="quotation.expiring_soon", init=False)
    aggregate_type: str = field(default="SalesQuotation", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    quotation_id: UUID = field(default_factory=lambda: UUID(int=0))
    quotation_number: str = ""
    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    validity_date: str = ""
    days_remaining: int = 0
