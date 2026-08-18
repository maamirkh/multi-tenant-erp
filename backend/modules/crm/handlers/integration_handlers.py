"""Integration event handlers — CRM consuming Sales' existing events.

Subscribes CRM to 2 events Sales ALREADY publishes (spec.md §21.2, plan.md
§15.4) — no Sales file is modified to make this possible, mirroring
``modules/accounting/handlers/integration_handlers.py``'s own confirmed
pattern for cross-module event subscription (subscribing onto the
PRODUCER module's bus instance, not CRM's own).

**Event-name correction** (verified against the actual codebase before
implementing, per this task's own explicit instruction — spec.md's prose
names the quotation event ``sales.quotation.accepted``, but the real,
currently-published event type, confirmed in
``modules.sales.events.quotation_events.QuotationAccepted``, is
``"quotation.accepted"`` — no ``sales.`` prefix. The credit-hold event
name IS exactly as documented: ``"sales.order.credit_hold"``
(``modules.sales.events.order_events.OrderCreditHold``). This module
subscribes to the real event-type strings.

Both handlers write a single CRM Activity (type NOTE) for salesperson
visibility only — no state mutation on any CRM aggregate (spec.md §21.2's
explicit "human always confirms pipeline movement" invariant). Each
handler resolves an owner to assign the note to via the customer's most
recently-touched Opportunity; if no Opportunity exists yet for that
customer, the event is logged and dropped (a graceful no-op, matching
Accounting's own "silently no-ops until a precondition is met" precedent
for its own inbound handlers) rather than inventing a fake actor.

Spec ref: specs/009-crm/spec.md §21.2; plan.md §15.4.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from core.database.session import SessionLocal
from core.utils.datetime import utcnow
from modules.crm.events import get_event_bus
from modules.crm.events.activity_events import ActivityCreated
from modules.crm.models.activity import Activity
from modules.crm.repositories.activity import ActivityRepository
from modules.crm.repositories.opportunity import OpportunityRepository

logger = logging.getLogger(__name__)


def _resolve_owner_for_customer(
    db: Any, company_id: UUID, customer_id: UUID
) -> UUID | None:
    """Return the owner_id of the customer's most-recently-created
    Opportunity, or ``None`` if the customer has no CRM Opportunity yet."""
    opportunities, _ = OpportunityRepository(db).list_filtered(
        company_id, customer_id=customer_id, page=1, page_size=1
    )
    if not opportunities:
        return None
    return UUID(opportunities[0].owner_id)


def handle_quotation_accepted(event: Any) -> None:
    """Handler for Sales' ``quotation.accepted`` event.

    Payload fields (``QuotationAccepted``): ``quotation_id,
    quotation_number, customer_id, total_amount, accepted_by``. Surfaces
    the acceptance in Customer 360's timeline as a NOTE Activity — no
    Opportunity stage change is forced (spec.md §21.2).
    """
    try:
        customer_id = UUID(str(event.customer_id))
    except (ValueError, AttributeError, TypeError):
        logger.error(
            "handle_quotation_accepted: unparseable customer_id, dropping event: %r",
            event,
        )
        return

    db = SessionLocal()
    try:
        owner_id = _resolve_owner_for_customer(db, event.company_id, customer_id)
        if owner_id is None:
            logger.debug(
                "handle_quotation_accepted: no Opportunity/owner found for "
                "customer %s in company %s — dropping event",
                customer_id,
                event.company_id,
            )
            return

        activity = ActivityRepository(db).create(
            Activity(
                company_id=event.company_id,
                activity_type="NOTE",
                subject=f"Quotation {event.quotation_number} accepted",
                description=(
                    f"Quotation {event.quotation_number} was accepted by the "
                    f"customer (total {event.total_amount})."
                ),
                status="COMPLETED",
                completed_at=utcnow(),
                assigned_to=str(owner_id),
                customer_id=str(customer_id),
            )
        )
        get_event_bus().publish(
            ActivityCreated(
                aggregate_id=activity.id,
                company_id=event.company_id,
                activity_id=activity.id,
                activity_type="NOTE",
            )
        )
    finally:
        db.close()


def handle_order_credit_hold(event: Any) -> None:
    """Handler for Sales' ``sales.order.credit_hold`` event.

    Payload fields (``OrderCreditHold``): ``order_id, order_number,
    customer_id, credit_status, credit_limit, outstanding_balance,
    order_total``. Logged as a CRM Activity/note for salesperson
    visibility only — never a blocking action (spec.md §21.2).
    """
    try:
        customer_id = UUID(str(event.customer_id))
    except (ValueError, AttributeError, TypeError):
        logger.error(
            "handle_order_credit_hold: unparseable customer_id, dropping event: %r",
            event,
        )
        return

    db = SessionLocal()
    try:
        owner_id = _resolve_owner_for_customer(db, event.company_id, customer_id)
        if owner_id is None:
            logger.debug(
                "handle_order_credit_hold: no Opportunity/owner found for "
                "customer %s in company %s — dropping event",
                customer_id,
                event.company_id,
            )
            return

        activity = ActivityRepository(db).create(
            Activity(
                company_id=event.company_id,
                activity_type="NOTE",
                subject=f"Order {event.order_number} on credit hold",
                description=(
                    f"Order {event.order_number} was blocked by a credit "
                    f"check (status={event.credit_status}, "
                    f"outstanding={event.outstanding_balance}, "
                    f"limit={event.credit_limit})."
                ),
                status="COMPLETED",
                completed_at=utcnow(),
                assigned_to=str(owner_id),
                customer_id=str(customer_id),
            )
        )
        get_event_bus().publish(
            ActivityCreated(
                aggregate_id=activity.id,
                company_id=event.company_id,
                activity_id=activity.id,
                activity_type="NOTE",
            )
        )
    finally:
        db.close()


def register_crm_integration_handlers() -> None:
    """Subscribe CRM's 2 handlers to Sales's real event bus.

    Idempotent-in-intent but ``InProcessEventBus.subscribe`` itself simply
    appends — callers (module startup, test fixtures) should call this
    exactly once per Sales bus instance, matching Accounting's own
    ``register_integration_handlers`` documented caveat.
    """
    from modules.sales.events import get_event_bus as get_sales_event_bus

    sales_bus = get_sales_event_bus()
    sales_bus.subscribe("quotation.accepted", handle_quotation_accepted)
    sales_bus.subscribe("sales.order.credit_hold", handle_order_credit_hold)


__all__ = [
    "handle_order_credit_hold",
    "handle_quotation_accepted",
    "register_crm_integration_handlers",
]
