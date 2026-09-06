"""Activity domain events — spec.md §36.3.

Event taxonomy:
  crm.activity.created    — Activity created
  crm.activity.completed  — status -> COMPLETED

Spec ref: specs/009-crm/spec.md §36.3; plan.md §19.2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from modules.crm.events import CrmDomainEvent


@dataclass
class ActivityCreated(CrmDomainEvent):
    """Raised when a new Activity is logged."""

    event_type: str = field(default="crm.activity.created", init=False)
    aggregate_type: str = field(default="Activity", init=False)

    activity_id: UUID = field(default_factory=lambda: UUID(int=0))
    activity_type: str = ""


@dataclass
class ActivityCompleted(CrmDomainEvent):
    """Raised when an Activity's status becomes COMPLETED."""

    event_type: str = field(default="crm.activity.completed", init=False)
    aggregate_type: str = field(default="Activity", init=False)

    activity_id: UUID = field(default_factory=lambda: UUID(int=0))
    activity_type: str = ""
