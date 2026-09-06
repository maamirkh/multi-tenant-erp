"""Accounting domain events and in-process EventBus.

Provides:
  - ``AccountingDomainEvent`` — base dataclass for all accounting domain events
  - ``EventBus``              — abstract interface (publish/subscribe)
  - ``InProcessEventBus``     — synchronous in-process implementation

The EventBus is intentionally synchronous to avoid external dependencies.
The interface is designed so a future message-broker implementation
(RabbitMQ, Redis Streams) can be swapped in without changing callers.

Reuses the same EventBus pattern established in Epic 5 (Inventory), Epic 6
(Purchase), and Epic 7 (Sales) modules. As with those modules, this bus is
independent of Sales/Purchase/Inventory's own bus instances — cross-module
event consumption subscribes directly on the producing module's bus (see
Phase 0 quickstart.md "Phase 0 Verification Findings").

Spec ref: specs/008-accounting-finance/contracts/events.md
Plan ref: specs/008-accounting-finance/plan.md Phase 1
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from core.utils.datetime import utcnow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base domain event
# ---------------------------------------------------------------------------


@dataclass
class AccountingDomainEvent:
    """Base class for all accounting domain events.

    Every concrete event inherits this class and adds its own payload fields.
    The ``event_id`` is a stable UUID that uniquely identifies this event
    occurrence — suitable for idempotency checks in downstream consumers.

    ``aggregate_type`` and ``aggregate_id`` identify the entity that produced
    the event (e.g. ``"JournalEntry"`` / ``<journal_entry_uuid>``).
    """

    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    company_id: UUID
    occurred_at: datetime = field(default_factory=utcnow)
    event_id: UUID = field(default_factory=uuid4)
    actor_id: UUID | None = None
    correlation_id: str | None = None
    event_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Return a serialisable dict representation of this event."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "event_version": self.event_version,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": str(self.aggregate_id),
            "company_id": str(self.company_id),
            "occurred_at": self.occurred_at.isoformat(),
            "actor_id": str(self.actor_id) if self.actor_id else None,
            "correlation_id": self.correlation_id,
        }


# ---------------------------------------------------------------------------
# EventBus interface
# ---------------------------------------------------------------------------

HandlerType = Callable[[AccountingDomainEvent], None]


class EventBus(ABC):
    """Abstract interface for the accounting domain event bus.

    Implementations may be synchronous (in-process) or asynchronous
    (message broker). All callers depend only on this interface.
    """

    @abstractmethod
    def publish(self, event: AccountingDomainEvent) -> None:
        """Publish an event to all registered subscribers."""

    @abstractmethod
    def subscribe(self, event_type: str, handler: HandlerType) -> None:
        """Register a handler for a specific event type.

        Use ``"*"`` to subscribe to all events.
        """

    @abstractmethod
    def clear_handlers(self) -> None:
        """Remove all registered handlers. Primarily used in tests."""


# ---------------------------------------------------------------------------
# In-process synchronous implementation
# ---------------------------------------------------------------------------


class InProcessEventBus(EventBus):
    """Synchronous, in-process EventBus implementation.

    Events are dispatched immediately and synchronously in the same thread
    as the publisher. Handler exceptions are caught and logged — they do NOT
    propagate to the publisher so a faulty subscriber cannot break the
    primary operation (e.g. a GL posting must still commit even if a
    notification handler fails).
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[HandlerType]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: HandlerType) -> None:
        """Register a handler for ``event_type`` (or ``"*"`` for all)."""
        self._handlers[event_type].append(handler)
        logger.debug(
            "AccountingEventBus: subscribed handler %s to '%s'",
            getattr(handler, "__qualname__", repr(handler)),
            event_type,
        )

    def publish(self, event: AccountingDomainEvent) -> None:
        """Dispatch ``event`` to all matching and wildcard handlers."""
        logger.debug(
            "AccountingEventBus: publishing %s (aggregate=%s/%s company=%s)",
            event.event_type,
            event.aggregate_type,
            event.aggregate_id,
            event.company_id,
        )
        handlers = list(self._handlers.get(event.event_type, []))
        handlers += list(self._handlers.get("*", []))

        for handler in handlers:
            try:
                handler(event)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "AccountingEventBus: handler %s raised an exception for event %s",
                    getattr(handler, "__qualname__", repr(handler)),
                    event.event_type,
                )

    def clear_handlers(self) -> None:
        """Remove all registered handlers."""
        self._handlers.clear()

    def handler_count(self, event_type: str | None = None) -> int:
        """Return the number of registered handlers."""
        if event_type is not None:
            return len(self._handlers.get(event_type, []))
        return sum(len(hs) for hs in self._handlers.values())


# ---------------------------------------------------------------------------
# Module-level singleton (overridable in tests)
# ---------------------------------------------------------------------------

#: Module-level event bus singleton — can be replaced in tests.
_accounting_event_bus: EventBus = InProcessEventBus()


def get_event_bus() -> EventBus:
    """Return the active accounting EventBus instance."""
    return _accounting_event_bus


def set_event_bus(bus: EventBus) -> None:
    """Replace the active EventBus — used in tests and DI wiring."""
    global _accounting_event_bus  # noqa: PLW0603
    _accounting_event_bus = bus


__all__ = [
    "AccountingDomainEvent",
    "EventBus",
    "InProcessEventBus",
    "get_event_bus",
    "set_event_bus",
]
