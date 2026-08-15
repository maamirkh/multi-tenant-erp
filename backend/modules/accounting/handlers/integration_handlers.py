"""Integration event handlers — Phase 4 (T099), extended in Phase 6 (T141/T142)
and Phase 7 (T163/T164).

Registers 8 handlers for the inbound events tasks.md/spec.md §38 describe.
Per plan.md's own Phase 4 scope ("Integration event handlers (registration
only in Phase 4; full posting logic in Phases 5-9)") and the Phase 0
findings (quickstart.md "Phase 0 Verification Findings"), the actual state
of these 8 integrations differs sharply from what was originally
documented:

| # | tasks.md handler name              | Real event (quickstart.md)                          | This phase's status |
|---|-------------------------------------|-------------------------------------------------------|----------------------|
| 1 | HandleSalesInvoicePosted            | `sales.invoice.issued` (`InvoiceIssued`)              | **Live**: creates an ``ARTransaction`` in the customer's ledger AND posts DR AR / CR Revenue to the GL, atomically (Phase 6, T141) — full amount, no tax split (event payload carries no line/tax breakdown) |
| 2 | HandleSalesCreditNotePosted         | `sales.invoice.credit_note_issued`                    | **Live**: creates a credit-note ``ARTransaction`` AND posts DR Revenue / CR AR, atomically (Phase 6, T142) |
| 3 | HandlePurchaseBillPosted            | **Does not exist** — Purchase has no Bill/AP entity   | Stub — there is nothing to subscribe to. AP bill capture is instead built inside Accounting itself (Phase 7, T163): `AccountsPayableService.record_supplier_bill()`, exposed via `POST /accounting/ap/bills`, provides the same atomic GL+AP posting a real event handler would have performed, minus the event subscription |
| 4 | HandlePurchaseCreditNotePosted      | **Does not exist**, same reason                       | Stub — mirrors #3; `AccountsPayableService.record_supplier_credit_note()` via `POST /accounting/ap/credit-notes` (Phase 7, T164) |
| 5 | HandleInventoryAdjustmentPosted     | `StockAdjusted`/`InventoryAdjustmentApproved` (real, but no GL account fields) | Stub — ADR-0004 explicitly leaves "Inventory GL-value sufficiency" as an open Phase 4+ item; no safe default account mapping exists yet |
| 6 | HandleInventoryCostUpdated          | **Does not exist** — Inventory has no cost/valuation event | Stub |
| 7 | HandleSalesPaymentReceived          | **Does not exist** — this is one of Accounting's OWN capabilities (Phase 10), not inbound | Stub — confirmed at Phase 10; real capability is `PaymentService.create_customer_payment()` / `POST /accounting/payments/customer` |
| 8 | HandleSupplierPaymentMade           | **Does not exist**, same reason                        | Stub — confirmed at Phase 10; real capability is `PaymentService.create_supplier_payment()` / `POST /accounting/payments/supplier` |

Handlers #1/#2 are wired to Sales's real `InProcessEventBus` (the first
cross-module event subscription in this codebase — see note below) and
call `AccountsReceivableService.record_sales_invoice()`/
`record_sales_credit_note()` (Phase 6), which stage the GL entry via
`PostingEngine.stage_direct_posting()`, add the `ARTransaction` to the SAME
session, and commit both together via `finalize_and_publish()` — genuine
single-transaction atomicity between the GL and the AR subsidiary ledger
(tasks.md T141/T142: "all within one transaction"). If the default AR/
Revenue control accounts are not configured for a company, the handler
raises — the exception is caught and logged by Sales's own
`InProcessEventBus.publish()` (it never propagates to the publisher), so
an unconfigured company's Sales flow is unaffected; only the AR/GL posting
silently fails until an admin configures the accounts.

Handlers #3/#4 remain unsubscribed stubs — Purchase (Epic 6) never built a
Bill/AP concept (spec 006 §60.2 defers Invoice Processing/Three-Way
Matching/Accounts Payable to Epic 8), so there is no `purchase.bill.posted`
producer to subscribe to, unlike #1/#2's real Sales events. Phase 7's
`AccountsPayableService.record_supplier_bill()`/`record_supplier_credit_
note()` provide the identical atomic-posting capability these handlers
would have used, just invoked directly by an API endpoint (manual bill
entry) instead of by an event callback.

Cross-module subscription note: Phase 3's `period_lock_handler.py`
explicitly declined to subscribe Accounting to Sales/Purchase/Inventory's
buses because none of those modules had any posting concept to protect.
Here the situation is the opposite: Accounting's own `PostingEngine` IS
the intended consumer of these events (research.md Decision 2 — "If the
Sales module raises an invoice, it calls the PostingEngine"), so wiring
the subscription is the designed integration point for Phase 4, not a
speculative addition.

Spec ref: specs/008-accounting-finance/tasks.md T099, T141, T142, T163, T164
"""

from __future__ import annotations

import logging
from datetime import date as _date
from decimal import Decimal
from typing import Any
from uuid import UUID

from core.database.session import SessionLocal
from modules.accounting.dependencies import build_ar_service

logger = logging.getLogger(__name__)


def handle_sales_invoice_posted(event: Any) -> None:
    """``HandleSalesInvoicePosted`` — live handler for ``sales.invoice.issued``.

    Payload fields (``modules.sales.events.invoice_events.InvoiceIssued``):
    ``invoice_id, invoice_number, customer_id, due_date, total_amount,
    currency_code, issued_by``. ``customer_id``/``issued_by`` are plain
    strings in the Sales event (not UUID-typed) — best-effort UUID parsing;
    if ``customer_id`` cannot be parsed, the event is logged and dropped
    (no ARTransaction can be recorded without a real customer reference).
    """
    try:
        customer_id = UUID(str(event.customer_id))
    except (ValueError, AttributeError, TypeError):
        logger.error(
            "handle_sales_invoice_posted: unparseable customer_id, dropping event: %r",
            event,
        )
        return

    actor_id: UUID | None
    try:
        actor_id = UUID(str(event.issued_by))
    except (ValueError, AttributeError, TypeError):
        actor_id = None

    due_date = None
    try:
        due_date = _date.fromisoformat(str(event.due_date))
    except (ValueError, AttributeError, TypeError):
        pass

    db = SessionLocal()
    try:
        ar_service = build_ar_service(db)
        ar_service.record_sales_invoice(
            company_id=event.company_id,
            customer_id=customer_id,
            invoice_id=event.invoice_id,
            invoice_number=event.invoice_number,
            total_amount=Decimal(str(event.total_amount)),
            currency_code=event.currency_code,
            transaction_date=_date.today(),
            due_date=due_date,
            actor_id=actor_id,
        )
    finally:
        db.close()


def handle_sales_credit_note_posted(event: Any) -> None:
    """``HandleSalesCreditNotePosted`` — live handler for ``sales.invoice.credit_note_issued``.

    Payload fields (``InvoiceCreditNoteIssued``): ``invoice_id,
    invoice_number, customer_id, credit_note_amount, issued_by``.
    """
    try:
        customer_id = UUID(str(event.customer_id))
    except (ValueError, AttributeError, TypeError):
        logger.error(
            "handle_sales_credit_note_posted: unparseable customer_id, dropping event: %r",
            event,
        )
        return

    actor_id: UUID | None
    try:
        actor_id = UUID(str(event.issued_by))
    except (ValueError, AttributeError, TypeError):
        actor_id = None

    db = SessionLocal()
    try:
        ar_service = build_ar_service(db)
        ar_service.record_sales_credit_note(
            company_id=event.company_id,
            customer_id=customer_id,
            invoice_id=event.invoice_id,
            invoice_number=event.invoice_number,
            credit_amount=Decimal(str(event.credit_note_amount)),
            transaction_date=_date.today(),
            actor_id=actor_id,
        )
    finally:
        db.close()


def handle_purchase_bill_posted(event: Any) -> None:
    """``HandlePurchaseBillPosted`` — STUB. No real event exists.

    Purchase (Epic 6) has no Bill/Invoice/AP entity at all (spec 006 §60.2
    defers Invoice Processing/AP to Epic 8's own future scope). This
    handler is not subscribed to anything — there is nothing to subscribe
    to. AP bill capture (Phase 7, T163) is instead implemented as
    ``AccountsPayableService.record_supplier_bill()``, called directly by
    ``POST /accounting/ap/bills`` (manual entry) rather than by an event
    callback. This stub exists so the handler name/signature from
    tasks.md T099 stays real and importable, and as the concrete place a
    future real Purchase Bill event (if Epic 6 ever adds one) would wire in.
    """
    logger.warning(
        "handle_purchase_bill_posted: stub — Purchase has no Bill/AP entity yet. "
        "AP bill capture is implemented directly via AccountsPayableService."
        "record_supplier_bill() / POST /accounting/ap/bills (Phase 7). "
        "Event ignored: %r",
        event,
    )


def handle_purchase_credit_note_posted(event: Any) -> None:
    """``HandlePurchaseCreditNotePosted`` — STUB. Same reason as
    ``handle_purchase_bill_posted``; mirrors it with ``AccountsPayableService.
    record_supplier_credit_note()`` / ``POST /accounting/ap/credit-notes``.
    """
    logger.warning(
        "handle_purchase_credit_note_posted: stub — no Purchase AP entity yet. "
        "AP credit-note capture is implemented directly via "
        "AccountsPayableService.record_supplier_credit_note() / "
        "POST /accounting/ap/credit-notes (Phase 7). Event ignored: %r",
        event,
    )


def handle_inventory_adjustment_posted(event: Any) -> None:
    """``HandleInventoryAdjustmentPosted`` — STUB.

    Real events exist (`StockAdjusted`/`InventoryAdjustmentApproved`), but
    ADR-0004 explicitly leaves "Inventory GL-value sufficiency" as an open
    Phase 4+ item — there is no default inventory-valuation/adjustment
    control account resolution defined yet, so posting here would risk an
    incorrect GL entry. Deferred rather than guessed.
    """
    logger.warning(
        "handle_inventory_adjustment_posted: stub — inventory GL-account "
        "resolution is an open item per ADR-0004. Event ignored: %r",
        event,
    )


def handle_inventory_cost_updated(event: Any) -> None:
    """``HandleInventoryCostUpdated`` — STUB. No real event exists (Inventory has no cost/valuation event)."""
    logger.warning(
        "handle_inventory_cost_updated: stub — Inventory has no cost/valuation "
        "event. Event ignored: %r",
        event,
    )


def handle_sales_payment_received(event: Any) -> None:
    """``HandleSalesPaymentReceived`` — STUB, confirmed still correct as of
    Phase 10 (Payment Processing).

    Per quickstart.md's Phase 0 verification, this was never a real inbound
    event — Sales (Epic 7) publishes no ``sales.payment.received`` event to
    subscribe to. It is one of Accounting's OWN outbound-shaped capabilities.
    Now that Phase 10 exists, the real capability is
    ``PaymentService.create_customer_payment()``, exposed via
    ``POST /accounting/payments/customer`` — mirrors exactly how
    ``handle_purchase_bill_posted``/``handle_purchase_credit_note_posted``
    (#3/#4 above) were resolved in Phase 7: manual/API entry instead of an
    event callback, because there is nothing to subscribe to.
    """
    logger.warning(
        "handle_sales_payment_received: stub — no real sales.payment.received "
        "event exists to subscribe to; use PaymentService.create_customer_payment() "
        "/ POST /accounting/payments/customer (Phase 10). Event ignored: %r",
        event,
    )


def handle_supplier_payment_made(event: Any) -> None:
    """``HandleSupplierPaymentMade`` — STUB, confirmed still correct as of
    Phase 10. Same reason as ``handle_sales_payment_received``; the real
    capability is ``PaymentService.create_supplier_payment()`` /
    ``POST /accounting/payments/supplier``.
    """
    logger.warning(
        "handle_supplier_payment_made: stub — no real purchase.payment.made "
        "event exists to subscribe to; use PaymentService.create_supplier_payment() "
        "/ POST /accounting/payments/supplier (Phase 10). Event ignored: %r",
        event,
    )


def register_integration_handlers() -> None:
    """Subscribe the 2 live handlers to Sales's real event bus.

    The other 6 handlers are intentionally NOT subscribed anywhere — see
    the module docstring table for why each one has no real event to
    subscribe to yet. Calling this function is idempotent-in-intent but
    ``InProcessEventBus.subscribe`` itself simply appends — callers
    (module startup, test fixtures) should call this exactly once per
    Sales bus instance, matching ``period_lock_handler.
    register_period_lock_handlers``'s documented caveat.
    """
    from modules.sales.events import get_event_bus as get_sales_event_bus

    sales_bus = get_sales_event_bus()
    sales_bus.subscribe("sales.invoice.issued", handle_sales_invoice_posted)
    sales_bus.subscribe(
        "sales.invoice.credit_note_issued", handle_sales_credit_note_posted
    )


__all__ = [
    "handle_inventory_adjustment_posted",
    "handle_inventory_cost_updated",
    "handle_purchase_bill_posted",
    "handle_purchase_credit_note_posted",
    "handle_sales_credit_note_posted",
    "handle_sales_invoice_posted",
    "handle_sales_payment_received",
    "handle_supplier_payment_made",
    "register_integration_handlers",
]
