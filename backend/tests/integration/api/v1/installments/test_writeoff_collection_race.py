"""[Epic 10, Phase 10, T186] Real-Postgres concurrency test — concurrent
write-off vs. collection on the same DEFAULTED contract. The shared
``FOR UPDATE`` lock on ``InstallmentContract`` ensures at most one
succeeds cleanly (BR-INST-011/013), mirroring Phase 7's
``test_concurrent_collections.py``/Phase 9's
``test_settlement_concurrency.py`` two-thread/two-session pattern.
"""

from __future__ import annotations

import threading
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from core.events.outbox import EventOutboxRepository
from modules.accounting.dependencies import (
    build_allocation_engine,
    build_ar_service,
    build_payment_service,
)
from modules.accounting.models.ar import ARTransaction
from modules.accounting.models.gl import JournalEntry
from modules.accounting.models.payments import Payment
from modules.installments.exceptions import (
    InstallmentActivationFailedError,
    InstallmentIllegalTransitionError,
)
from modules.installments.models.allocation_reference import (
    InstallmentAllocationReference,
)
from modules.installments.models.contract import InstallmentContract
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
    build_collection_service,
)


def _build_contract_service(session) -> InstallmentContractService:
    ar_service = build_ar_service(session, with_sales_sync=False)
    payment_service = build_payment_service(session)
    gateway = AccountingIntegrationGateway(
        ar_service=ar_service,
        payment_service=payment_service,
        allocation_engine=build_allocation_engine(session),
    )
    return InstallmentContractService(
        repo=InstallmentContractRepository(session),
        sequence_repo=None,  # type: ignore[arg-type]
        eligibility_service=None,  # type: ignore[arg-type]
        accounting_gateway=gateway,
        configuration_service=InstallmentConfigurationService(
            repo=InstallmentConfigurationRepository(session)
        ),
        audit_service=InstallmentAuditService(
            db=session, audit_repo=InstallmentAuditLogRepository(session)
        ),
        schedule_repo=InstallmentScheduleRepository(session),
        idempotency_service=InstallmentIdempotencyService(session),
        outbox_repo=EventOutboxRepository(session),
        allocation_ref_repo=InstallmentAllocationReferenceRepository(session),
    )


class TestWriteoffVsCollectionRace:
    def test_at_most_one_of_writeoff_and_collection_succeeds(
        self, db_session, pg_engine
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        contract = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        contract.status = "DEFAULTED"
        contract.defaulted_at = contract.contract_date
        db_session.add(contract)
        db_session.commit()

        company_id = ctx["company_id"]
        contract_id = ctx["contract"].id
        bank_account_id = ctx["bank_account"].id
        customer_id = ctx["customer_id"]

        session_factory = sessionmaker(bind=pg_engine)
        session_a = session_factory()
        session_b = session_factory()

        results: dict[str, tuple[str, object]] = {}

        def _attempt_writeoff(session) -> None:
            try:
                svc = _build_contract_service(session)
                updated = svc.writeoff(
                    company_id,
                    contract_id,
                    "Uncollectible",
                    idempotency_key=str(uuid.uuid4()),
                    actor_id=None,
                )
                results["writeoff"] = ("success", updated.status)
            except Exception as exc:  # noqa: BLE001 — capturing for assertion
                session.rollback()
                results["writeoff"] = ("error", exc)

        def _attempt_collection(session) -> None:
            try:
                svc = build_collection_service(session)
                result = svc.record_collection(
                    company_id,
                    contract_id,
                    amount=Decimal("500.00"),
                    payment_method="BANK_TRANSFER",
                    idempotency_key=str(uuid.uuid4()),
                    actor_id=None,
                    bank_account_id=bank_account_id,
                )
                results["collection"] = ("success", result["contract_status"])
            except Exception as exc:  # noqa: BLE001 — capturing for assertion
                session.rollback()
                results["collection"] = ("error", exc)

        thread_a = threading.Thread(target=_attempt_writeoff, args=(session_a,))
        thread_b = threading.Thread(target=_attempt_collection, args=(session_b,))
        thread_a.start()
        thread_b.start()
        thread_a.join(timeout=30)
        thread_b.join(timeout=30)

        session_a.close()
        session_b.close()

        outcomes = [results["writeoff"][0], results["collection"][0]]
        # The FOR UPDATE lock serializes the two attempts — exactly one
        # must succeed (never both, never neither): whichever acquires
        # the lock first commits WRITTEN_OFF or COMPLETED; the second,
        # reading the now-committed non-DEFAULTED status, is rejected by
        # its own status guard.
        assert outcomes.count("success") == 1, (
            f"expected exactly one success, got: {results}"
        )
        assert outcomes.count("error") == 1

        loser_key = "writeoff" if results["writeoff"][0] == "error" else "collection"
        loser_exc = results[loser_key][1]
        if loser_key == "writeoff":
            assert isinstance(loser_exc, InstallmentIllegalTransitionError)
        else:
            assert isinstance(loser_exc, InstallmentActivationFailedError)

        verify_session = session_factory()
        try:
            refreshed_contract = (
                verify_session.query(InstallmentContract)
                .filter_by(id=contract_id)
                .one()
            )
            assert refreshed_contract.status in ("WRITTEN_OFF", "COMPLETED")

            # No matter which won, the invoice ARTransaction reflects
            # exactly one coherent authoritative outcome — never a torn
            # state (e.g. WRITTEN_OFF status with money still owed, or a
            # completed payoff whose ARTransaction is somehow also
            # flagged WRITTEN_OFF).
            gateway = AccountingIntegrationGateway(
                ar_service=build_ar_service(verify_session, with_sales_sync=False),
                payment_service=build_payment_service(verify_session),
                allocation_engine=build_allocation_engine(verify_session),
            )
            ar_transaction_id = gateway.get_invoice_ar_transaction_id(
                company_id, ctx["contract"].sales_invoice_id
            )
            ar_transaction = verify_session.execute(
                select(ARTransaction).where(ARTransaction.id == ar_transaction_id)
            ).scalar_one()
            if refreshed_contract.status == "WRITTEN_OFF":
                assert ar_transaction.status == "WRITTEN_OFF"
            else:
                assert ar_transaction.status == "PAID"
                assert ar_transaction.outstanding_amount == Decimal("0")

            # --- Fully unconditional, company-wide exactly-once proof ---
            # Mirrors Phase 9's test_settlement_concurrency.py standard:
            # none of these queries filter by a winning row's own id —
            # a second row left behind by a genuinely broken lock (rather
            # than a cleanly rolled-back loser) cannot hide from them.
            # Only company/customer_id plus the minimal authoritative
            # type/source discriminators are used.
            #
            # Collection creates exactly 1 new Payment + 1 PAYMENT-sourced
            # JournalEntry + 1 payment-sourced credit ARTransaction + 1
            # InstallmentAllocationReference. Write-off creates NEW rows
            # in none of those — it mutates the existing invoice
            # ARTransaction in place and posts exactly 1 MANUAL-sourced
            # JournalEntry (source_document_type="ARTransaction").
            all_payments_for_company = (
                verify_session.execute(
                    select(Payment)
                    .where(Payment.company_id == company_id)
                    .where(Payment.party_id == customer_id)
                )
                .scalars()
                .all()
            )
            all_refs_for_company = (
                verify_session.execute(
                    select(InstallmentAllocationReference).where(
                        InstallmentAllocationReference.company_id == company_id
                    )
                )
                .scalars()
                .all()
            )
            all_payment_journal_entries = (
                verify_session.execute(
                    select(JournalEntry)
                    .where(JournalEntry.company_id == company_id)
                    .where(JournalEntry.posting_source == "PAYMENT")
                )
                .scalars()
                .all()
            )
            all_writeoff_journal_entries = (
                verify_session.execute(
                    select(JournalEntry)
                    .where(JournalEntry.company_id == company_id)
                    .where(JournalEntry.posting_source == "MANUAL")
                    .where(JournalEntry.source_document_type == "ARTransaction")
                    .where(JournalEntry.source_document_id == ar_transaction_id)
                )
                .scalars()
                .all()
            )
            all_payment_credit_ar_transactions = (
                verify_session.execute(
                    select(ARTransaction)
                    .where(ARTransaction.company_id == company_id)
                    .where(ARTransaction.transaction_type == "PAYMENT")
                    .where(ARTransaction.source_document_type == "Payment")
                )
                .scalars()
                .all()
            )

            if refreshed_contract.status == "WRITTEN_OFF":
                assert len(all_payments_for_company) == 0, (
                    f"write-off must create ZERO Payment rows, found {len(all_payments_for_company)}"
                )
                assert len(all_refs_for_company) == 0, (
                    f"write-off must create ZERO InstallmentAllocationReference rows, found {len(all_refs_for_company)}"
                )
                assert len(all_payment_journal_entries) == 0, (
                    f"write-off must create ZERO PAYMENT-sourced JournalEntry rows, found {len(all_payment_journal_entries)}"
                )
                assert len(all_payment_credit_ar_transactions) == 0, (
                    f"write-off must create ZERO payment-sourced ARTransaction rows, found {len(all_payment_credit_ar_transactions)}"
                )
                assert len(all_writeoff_journal_entries) == 1, (
                    f"expected exactly 1 write-off JournalEntry, found {len(all_writeoff_journal_entries)}"
                )
            else:
                assert len(all_payments_for_company) == 1, (
                    f"expected exactly 1 Payment company-wide, found {len(all_payments_for_company)}"
                )
                assert len(all_refs_for_company) == 1, (
                    f"expected exactly 1 InstallmentAllocationReference, found {len(all_refs_for_company)}"
                )
                assert len(all_payment_journal_entries) == 1, (
                    f"expected exactly 1 payment-sourced JournalEntry, found {len(all_payment_journal_entries)}"
                )
                assert len(all_payment_credit_ar_transactions) == 1, (
                    f"expected exactly 1 payment-sourced ARTransaction, found {len(all_payment_credit_ar_transactions)}"
                )
                assert len(all_writeoff_journal_entries) == 0, (
                    f"a successful collection must leave ZERO write-off JournalEntry rows, found {len(all_writeoff_journal_entries)}"
                )
                assert (
                    all_payments_for_company[0].id
                    == all_refs_for_company[0].accounting_payment_id
                )
        finally:
            verify_session.close()
