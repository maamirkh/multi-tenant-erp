# Domain Events Contract: Epic 9 — CRM

Mirrors Epic 8's `contracts/events.md` envelope-table format. All events use `modules/crm/events/__init__.py`'s `CrmDomainEvent` dataclass base and are published via CRM's own in-process `EventBus` (`get_event_bus()`), matching the "each module owns its own bus" convention already established by Sales/Accounting/Purchase — no shared/global bus instance.

## Event Schema Conventions

Every event carries this envelope (from `CrmDomainEvent`):

| Field | Type | Notes |
|---|---|---|
| `event_id` | UUID | auto-generated |
| `event_type` | string | e.g. `crm.lead.created` |
| `event_version` | int | `1` for all Epic 9 events |
| `aggregate_type` | string | `Lead` / `Opportunity` / `Activity` |
| `aggregate_id` | UUID | the entity's own id |
| `company_id` | UUID | tenant scope |
| `occurred_at` | ISO 8601 datetime | server-set |
| `actor_id` | UUID \| null | `None` for system-initiated events |
| `correlation_id` | string \| null | |

Publish discipline (plan.md §19.3): every `publish()` call happens **after** the triggering write's `db.commit()`, never before — an event is only emitted once its underlying state change is durable.

## Events Published by CRM (Outbound)

### Lead events (`modules/crm/events/lead_events.py`)

| Event Type | Trigger | Extra Payload |
|---|---|---|
| `crm.lead.created` | Lead captured | `lead_id`, `source_id` |
| `crm.lead.status_changed` | Any status transition | `lead_id`, `from_status`, `to_status` |
| `crm.lead.qualified` | Status → `QUALIFIED` | `lead_id` |
| `crm.lead.assigned` | `owner_id` changed | `lead_id`, `owner_id` |
| `crm.lead.converted` | Successful conversion (spec.md §16) | `lead_id`, `customer_id`, `opportunity_id`, `customer_matched` |

### Opportunity events (`modules/crm/events/opportunity_events.py`)

| Event Type | Trigger | Extra Payload |
|---|---|---|
| `crm.opportunity.created` | Opportunity created (manual or via conversion) | `opportunity_id`, `customer_id`, `source_lead_id` |
| `crm.opportunity.stage_changed` | Stage change while still `OPEN` | `opportunity_id`, `from_stage_id`, `to_stage_id` |
| `crm.opportunity.assigned` | `owner_id` changed | `opportunity_id`, `owner_id` |
| `crm.opportunity.won` | Status → `WON` | `opportunity_id`, `value`, `currency_code` |
| `crm.opportunity.lost` | Status → `LOST` | `opportunity_id`, `lost_reason` |

### Activity events (`modules/crm/events/activity_events.py`)

| Event Type | Trigger | Extra Payload |
|---|---|---|
| `crm.activity.created` | Activity logged (including the 2 integration-handler-generated NOTE activities below) | `activity_id`, `activity_type` |
| `crm.activity.completed` | Status → `COMPLETED` | `activity_id`, `activity_type` |

12 events total, matching spec.md §36 exactly.

## Events Consumed by CRM (Inbound)

CRM subscribes to 2 events **already published by Sales**, on Sales' own event bus instance (`modules.sales.events.get_event_bus()`) — no Sales file is modified to enable this (`modules/crm/handlers/integration_handlers.py`).

| Event Type (real, verified) | Publisher | CRM Handler | Effect |
|---|---|---|---|
| `quotation.accepted` | Sales (`QuotationAccepted`) | `handle_quotation_accepted` | Writes one `NOTE` Activity on the customer's most-recent Opportunity owner, for visibility only |
| `sales.order.credit_hold` | Sales (`OrderCreditHold`) | `handle_order_credit_hold` | Writes one `NOTE` Activity, same visibility-only pattern |

Both handlers are pure additive event *consumers* — no Opportunity/Lead state is mutated, no Sales write occurs. If the customer has no CRM Opportunity yet (no owner to notify), the event is logged and dropped (graceful no-op, not an error), matching Accounting's own inbound-handler precedent.

**Note on event-name verification**: spec.md's prose names the quotation event `sales.quotation.accepted`; the actual, currently-published event type (verified against `modules.sales.events.quotation_events.QuotationAccepted` before implementation) is `quotation.accepted` — no `sales.` prefix. The credit-hold event name matches spec.md exactly. This file documents the real, verified names.

Registration: `register_crm_integration_handlers()` is called once from `backend/main.py`'s `lifespan`, alongside the existing Accounting integration-handler registration call.

## Event Versioning

All 12 events are `event_version=1` at Epic 9 close. Payload changes to a published event in a future epic must bump `event_version` and remain additive (new optional fields only) to avoid breaking any future consumer — the same discipline already applied to Sales/Accounting events.

## Integration Guarantees

- Zero Sales/Accounting file modified to enable event consumption (subscribes onto the *producer's* existing bus instance).
- Zero write to any `sales_*`/`accounting_*` table from any CRM event handler.
- CRM's own event bus (used for the 12 outbound events) is entirely independent of Sales'/Accounting's bus instances — no cross-module publish, only cross-module *subscribe*.
