"""Lead domain events — spec.md §36.1.

Event taxonomy:
  crm.lead.created         — Lead captured
  crm.lead.status_changed  — any status transition
  crm.lead.qualified       — status -> QUALIFIED
  crm.lead.assigned        — owner_id changed
  crm.lead.converted       — successful conversion

Spec ref: specs/009-crm/spec.md §36.1; plan.md §19.2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from modules.crm.events import CrmDomainEvent


@dataclass
class LeadCreated(CrmDomainEvent):
    """Raised when a new Lead is captured."""

    event_type: str = field(default="crm.lead.created", init=False)
    aggregate_type: str = field(default="Lead", init=False)

    lead_id: UUID = field(default_factory=lambda: UUID(int=0))
    source_id: UUID | None = None


@dataclass
class LeadStatusChanged(CrmDomainEvent):
    """Raised on any Lead status transition (spec.md §14.2)."""

    event_type: str = field(default="crm.lead.status_changed", init=False)
    aggregate_type: str = field(default="Lead", init=False)

    lead_id: UUID = field(default_factory=lambda: UUID(int=0))
    from_status: str = ""
    to_status: str = ""


@dataclass
class LeadQualified(CrmDomainEvent):
    """Raised when a Lead's status becomes QUALIFIED."""

    event_type: str = field(default="crm.lead.qualified", init=False)
    aggregate_type: str = field(default="Lead", init=False)

    lead_id: UUID = field(default_factory=lambda: UUID(int=0))


@dataclass
class LeadAssigned(CrmDomainEvent):
    """Raised when a Lead's owner_id changes."""

    event_type: str = field(default="crm.lead.assigned", init=False)
    aggregate_type: str = field(default="Lead", init=False)

    lead_id: UUID = field(default_factory=lambda: UUID(int=0))
    owner_id: str = ""


@dataclass
class LeadConverted(CrmDomainEvent):
    """Raised on a successful Lead conversion (spec.md §16)."""

    event_type: str = field(default="crm.lead.converted", init=False)
    aggregate_type: str = field(default="Lead", init=False)

    lead_id: UUID = field(default_factory=lambda: UUID(int=0))
    customer_id: str = ""
    opportunity_id: UUID = field(default_factory=lambda: UUID(int=0))
    customer_matched: bool = False
