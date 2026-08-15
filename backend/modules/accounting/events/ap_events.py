"""Accounts Payable domain events — Phase 7.

  BillDueEvent — ``accounting.ap.bill.due``

Spec ref: specs/008-accounting-finance/contracts/events.md,
specs/008-accounting-finance/tasks.md T166
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from modules.accounting.events import AccountingDomainEvent


@dataclass
class BillDueEvent(AccountingDomainEvent):
    """``accounting.ap.bill.due`` — published by the daily bill-due-reminder job."""

    ap_transaction_id: UUID | None = None
    supplier_id: UUID | None = None
    bill_number: str | None = None
    due_date: str | None = None
    days_until_due: int | None = None
    outstanding_amount_base: Decimal | None = None


__all__ = ["BillDueEvent"]
