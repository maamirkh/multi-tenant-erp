"""Opportunity domain events — spec.md §36.2.

Event taxonomy:
  crm.opportunity.created        — Opportunity created
  crm.opportunity.stage_changed  — stage change within OPEN
  crm.opportunity.assigned       — owner_id changed
  crm.opportunity.won            — status -> WON
  crm.opportunity.lost           — status -> LOST

Spec ref: specs/009-crm/spec.md §36.2; plan.md §19.2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from modules.crm.events import CrmDomainEvent


@dataclass
class OpportunityCreated(CrmDomainEvent):
    """Raised when a new Opportunity is created."""

    event_type: str = field(default="crm.opportunity.created", init=False)
    aggregate_type: str = field(default="Opportunity", init=False)

    opportunity_id: UUID = field(default_factory=lambda: UUID(int=0))
    customer_id: str = ""
    source_lead_id: UUID | None = None


@dataclass
class OpportunityStageChanged(CrmDomainEvent):
    """Raised on a stage change while the Opportunity remains OPEN."""

    event_type: str = field(default="crm.opportunity.stage_changed", init=False)
    aggregate_type: str = field(default="Opportunity", init=False)

    opportunity_id: UUID = field(default_factory=lambda: UUID(int=0))
    from_stage_id: UUID = field(default_factory=lambda: UUID(int=0))
    to_stage_id: UUID = field(default_factory=lambda: UUID(int=0))


@dataclass
class OpportunityAssigned(CrmDomainEvent):
    """Raised when an Opportunity's owner_id changes."""

    event_type: str = field(default="crm.opportunity.assigned", init=False)
    aggregate_type: str = field(default="Opportunity", init=False)

    opportunity_id: UUID = field(default_factory=lambda: UUID(int=0))
    owner_id: str = ""


@dataclass
class OpportunityWon(CrmDomainEvent):
    """Raised when an Opportunity's status becomes WON."""

    event_type: str = field(default="crm.opportunity.won", init=False)
    aggregate_type: str = field(default="Opportunity", init=False)

    opportunity_id: UUID = field(default_factory=lambda: UUID(int=0))
    value: Decimal = Decimal("0")
    currency_code: str = "USD"


@dataclass
class OpportunityLost(CrmDomainEvent):
    """Raised when an Opportunity's status becomes LOST."""

    event_type: str = field(default="crm.opportunity.lost", init=False)
    aggregate_type: str = field(default="Opportunity", init=False)

    opportunity_id: UUID = field(default_factory=lambda: UUID(int=0))
    lost_reason: str = ""
