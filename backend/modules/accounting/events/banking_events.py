"""Banking domain events — Phase 8.

  BankReconciledEvent — ``accounting.bank.reconciled``

Spec ref: specs/008-accounting-finance/contracts/events.md,
specs/008-accounting-finance/tasks.md T183
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from modules.accounting.events import AccountingDomainEvent


@dataclass
class BankReconciledEvent(AccountingDomainEvent):
    """``accounting.bank.reconciled`` — published when a reconciliation is locked."""

    bank_account_id: UUID | None = None
    bank_account_name: str | None = None
    statement_date: str | None = None
    statement_closing_balance: Decimal | None = None
    gl_balance_at_date: Decimal | None = None


__all__ = ["BankReconciledEvent"]
