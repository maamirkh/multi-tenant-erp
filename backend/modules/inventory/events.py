"""Inventory domain events and in-process EventBus.

Provides:
  - ``InventoryDomainEvent``  — base dataclass for all inventory domain events
  - ``EventBus``              — abstract interface (publish/subscribe)
  - ``InProcessEventBus``     — synchronous in-process implementation for Phase 0

The EventBus is intentionally synchronous in Phase 0 to avoid external
dependencies. The interface is async-ready so a future message-broker
implementation (RabbitMQ, Redis Streams) can be swapped in without
changing callers.

Spec ref: specs/005-inventory-management/spec.md §31 Domain Events
Plan ref: specs/005-inventory-management/plan.md Phase 0
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
class InventoryDomainEvent:
    """Base class for all inventory domain events.

    Every concrete event inherits this class and adds its own payload fields.
    The ``event_id`` is a stable UUID that uniquely identifies this event
    occurrence — suitable for idempotency checks in downstream consumers.

    ``aggregate_type`` and ``aggregate_id`` identify the entity that produced
    the event (e.g. ``"Product"`` / ``<product_uuid>``).
    """

    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    company_id: UUID
    occurred_at: datetime = field(default_factory=utcnow)
    event_id: UUID = field(default_factory=uuid4)
    actor_id: UUID | None = None
    correlation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a serialisable dict representation of this event."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
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

HandlerType = Callable[[InventoryDomainEvent], None]


class EventBus(ABC):
    """Abstract interface for the inventory domain event bus.

    Implementations may be synchronous (in-process) or asynchronous
    (message broker). All callers depend only on this interface.
    """

    @abstractmethod
    def publish(self, event: InventoryDomainEvent) -> None:
        """Publish an event to all registered subscribers.

        Args:
            event: The domain event to publish.
        """

    @abstractmethod
    def subscribe(self, event_type: str, handler: HandlerType) -> None:
        """Register a handler for a specific event type.

        Args:
            event_type: The ``event_type`` string to subscribe to.
                        Use ``"*"`` to subscribe to all events.
            handler: A callable that accepts an ``InventoryDomainEvent``.
        """

    @abstractmethod
    def clear_handlers(self) -> None:
        """Remove all registered handlers.

        Primarily used in tests to isolate handler registration between
        test cases.
        """


# ---------------------------------------------------------------------------
# In-process synchronous implementation
# ---------------------------------------------------------------------------


class InProcessEventBus(EventBus):
    """Synchronous, in-process EventBus implementation.

    Events are dispatched immediately and synchronously in the same thread
    as the publisher. Suitable for Phase 0 and testing.

    Handler exceptions are caught and logged — they do NOT propagate to
    the publisher so a faulty subscriber cannot break the primary operation.

    Thread safety: This implementation is NOT thread-safe. In production,
    use a message-broker implementation instead.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[HandlerType]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: HandlerType) -> None:
        """Register a handler for ``event_type`` (or ``"*"`` for all)."""
        self._handlers[event_type].append(handler)
        logger.debug(
            "EventBus: subscribed handler %s to '%s'",
            getattr(handler, "__qualname__", repr(handler)),
            event_type,
        )

    def publish(self, event: InventoryDomainEvent) -> None:
        """Dispatch ``event`` to all matching and wildcard handlers."""
        logger.debug(
            "EventBus: publishing %s (aggregate=%s/%s company=%s)",
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
                    "EventBus: handler %s raised an exception for event %s",
                    getattr(handler, "__qualname__", repr(handler)),
                    event.event_type,
                )

    def clear_handlers(self) -> None:
        """Remove all registered handlers."""
        self._handlers.clear()

    def handler_count(self, event_type: str | None = None) -> int:
        """Return the number of registered handlers.

        Args:
            event_type: If provided, count handlers for this specific type.
                        If None, count all handlers across all types.
        """
        if event_type is not None:
            return len(self._handlers.get(event_type, []))
        return sum(len(hs) for hs in self._handlers.values())


# ---------------------------------------------------------------------------
# Module-level singleton (overridable in tests)
# ---------------------------------------------------------------------------

#: Module-level event bus singleton — can be replaced in tests.
_inventory_event_bus: EventBus = InProcessEventBus()


def get_event_bus() -> EventBus:
    """Return the active inventory EventBus instance."""
    return _inventory_event_bus


def set_event_bus(bus: EventBus) -> None:
    """Replace the active EventBus — used in tests and DI wiring."""
    global _inventory_event_bus  # noqa: PLW0603
    _inventory_event_bus = bus


__all__ = [
    "EventBus",
    "InProcessEventBus",
    "InventoryDomainEvent",
    "get_event_bus",
    "set_event_bus",
]
