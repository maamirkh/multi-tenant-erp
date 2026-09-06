"""Customer domain events for Phase 1.

Events published via InProcessEventBus for cross-module coordination
and future message-broker integration.

Event taxonomy:
  customer.created               — new customer record created (DRAFT)
  customer.activated             — DRAFT/INACTIVE → ACTIVE
  customer.updated               — core fields changed
  customer.on_hold               — ACTIVE → ON_HOLD
  customer.hold_released         — ON_HOLD → ACTIVE
  customer.blocked               — ACTIVE → BLOCKED
  customer.unblocked             — BLOCKED → ACTIVE
  customer.deactivated           — ACTIVE → INACTIVE
  customer.credit_limit_changed  — credit_limit updated by Finance Manager
  customer.credit_hold_placed    — credit_status → HOLD
  customer.credit_hold_released  — credit_status HOLD → GOOD/WARNING

Spec ref: specs/007-sales-management/spec.md §34 Domain Events
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from modules.sales.events import SalesDomainEvent


@dataclass
class CustomerCreated(SalesDomainEvent):
    """Raised when a new customer is created in DRAFT status."""

    event_type: str = field(default="customer.created", init=False)
    aggregate_type: str = field(default="Customer", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    customer_code: str = ""
    legal_name: str = ""
    customer_type: str = ""
    created_by: UUID | None = None


@dataclass
class CustomerActivated(SalesDomainEvent):
    """Raised when a customer transitions to ACTIVE status."""

    event_type: str = field(default="customer.activated", init=False)
    aggregate_type: str = field(default="Customer", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    previous_status: str = ""
    activated_by: UUID | None = None


@dataclass
class CustomerUpdated(SalesDomainEvent):
    """Raised when core customer fields are changed."""

    event_type: str = field(default="customer.updated", init=False)
    aggregate_type: str = field(default="Customer", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    changed_fields: list[str] = field(default_factory=list)
    updated_by: UUID | None = None


@dataclass
class CustomerOnHold(SalesDomainEvent):
    """Raised when a customer is placed on hold (ACTIVE → ON_HOLD)."""

    event_type: str = field(default="customer.on_hold", init=False)
    aggregate_type: str = field(default="Customer", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    reason: str = ""
    placed_by: UUID | None = None


@dataclass
class CustomerHoldReleased(SalesDomainEvent):
    """Raised when a customer hold is released (ON_HOLD → ACTIVE)."""

    event_type: str = field(default="customer.hold_released", init=False)
    aggregate_type: str = field(default="Customer", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    released_by: UUID | None = None


@dataclass
class CustomerBlocked(SalesDomainEvent):
    """Raised when a customer is blocked (ACTIVE → BLOCKED)."""

    event_type: str = field(default="customer.blocked", init=False)
    aggregate_type: str = field(default="Customer", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    reason: str = ""
    blocked_by: UUID | None = None


@dataclass
class CustomerUnblocked(SalesDomainEvent):
    """Raised when a customer block is resolved (BLOCKED → ACTIVE)."""

    event_type: str = field(default="customer.unblocked", init=False)
    aggregate_type: str = field(default="Customer", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    unblocked_by: UUID | None = None


@dataclass
class CustomerDeactivated(SalesDomainEvent):
    """Raised when a customer is deactivated (ACTIVE → INACTIVE)."""

    event_type: str = field(default="customer.deactivated", init=False)
    aggregate_type: str = field(default="Customer", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    deactivated_by: UUID | None = None


@dataclass
class CustomerCreditLimitChanged(SalesDomainEvent):
    """Raised when a customer's credit limit is updated by Finance Manager."""

    event_type: str = field(default="customer.credit_limit_changed", init=False)
    aggregate_type: str = field(default="Customer", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    previous_credit_limit: float = 0.0
    new_credit_limit: float = 0.0
    changed_by: UUID | None = None


@dataclass
class CustomerCreditHoldPlaced(SalesDomainEvent):
    """Raised when credit_status transitions to HOLD."""

    event_type: str = field(default="customer.credit_hold_placed", init=False)
    aggregate_type: str = field(default="Customer", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    credit_limit: float = 0.0
    credit_used: float = 0.0
    placed_by: UUID | None = None


@dataclass
class CustomerCreditHoldReleased(SalesDomainEvent):
    """Raised when credit_status transitions from HOLD to GOOD/WARNING."""

    event_type: str = field(default="customer.credit_hold_released", init=False)
    aggregate_type: str = field(default="Customer", init=False)
    aggregate_id: UUID = field(default_factory=lambda: UUID(int=0))
    company_id: UUID = field(default_factory=lambda: UUID(int=0))
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    customer_id: UUID = field(default_factory=lambda: UUID(int=0))
    new_credit_status: str = "GOOD"
    released_by: UUID | None = None
