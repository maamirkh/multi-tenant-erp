"""Sales integration event handlers — Epic 10, Phase 15 (T260 gap-closure,
plan.md §13, line 709).

Subscribes Installments to 2 events Sales ALREADY publishes — no Sales
file is modified to make this possible, mirroring
``modules/accounting/handlers/integration_handlers.py``'s and
``modules/crm/handlers/integration_handlers.py``'s own confirmed pattern
for cross-module event subscription (subscribing onto the PRODUCER
module's bus instance, never Installments' own).

Event-type strings verified directly against
``modules.sales.events.invoice_events`` before writing this handler
(mirroring CRM's own documented "verify, never trust prose" precedent):
``"sales.invoice.cancelled"`` (``InvoiceCancelled``) and
``"sales.invoice.credit_note_issued"`` (``InvoiceCreditNoteIssued``).

Both handlers set a **non-terminal flag** ``requires_review = true`` on
any non-terminal Installments contract referencing the corrected
invoice, plus an ``InstallmentAuditLog(action="ORIGINATING_INVOICE_
CORRECTED")`` entry — never an auto-cancel or auto-adjustment (Scenario
H, spec.md §16.1/FR-INST-241 explicitly requires an authorized human
action to resolve it). If no non-terminal contract references the
invoice, the event is logged and dropped (a graceful no-op, matching
Accounting's/CRM's own "silently no-ops until a precondition is met"
precedent for their own inbound handlers).

Spec ref: specs/010-installments/plan.md §13 (line 709);
specs/010-installments/spec.md Scenario H, FR-INST-241.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from core.database.session import SessionLocal
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.services.audit_service import InstallmentAuditService

logger = logging.getLogger(__name__)


def _flag_contract_for_review(
    *, company_id: Any, invoice_id: Any, invoice_number: str, reason: str
) -> None:
    try:
        company_uuid = UUID(str(company_id))
        invoice_uuid = UUID(str(invoice_id))
    except (ValueError, AttributeError, TypeError):
        logger.error(
            "installments sales_integration_handlers: unparseable company_id/"
            "invoice_id, dropping event (company_id=%r, invoice_id=%r)",
            company_id,
            invoice_id,
        )
        return

    db = SessionLocal()
    try:
        contract_repo = InstallmentContractRepository(db)
        contract = contract_repo.find_active_by_sales_invoice(
            company_uuid, invoice_uuid
        )
        if contract is None:
            logger.debug(
                "installments sales_integration_handlers: no non-terminal "
                "contract references invoice %s in company %s — dropping event",
                invoice_uuid,
                company_uuid,
            )
            return

        before_flag = contract.requires_review
        contract.requires_review = True
        db.add(contract)

        InstallmentAuditService(
            db=db, audit_repo=InstallmentAuditLogRepository(db)
        ).record(
            company_uuid,
            "InstallmentContract",
            contract.id,
            action="ORIGINATING_INVOICE_CORRECTED",
            actor_id=None,
            before={"requires_review": before_flag},
            after={"requires_review": True},
            reason=f"Sales invoice {invoice_number}: {reason}",
        )
        db.commit()
    finally:
        db.close()


def handle_invoice_credit_note_issued(event: Any) -> None:
    """Handler for Sales' ``sales.invoice.credit_note_issued`` event.

    Payload fields (``InvoiceCreditNoteIssued``): ``invoice_id,
    invoice_number, customer_id, credit_note_amount, issued_by``.
    """
    _flag_contract_for_review(
        company_id=event.company_id,
        invoice_id=event.invoice_id,
        invoice_number=event.invoice_number,
        reason=f"credit note issued (amount {event.credit_note_amount})",
    )


def handle_invoice_cancelled(event: Any) -> None:
    """Handler for Sales' ``sales.invoice.cancelled`` event.

    Payload fields (``InvoiceCancelled``): ``invoice_id, invoice_number,
    customer_id, previous_status, cancelled_by``.
    """
    _flag_contract_for_review(
        company_id=event.company_id,
        invoice_id=event.invoice_id,
        invoice_number=event.invoice_number,
        reason=f"invoice cancelled (was {event.previous_status})",
    )


def register_installments_sales_integration_handlers() -> None:
    """Subscribe the 2 handlers to Sales's real event bus.

    Calling this function is idempotent-in-intent but
    ``InProcessEventBus.subscribe`` itself simply appends — callers
    (module startup, test fixtures) should call this exactly once per
    Sales bus instance, matching Accounting's/CRM's own documented
    caveat for their own registration functions.
    """
    from modules.sales.events import get_event_bus as get_sales_event_bus

    sales_bus = get_sales_event_bus()
    sales_bus.subscribe(
        "sales.invoice.credit_note_issued", handle_invoice_credit_note_issued
    )
    sales_bus.subscribe("sales.invoice.cancelled", handle_invoice_cancelled)


__all__ = [
    "handle_invoice_cancelled",
    "handle_invoice_credit_note_issued",
    "register_installments_sales_integration_handlers",
]
