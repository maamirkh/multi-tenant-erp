"""Accounts Receivable domain events — Phase 6.

  CreditHoldPlacedEvent       — ``accounting.ar.customer.credithold``
  CreditHoldReleasedEvent     — ``accounting.ar.customer.credithold.released``
  InvoiceOverdueEvent         — ``accounting.ar.invoice.overdue``
  CreditLimitWarningEvent     — ``accounting.ar.customer.creditlimit.warning``

Spec ref: specs/008-accounting-finance/tasks.md T137, T143
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from modules.accounting.events import AccountingDomainEvent


@dataclass
class CreditHoldPlacedEvent(AccountingDomainEvent):
    """``accounting.ar.customer.credithold`` — published by ``place_credit_hold()``."""

    customer_id: UUID | None = None
    customer_ledger_id: UUID | None = None
    reason: str | None = None
    placed_by: UUID | None = None


@dataclass
class CreditHoldReleasedEvent(AccountingDomainEvent):
    """``accounting.ar.customer.credithold.released`` — published by ``release_credit_hold()``."""

    customer_id: UUID | None = None
    customer_ledger_id: UUID | None = None
    new_credit_status: str | None = None
    released_by: UUID | None = None


@dataclass
class InvoiceOverdueEvent(AccountingDomainEvent):
    """``accounting.ar.invoice.overdue`` — published by the daily AR overdue check job."""

    ar_transaction_id: UUID | None = None
    customer_id: UUID | None = None
    invoice_number: str | None = None
    due_date: str | None = None
    outstanding_amount: Decimal | None = None


@dataclass
class CreditLimitWarningEvent(AccountingDomainEvent):
    """``accounting.ar.customer.creditlimit.warning`` — published at the warning threshold."""

    customer_id: UUID | None = None
    customer_ledger_id: UUID | None = None
    credit_limit: Decimal | None = None
    total_outstanding_base: Decimal | None = None
    utilization_pct: Decimal | None = None


__all__ = [
    "CreditHoldPlacedEvent",
    "CreditHoldReleasedEvent",
    "CreditLimitWarningEvent",
    "InvoiceOverdueEvent",
]
