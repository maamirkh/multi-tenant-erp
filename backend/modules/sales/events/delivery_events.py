"""Delivery Note domain events — Phase 5.

Events published via InProcessEventBus for cross-module coordination.

Event taxonomy:
  sales.delivery.created    — new DN created (DRAFT)
  sales.delivery.dispatched — DRAFT → DISPATCHED (stock deducted)
  sales.delivery.delivered  — DISPATCHED → DELIVERED
  sales.delivery.cancelled  — any live status → CANCELLED (reservation released)

Spec ref: specs/007-sales-management/spec.md §34 Domain Events
Task: T147
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from modules.sales.events import SalesDomainEvent


@dataclass
class DeliveryNoteCreated(SalesDomainEvent):
    """Raised when a new Delivery Note is created in DRAFT status."""

    event_type: str = field(default="sales.delivery.created", init=False)
    aggregate_type: str = field(default="DeliveryNote", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    delivery_note_id: UUID = field(default_factory=lambda: UUID(int=0))
    delivery_number: str = ""
    order_id: str = ""
    customer_id: str = ""
    line_count: int = 0


@dataclass
class DeliveryNoteDispatched(SalesDomainEvent):
    """Raised when a Delivery Note transitions to DISPATCHED.

    At this point stock has been deducted from inventory (Epic 5).
    """

    event_type: str = field(default="sales.delivery.dispatched", init=False)
    aggregate_type: str = field(default="DeliveryNote", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    delivery_note_id: UUID = field(default_factory=lambda: UUID(int=0))
    delivery_number: str = ""
    order_id: str = ""
    customer_id: str = ""
    dispatch_date: str = ""
    dispatched_by: str = ""


@dataclass
class DeliveryNoteDelivered(SalesDomainEvent):
    """Raised when a Delivery Note transitions to DELIVERED."""

    event_type: str = field(default="sales.delivery.delivered", init=False)
    aggregate_type: str = field(default="DeliveryNote", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    delivery_note_id: UUID = field(default_factory=lambda: UUID(int=0))
    delivery_number: str = ""
    order_id: str = ""
    customer_id: str = ""


@dataclass
class DeliveryNoteCancelled(SalesDomainEvent):
    """Raised when a Delivery Note is cancelled (reservation released)."""

    event_type: str = field(default="sales.delivery.cancelled", init=False)
    aggregate_type: str = field(default="DeliveryNote", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    delivery_note_id: UUID = field(default_factory=lambda: UUID(int=0))
    delivery_number: str = ""
    order_id: str = ""
    customer_id: str = ""
    previous_status: str = ""
