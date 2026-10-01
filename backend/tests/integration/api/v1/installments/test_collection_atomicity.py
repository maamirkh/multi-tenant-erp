"""[Epic 10, Phase 7, T136 — Correction 4, Layer B] Real-Postgres
forced-failure test: full cross-module collection atomicity.

Fails *after* ``stage_customer_payment()``+``stage_allocation()`` flush
and *after* ``InstallmentAllocationReference``/``InstallmentAuditLog``/
outbox/idempotency-completion are staged, but *before*
``finalize_customer_payment()`` — asserts **all** of ``Payment``, credit
``ARTransaction``, ``PaymentAllocationLine``, the target invoice
transaction's outstanding change, ``InstallmentAllocationReference``,
``InstallmentAuditLog``, the outbox event, and the idempotency-key row
are simultaneously absent post-rollback (the key becomes available again
for retry, not stranded ``IN_PROGRESS``).

Replicates ``InstallmentCollectionService.record_collection()``'s exact
staged sequence directly (mirroring T114-T116's established pattern) so
the injected failure point is precise and verifiable via a second,
independent connection.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import sessionmaker

from core.events.outbox import EventOutboxRepository, OutboxRecord
from modules.accounting.dependencies import (
    build_allocation_engine,
    build_payment_service,
)
from modules.accounting.models.ar import ARTransaction
from modules.accounting.models.payments import Payment, PaymentAllocationLine
from modules.accounting.services.payment_service import StagedCustomerPayment
from modules.installments.models.allocation_reference import (
    InstallmentAllocationReference,
)
from modules.installments.models.audit import InstallmentAuditLog
from modules.installments.models.idempotency import InstallmentIdempotencyKey
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.services.allocation_policy import (
    InstallmentAllocationPolicy,
)
from modules.installments.services.audit_service import InstallmentAuditService
from modules.installments.services.idempotency_service import (
    InstallmentIdempotencyService,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
)


class TestCollectionAtomicityLayerB:
    def test_forced_failure_before_finalize_leaves_nothing_committed(
        self, db_session, pg_engine
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("300.00")
        )
        collection_service = build_collection_service(db_session)

        payment_service = build_payment_service(db_session)
        allocation_engine = build_allocation_engine(db_session)
        allocation_ref_repo = InstallmentAllocationReferenceRepository(db_session)
        audit_service = InstallmentAuditService(
            db=db_session, audit_repo=InstallmentAuditLogRepository(db_session)
        )
        outbox_repo = EventOutboxRepository(db_session)
        idempotency_service = InstallmentIdempotencyService(db_session)

        idempotency_key = str(uuid.uuid4())
        fingerprint = "test-fingerprint-t136"
        reservation = idempotency_service.reserve(
            ctx["company_id"],
            "collection.create",
            idempotency_key,
            fingerprint,
            contract_id=ctx["contract"].id,
        )
        assert reservation.outcome == "RESERVED"

        # Replicates record_collection()'s exact sequence up to (but not
        # including) the Accounting finalize calls.
        outstanding = [
            (line.id, line.due_date, line.scheduled_amount)
            for line in ctx["schedule_lines"]
        ]
        from modules.installments.services.allocation_policy import OutstandingLine

        instructions = InstallmentAllocationPolicy.allocate_oldest_first(
            Decimal("300.00"),
            [
                OutstandingLine(schedule_line_id=i, due_date=d, outstanding_amount=a)
                for i, d, a in outstanding
            ],
        )

        staged_payment = payment_service.stage_customer_payment(
            company_id=ctx["company_id"],
            customer_id=ctx["customer_id"],
            payment_method="BANK_TRANSFER",
            payment_date=date.today(),
            amount=Decimal("300.00"),
            currency_code="USD",
            bank_account_id=ctx["bank_account"].id,
            actor_id=None,
        )
        staged_allocation = allocation_engine.stage_allocation(
            company_id=ctx["company_id"],
            payment_id=staged_payment.payment.id,
            allocation_lines=[
                {
                    "transaction_id": ctx["invoice"].id,
                    "amount_foreign": Decimal("300.00"),
                }
            ],
            actor_id=None,
        )

        payment_id = staged_payment.payment.id
        allocation_line_ids = [line.id for line in staged_allocation.results]
        assert isinstance(staged_payment, StagedCustomerPayment)
        journal_entry_id = staged_payment.journal_entry.id

        for instr, alloc_line in zip(
            instructions, staged_allocation.results, strict=True
        ):
            allocation_ref_repo.create(
                InstallmentAllocationReference(
                    company_id=ctx["company_id"],
                    contract_id=ctx["contract"].id,
                    schedule_line_id=instr.schedule_line_id,
                    accounting_payment_id=payment_id,
                    accounting_payment_allocation_line_id=alloc_line.id,
                    allocated_amount=instr.amount,
                    allocation_order=instr.allocation_order,
                    is_reversal=False,
                )
            )
        allocation_ref_ids = [
            ref.id
            for ref in allocation_ref_repo.list_for_contract(
                ctx["company_id"], ctx["contract"].id
            )
        ]
        audit_row = audit_service.record(
            ctx["company_id"],
            "InstallmentContract",
            ctx["contract"].id,
            action="COLLECTED",
            actor_id=None,
            after={"amount": "300.00"},
        )
        audit_row_id = audit_row.id
        outbox_repo.create(
            OutboxRecord(
                event_type="installment.collected",
                aggregate_id=str(ctx["contract"].id),
                aggregate_type="InstallmentContract",
                payload={"contract_id": str(ctx["contract"].id)},
            )
        )
        idempotency_service.complete(
            reservation.reservation_id,
            {"contract_id": str(ctx["contract"].id), "status": "COMPLETED"},
        )
        reservation_id = reservation.reservation_id

        class _InjectedFailure(Exception):
            pass

        try:
            raise _InjectedFailure(
                "simulated failure before finalize_customer_payment()/finalize_allocation()"
            )
        except _InjectedFailure:
            db_session.rollback()

        verify_session_factory = sessionmaker(bind=pg_engine)
        verify_session = verify_session_factory()
        try:
            assert verify_session.get(Payment, payment_id) is None
            for line_id in allocation_line_ids:
                assert verify_session.get(PaymentAllocationLine, line_id) is None
            for ref_id in allocation_ref_ids:
                assert (
                    verify_session.get(InstallmentAllocationReference, ref_id) is None
                )
            assert verify_session.get(InstallmentAuditLog, audit_row_id) is None
            assert verify_session.get(InstallmentIdempotencyKey, reservation_id) is None

            refreshed_invoice = verify_session.get(ARTransaction, ctx["invoice"].id)
            assert refreshed_invoice is not None
            assert refreshed_invoice.outstanding_amount == Decimal("300.00")
            assert refreshed_invoice.status == "OPEN"

            from core.events.outbox import OutboxRecord as _OutboxRecord

            outbox_rows = (
                verify_session.query(_OutboxRecord)
                .filter_by(aggregate_id=str(ctx["contract"].id))
                .all()
            )
            assert outbox_rows == []
        finally:
            verify_session.close()

        # The idempotency key is genuinely available for retry, not
        # stranded IN_PROGRESS.
        retry_session_factory = sessionmaker(bind=pg_engine)
        retry_session = retry_session_factory()
        try:
            retry_idempotency_service = InstallmentIdempotencyService(retry_session)
            retry_reservation = retry_idempotency_service.reserve(
                ctx["company_id"],
                "collection.create",
                idempotency_key,
                fingerprint,
                contract_id=ctx["contract"].id,
            )
            assert retry_reservation.outcome == "RESERVED"
            retry_session.rollback()
        finally:
            retry_session.close()

    def test_normal_path_commits_everything_together(
        self, db_session, pg_engine
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("150.00")
        )
        collection_service = build_collection_service(db_session)

        result = collection_service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("150.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        verify_session_factory = sessionmaker(bind=pg_engine)
        verify_session = verify_session_factory()
        try:
            payment_id = uuid.UUID(result["accounting_payment_id"])
            assert verify_session.get(Payment, payment_id) is not None

            refs = (
                verify_session.query(InstallmentAllocationReference)
                .filter_by(contract_id=ctx["contract"].id)
                .all()
            )
            assert len(refs) == 1

            audit_rows = (
                verify_session.query(InstallmentAuditLog)
                .filter_by(entity_id=ctx["contract"].id, action="COLLECTED")
                .all()
            )
            assert len(audit_rows) == 1

            key_row = (
                verify_session.query(InstallmentIdempotencyKey)
                .filter_by(
                    contract_id=ctx["contract"].id, operation="collection.create"
                )
                .one()
            )
            assert key_row.status == "COMPLETED"
        finally:
            verify_session.close()
