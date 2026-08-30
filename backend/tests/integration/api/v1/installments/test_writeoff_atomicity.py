"""[Epic 10, Phase 10, T184 — Correction 4, Layer B: full cross-module
write-off atomicity] Real-Postgres forced-failure test.

Fails *after* ``stage_write_off()`` flushes the GL entry/``ARTransaction``
status-and-outstanding change/``CustomerLedger`` recompute and *after*
the contract's ``WRITTEN_OFF`` status/``InstallmentAuditLog``/outbox/
idempotency-completion are staged, but *before* ``finalize_write_off()``
— asserts **all** of ``JournalEntry``, ``ARTransaction`` status/
outstanding, the ``CustomerLedger`` recompute, contract ``WRITTEN_OFF``
status, ``InstallmentAuditLog``, the outbox event, and the idempotency-
key row are simultaneously absent post-rollback (plan.md §12.3.3;
mirrors T152's identical proof for late charges).

Replicates ``InstallmentContractService.writeoff()``'s exact staged
sequence directly so the injected failure point is precise and
verifiable via a second, independent connection.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from core.events.outbox import EventOutboxRepository, OutboxRecord
from core.utils.datetime import utcnow
from modules.accounting.dependencies import build_ar_service
from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.accounting.models.gl import JournalEntry
from modules.installments.models.audit import InstallmentAuditLog
from modules.installments.models.contract import InstallmentContract
from modules.installments.models.idempotency import InstallmentIdempotencyKey
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.configuration import (
    InstallmentConfigurationRepository,
)
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.services.accounting_gateway import (
    AccountingIntegrationGateway,
)
from modules.installments.services.audit_service import InstallmentAuditService
from modules.installments.services.configuration_service import (
    InstallmentConfigurationService,
)
from modules.installments.services.contract_service import InstallmentContractService
from modules.installments.services.idempotency_service import (
    InstallmentIdempotencyService,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
)


def _default_the_contract(db_session, contract_id: uuid.UUID) -> None:
    contract = db_session.query(InstallmentContract).filter_by(id=contract_id).one()
    contract.status = "DEFAULTED"
    contract.defaulted_at = contract.contract_date
    db_session.add(contract)
    db_session.commit()


class TestWriteoffAtomicityLayerB:
    def test_forced_failure_before_finalize_write_off_leaves_nothing_committed(
        self, db_session, pg_engine
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        _default_the_contract(db_session, ctx["contract"].id)

        ar_service = build_ar_service(db_session, with_sales_sync=False)
        gateway = AccountingIntegrationGateway(
            ar_service=ar_service, payment_service=None, allocation_engine=None
        )
        contract_repo = InstallmentContractRepository(db_session)
        audit_service = InstallmentAuditService(
            db=db_session, audit_repo=InstallmentAuditLogRepository(db_session)
        )
        outbox_repo = EventOutboxRepository(db_session)
        idempotency_service = InstallmentIdempotencyService(db_session)

        ledger_before = db_session.execute(
            select(CustomerLedger).where(
                CustomerLedger.company_id == ctx["company_id"],
                CustomerLedger.customer_id == ctx["customer_id"],
            )
        ).scalar_one()
        outstanding_before = ledger_before.total_outstanding_base

        contract = contract_repo.get_by_id_locked(ctx["contract"].id, ctx["company_id"])
        ar_transaction_id = gateway.get_invoice_ar_transaction_id(
            ctx["company_id"], contract.sales_invoice_id
        )

        idempotency_key = str(uuid.uuid4())
        reservation = idempotency_service.reserve(
            ctx["company_id"],
            "contract.writeoff",
            idempotency_key,
            "fingerprint",
            contract_id=contract.id,
        )
        assert reservation.outcome == "RESERVED"

        # Replicates writeoff()'s exact sequence up to (but not
        # including) finalize_write_off().
        staged = ar_service.stage_write_off(
            company_id=ctx["company_id"],
            ar_transaction_id=ar_transaction_id,
            reason="T184 forced-failure test",
            actor_id=None,
        )

        contract.status = "WRITTEN_OFF"
        contract.written_off_at = utcnow()
        db_session.add(contract)
        db_session.flush()

        audit_row = audit_service.record(
            ctx["company_id"],
            "InstallmentContract",
            contract.id,
            action="WRITTEN_OFF",
            actor_id=None,
            after={"status": "WRITTEN_OFF"},
        )
        audit_row_id = audit_row.id

        outbox_repo.create(
            OutboxRecord(
                event_type="installment.contract.written_off",
                aggregate_id=str(contract.id),
                aggregate_type="InstallmentContract",
                payload={"contract_id": str(contract.id)},
            )
        )
        idempotency_service.complete(
            reservation.reservation_id, {"contract_id": str(contract.id)}
        )

        journal_entry_id = staged.journal_entry.id
        ar_transaction_pk = staged.ar_transaction.id
        reservation_id = reservation.reservation_id

        class _InjectedFailure(Exception):
            pass

        try:
            raise _InjectedFailure("simulated failure before finalize_write_off()")
        except _InjectedFailure:
            db_session.rollback()

        verify_session_factory = sessionmaker(bind=pg_engine)
        verify_session = verify_session_factory()
        try:
            assert verify_session.get(JournalEntry, journal_entry_id) is None

            # The ARTransaction itself pre-existed (the invoice) — its
            # WRITTEN_OFF status/zeroed outstanding must NOT have stuck.
            refreshed_ar = verify_session.get(ARTransaction, ar_transaction_pk)
            assert refreshed_ar is not None
            assert refreshed_ar.status != "WRITTEN_OFF"
            assert refreshed_ar.outstanding_amount > 0

            refreshed_contract = verify_session.get(InstallmentContract, contract.id)
            assert refreshed_contract.status == "DEFAULTED"
            assert refreshed_contract.written_off_at is None

            assert verify_session.get(InstallmentAuditLog, audit_row_id) is None

            refreshed_ledger = verify_session.execute(
                select(CustomerLedger).where(
                    CustomerLedger.company_id == ctx["company_id"],
                    CustomerLedger.customer_id == ctx["customer_id"],
                )
            ).scalar_one()
            assert refreshed_ledger.total_outstanding_base == outstanding_before

            outbox_rows = (
                verify_session.query(OutboxRecord)
                .filter_by(aggregate_id=str(contract.id))
                .all()
            )
            assert outbox_rows == []

            assert verify_session.get(InstallmentIdempotencyKey, reservation_id) is None
        finally:
            verify_session.close()

    def test_normal_path_commits_gl_ar_ledger_contract_audit_outbox_together(
        self, db_session, pg_engine
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        _default_the_contract(db_session, ctx["contract"].id)

        ar_service = build_ar_service(db_session, with_sales_sync=False)
        gateway = AccountingIntegrationGateway(
            ar_service=ar_service, payment_service=None, allocation_engine=None
        )
        svc = InstallmentContractService(
            repo=InstallmentContractRepository(db_session),
            sequence_repo=None,  # type: ignore[arg-type]
            eligibility_service=None,  # type: ignore[arg-type]
            accounting_gateway=gateway,
            configuration_service=InstallmentConfigurationService(
                repo=InstallmentConfigurationRepository(db_session)
            ),
            audit_service=InstallmentAuditService(
                db=db_session, audit_repo=InstallmentAuditLogRepository(db_session)
            ),
            schedule_repo=InstallmentScheduleRepository(db_session),
            idempotency_service=InstallmentIdempotencyService(db_session),
            outbox_repo=EventOutboxRepository(db_session),
            allocation_ref_repo=InstallmentAllocationReferenceRepository(db_session),
        )

        updated = svc.writeoff(
            ctx["company_id"],
            ctx["contract"].id,
            "Uncollectible",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )
        assert updated.status == "WRITTEN_OFF"
        assert updated.written_off_at is not None

        verify_session_factory = sessionmaker(bind=pg_engine)
        verify_session = verify_session_factory()
        try:
            ar_transaction_id = gateway.get_invoice_ar_transaction_id(
                ctx["company_id"], ctx["contract"].sales_invoice_id
            )
            refreshed_ar = verify_session.get(ARTransaction, ar_transaction_id)
            assert refreshed_ar.status == "WRITTEN_OFF"
            assert refreshed_ar.outstanding_amount == Decimal("0")

            audit_rows = (
                verify_session.query(InstallmentAuditLog)
                .filter_by(entity_id=ctx["contract"].id, action="WRITTEN_OFF")
                .all()
            )
            assert len(audit_rows) == 1
        finally:
            verify_session.close()
