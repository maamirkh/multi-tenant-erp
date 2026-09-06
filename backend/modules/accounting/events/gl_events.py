"""General Ledger domain events — Phase 4.

  JournalPostedEvent    — ``accounting.journal.posted``
  JournalReversedEvent  — ``accounting.journal.reversed``

Spec ref: specs/008-accounting-finance/contracts/events.md, tasks.md T093 Step 8
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from modules.accounting.events import AccountingDomainEvent


@dataclass
class JournalPostedEvent(AccountingDomainEvent):
    """``accounting.journal.posted`` — published by PostingEngine Step 8."""

    journal_entry_id: UUID | None = None
    journal_number: str | None = None
    journal_type: str | None = None
    posting_source: str | None = None
    posting_date: str | None = None
    total_debit_base: Decimal | None = None
    total_credit_base: Decimal | None = None
    posted_at: datetime | None = None


@dataclass
class JournalReversedEvent(AccountingDomainEvent):
    """``accounting.journal.reversed`` — published when a POSTED entry is reversed."""

    original_journal_entry_id: UUID | None = None
    original_journal_number: str | None = None
    reversal_journal_entry_id: UUID | None = None
    reversal_journal_number: str | None = None
    reason: str | None = None


__all__ = ["JournalPostedEvent", "JournalReversedEvent"]
