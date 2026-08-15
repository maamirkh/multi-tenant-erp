"""Period lock cache handler — Phase 3.

Subscribes to ``accounting.period.locked`` / ``.unlocked`` / ``.closed`` and
maintains an in-memory, per-company cache of non-OPEN fiscal periods. This
is the exact lookup the PostingEngine (Phase 4, spec.md §14 Step 3) will
consult before allowing a journal to post, without a DB round-trip on every
candidate check.

Cross-module scope (task T076 asks this to be wired into Sales/Purchase/
Inventory's own PostingServices): verified by code search that none of
those three modules has any GL-posting/"PostingService" concept today —
all three currently only *publish* domain events; nothing in this codebase
*subscribes* to another module's event bus (Accounting included). GL
posting for Sales/Purchase/Inventory-originated transactions is exclusively
Accounting's Phase 4 responsibility, consuming their *outbound* events via
``handlers/integration_handlers.py`` — not the reverse. Registering a new,
speculative cross-module subscription against those already-shipped Epics
ahead of that real integration point would invent an API/contract that
doesn't exist yet, which the project's default policies explicitly avoid.
This cache is therefore built and wired to Accounting's own event bus now
(fully functional), and is ready for Phase 4's PostingEngine and, if a
future phase adds pre-check gating to Sales/Purchase/Inventory, for those
modules to subscribe to as well.

Spec ref: specs/008-accounting-finance/tasks.md T076
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from modules.accounting.events import AccountingDomainEvent, EventBus, get_event_bus
from modules.accounting.events.fiscal_events import (
    PeriodClosedEvent,
    PeriodLockedEvent,
    PeriodUnlockedEvent,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _LockedPeriodEntry:
    fiscal_period_id: UUID
    start_date: date
    end_date: date
    status: str  # "LOCKED" or "CLOSED"


class PeriodLockCache:
    """In-memory cache of non-OPEN fiscal periods, keyed by ``company_id``."""

    def __init__(self) -> None:
        self._entries: dict[UUID, dict[UUID, _LockedPeriodEntry]] = {}

    def mark_locked(
        self,
        company_id: UUID,
        fiscal_period_id: UUID,
        start_date: date,
        end_date: date,
    ) -> None:
        self._entries.setdefault(company_id, {})[fiscal_period_id] = _LockedPeriodEntry(
            fiscal_period_id=fiscal_period_id,
            start_date=start_date,
            end_date=end_date,
            status="LOCKED",
        )

    def mark_closed(self, company_id: UUID, fiscal_period_id: UUID) -> None:
        existing = self._entries.get(company_id, {}).get(fiscal_period_id)
        if existing is not None:
            self._entries[company_id][fiscal_period_id] = _LockedPeriodEntry(
                fiscal_period_id=existing.fiscal_period_id,
                start_date=existing.start_date,
                end_date=existing.end_date,
                status="CLOSED",
            )

    def unmark(self, company_id: UUID, fiscal_period_id: UUID) -> None:
        self._entries.get(company_id, {}).pop(fiscal_period_id, None)

    def is_locked(self, company_id: UUID, check_date: date) -> bool:
        """Return True if any cached LOCKED/CLOSED period covers ``check_date``."""
        for entry in self._entries.get(company_id, {}).values():
            if entry.start_date <= check_date <= entry.end_date:
                return True
        return False

    def clear(self) -> None:
        """Remove all cached entries — primarily used in tests."""
        self._entries.clear()


#: Module-level singleton — can be replaced/cleared in tests.
_period_lock_cache = PeriodLockCache()


def get_period_lock_cache() -> PeriodLockCache:
    """Return the active ``PeriodLockCache`` instance."""
    return _period_lock_cache


def _on_period_locked(event: AccountingDomainEvent) -> None:
    if not isinstance(event, PeriodLockedEvent):
        return
    if event.fiscal_period_id is None:
        return
    if event.period_start_date is None or event.period_end_date is None:
        return
    _period_lock_cache.mark_locked(
        company_id=event.company_id,
        fiscal_period_id=event.fiscal_period_id,
        start_date=event.period_start_date,
        end_date=event.period_end_date,
    )
    logger.debug(
        "PeriodLockCache: locked period %s cached for company %s",
        event.fiscal_period_id,
        event.company_id,
    )


def _on_period_unlocked(event: AccountingDomainEvent) -> None:
    if not isinstance(event, PeriodUnlockedEvent) or event.fiscal_period_id is None:
        return
    _period_lock_cache.unmark(
        company_id=event.company_id, fiscal_period_id=event.fiscal_period_id
    )
    logger.debug(
        "PeriodLockCache: period %s uncached (unlocked) for company %s",
        event.fiscal_period_id,
        event.company_id,
    )


def _on_period_closed(event: AccountingDomainEvent) -> None:
    if not isinstance(event, PeriodClosedEvent) or event.fiscal_period_id is None:
        return
    _period_lock_cache.mark_closed(
        company_id=event.company_id, fiscal_period_id=event.fiscal_period_id
    )
    logger.debug(
        "PeriodLockCache: period %s marked CLOSED for company %s",
        event.fiscal_period_id,
        event.company_id,
    )


def register_period_lock_handlers(bus: EventBus | None = None) -> None:
    """Subscribe the period-lock cache handlers to the accounting EventBus.

    Idempotent to call multiple times is NOT guaranteed by the underlying
    ``InProcessEventBus`` (it appends handlers) — callers (module startup,
    test fixtures) should call this exactly once per bus instance.
    """
    target_bus = bus or get_event_bus()
    target_bus.subscribe("accounting.period.locked", _on_period_locked)
    target_bus.subscribe("accounting.period.unlocked", _on_period_unlocked)
    target_bus.subscribe("accounting.period.closed", _on_period_closed)


__all__ = [
    "PeriodLockCache",
    "get_period_lock_cache",
    "register_period_lock_handlers",
]
