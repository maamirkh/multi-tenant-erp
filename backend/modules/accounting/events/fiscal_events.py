"""Fiscal Calendar domain events — Phase 3.

  PeriodLockedEvent      — ``accounting.period.locked``
  PeriodUnlockedEvent    — ``accounting.period.unlocked``
  PeriodClosedEvent      — ``accounting.period.closed``
  FiscalYearClosedEvent  — ``accounting.fiscalyear.closed``

All payload fields follow ``contracts/events.md`` field names as closely as
the actual codebase event envelope allows (flat dataclass, no ``tenant_id``
— see ``events/__init__.py`` docstring and quickstart.md "Phase 0
Verification Findings"). Fields not present on ``AccountingDomainEvent``
(e.g. ``fiscal_year_id``, ``lock_reason``) are added per-event below.

Spec ref: specs/008-accounting-finance/contracts/events.md, tasks.md T075
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from modules.accounting.events import AccountingDomainEvent


@dataclass
class PeriodLockedEvent(AccountingDomainEvent):
    """``accounting.period.locked`` — consumed by Sales, Purchase, Inventory.

    All operational modules must reject new postings dated within this
    period once this event is observed (see ``handlers/period_lock_handler.py``).
    """

    fiscal_year_id: UUID | None = None
    fiscal_period_id: UUID | None = None
    period_number: int | None = None
    period_name: str | None = None
    period_start_date: date | None = None
    period_end_date: date | None = None
    locked_by_user_id: UUID | None = None
    lock_reason: str | None = None


@dataclass
class PeriodUnlockedEvent(AccountingDomainEvent):
    """``accounting.period.unlocked`` — a locked period reopened by a Controller."""

    fiscal_period_id: UUID | None = None
    period_name: str | None = None
    unlocked_by_user_id: UUID | None = None
    reason: str | None = None


@dataclass
class PeriodClosedEvent(AccountingDomainEvent):
    """``accounting.period.closed`` — a period permanently closed (year-end close)."""

    fiscal_period_id: UUID | None = None
    period_name: str | None = None
    closed_at: datetime | None = None


@dataclass
class FiscalYearClosedEvent(AccountingDomainEvent):
    """``accounting.fiscalyear.closed`` — year-end close process completed.

    ``closing_journal_entry_id`` and ``net_income_transferred`` are ``None``
    in Phase 3: computing the actual closing entry requires the PostingEngine
    and JournalEntry aggregate, which do not exist until Phase 4. This is a
    documented gap (same pattern as Phase 2's GL-activity check) — Phase 4
    must populate these fields when ``execute_year_end_close`` gains the
    ability to call the PostingEngine.
    """

    fiscal_year_id: UUID | None = None
    fiscal_year_name: str | None = None
    closing_journal_entry_id: UUID | None = None
    net_income_transferred: str | None = None
    retained_earnings_account_id: UUID | None = None
    closed_at: datetime | None = None


__all__ = [
    "FiscalYearClosedEvent",
    "PeriodClosedEvent",
    "PeriodLockedEvent",
    "PeriodUnlockedEvent",
]
