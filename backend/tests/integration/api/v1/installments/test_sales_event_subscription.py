"""[Epic 10, Phase 15, T260] Cross-module integration test — Sales'
``InvoiceCreditNoteIssued``/``InvoiceCancelled`` event subscription
correctly flags an Installments contract ``requires_review=true``
without auto-cancelling (Scenario H).

Mirrors ``tests/integration/repositories/accounting/
test_integration_handlers.py``'s established pattern: construct the
real Sales event dataclass directly, monkeypatch the handler module's
``SessionLocal`` to the test's own real-Postgres session (so
assertions run inside the same transaction), call the handler function
directly (equivalent to what the real Sales event bus would do), then
assert on real DB state.

Real Postgres (schedule-backed contract fixture).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select

from modules.installments.handlers import sales_integration_handlers as handlers
from modules.installments.models.contract import InstallmentContract
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.sales.events.invoice_events import (
    InvoiceCancelled,
    InvoiceCreditNoteIssued,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
)


class TestInvoiceCreditNoteIssuedFlagsContractForReview:
    def test_credit_note_sets_requires_review_true_and_audits_without_cancelling(
        self, db_session, monkeypatch
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        # Capture primitives BEFORE calling the handler — the handler's
        # own `finally: db.close()` (correct for production: a fresh
        # SessionLocal() per event, closed after use) closes this SAME
        # session once monkeypatched, so any ORM object loaded before
        # the call (e.g. `ctx["contract"]`) becomes detached; only a
        # fresh post-call query against `db_session` (which itself
        # remains reusable after close(), it just starts a new
        # transaction) is safe — mirrors
        # test_integration_handlers.py's own established pattern.
        contract_id = ctx["contract"].id
        company_id = ctx["company_id"]
        assert ctx["contract"].requires_review is False
        monkeypatch.setattr(handlers, "SessionLocal", lambda: db_session)

        event = InvoiceCreditNoteIssued(
            aggregate_id=uuid.uuid4(),
            company_id=company_id,
            invoice_id=ctx["sales_invoice_id"],
            invoice_number="INV-E2E-0001",
            customer_id=str(ctx["customer_id"]),
            credit_note_amount="50.00",
            issued_by=str(uuid.uuid4()),
        )
        handlers.handle_invoice_credit_note_issued(event)

        refreshed = db_session.execute(
            select(InstallmentContract).where(InstallmentContract.id == contract_id)
        ).scalar_one()
        assert refreshed.requires_review is True
        # Never auto-cancelled or auto-adjusted — status is untouched.
        assert refreshed.status == "ACTIVE"

        audit_rows = InstallmentAuditLogRepository(db_session).list_for_entity(
            company_id, "InstallmentContract", contract_id
        )
        matching = [
            r for r in audit_rows if r.action == "ORIGINATING_INVOICE_CORRECTED"
        ]
        assert len(matching) == 1
        assert matching[0].after_state == {"requires_review": True}


class TestInvoiceCancelledFlagsContractForReview:
    def test_cancellation_sets_requires_review_true_without_cancelling_contract(
        self, db_session, monkeypatch
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("300.00")
        )
        contract_id = ctx["contract"].id
        monkeypatch.setattr(handlers, "SessionLocal", lambda: db_session)

        event = InvoiceCancelled(
            aggregate_id=uuid.uuid4(),
            company_id=ctx["company_id"],
            invoice_id=ctx["sales_invoice_id"],
            invoice_number="INV-E2E-0002",
            customer_id=str(ctx["customer_id"]),
            previous_status="ISSUED",
            cancelled_by=str(uuid.uuid4()),
        )
        handlers.handle_invoice_cancelled(event)

        refreshed = db_session.execute(
            select(InstallmentContract).where(InstallmentContract.id == contract_id)
        ).scalar_one()
        assert refreshed.requires_review is True
        assert refreshed.status == "ACTIVE"


class TestNoMatchingContractIsAGracefulNoOp:
    def test_unrelated_invoice_id_drops_the_event_without_error(
        self, db_session, monkeypatch
    ) -> None:
        monkeypatch.setattr(handlers, "SessionLocal", lambda: db_session)
        event = InvoiceCancelled(
            aggregate_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            invoice_id=uuid.uuid4(),
            invoice_number="INV-UNRELATED",
            customer_id=str(uuid.uuid4()),
            previous_status="ISSUED",
            cancelled_by=str(uuid.uuid4()),
        )
        # Must not raise — a graceful no-op.
        handlers.handle_invoice_cancelled(event)


class TestRegistration:
    def test_registers_exactly_two_subscriptions_on_sales_bus(self) -> None:
        from modules.sales.events import get_event_bus

        bus = get_event_bus()
        before_credit_note = len(
            bus._handlers.get("sales.invoice.credit_note_issued", [])
        )
        before_cancelled = len(bus._handlers.get("sales.invoice.cancelled", []))

        handlers.register_installments_sales_integration_handlers()

        after_credit_note = len(
            bus._handlers.get("sales.invoice.credit_note_issued", [])
        )
        after_cancelled = len(bus._handlers.get("sales.invoice.cancelled", []))
        assert after_credit_note == before_credit_note + 1
        assert after_cancelled == before_cancelled + 1
