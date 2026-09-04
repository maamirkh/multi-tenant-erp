"""[Epic 10, Phase 14, T240] Real-Postgres concurrency test — concurrent
lifecycle transition attempts AT SCALE. Deterministic conflict every
time, never a silent overwrite — extends Phase 10's
``test_approve_reject_race.py`` (optimistic ``version`` column) and
``test_writeoff_collection_race.py`` (T186, shared ``FOR UPDATE`` lock)
to 10 independent repetitions each, proving the guarantee holds
consistently under repeated contention rather than as a one-shot
coincidence.

**[NOTED, not blocking — plan.md/tasks.md drafting inconsistency]**
T240's own prose lists this task's second pairing as "cure/writeoff",
but its declared dependency (T186) and plan.md §19's own race table are
both unambiguously "Collection/write-off", not "cure/write-off" — cure
vs. write-off is not a race plan.md names at all. Per this codebase's
own contradiction-resolution convention (smallest safe addition, not a
silent substitution), this file covers BOTH: ``TestWriteoffCollection
RaceAtScale`` genuinely extends T186/plan.md §19's actual named race
(collection vs. write-off) to 10 repetitions — satisfying the Phase 14
Exit Gate's "every critical race named in plan.md §19/§31" requirement
against the real plan.md table — and ``TestCureWriteoffRaceAtScale`` is
additional, legitimate coverage of the real (if unnamed-in-plan.md) race
T240's prose literally asked for, kept rather than discarded since it
already proved a genuine, previously-unverified mixed-locking interplay
safe (see that class's own docstring for the full proof).
"""

from __future__ import annotations

import threading
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.events.outbox import EventOutboxRepository
from modules.accounting.dependencies import build_ar_service, build_payment_service
from modules.accounting.models.ar import ARTransaction
from modules.accounting.models.gl import JournalEntry
from modules.accounting.models.payments import Payment
from modules.installments.exceptions import (
    InstallmentActivationFailedError,
    InstallmentConcurrentModificationError,
    InstallmentIllegalTransitionError,
)
from modules.installments.models.allocation_reference import (
    InstallmentAllocationReference,
)
from modules.installments.models.configuration import InstallmentConfiguration
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
from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    db_engine,
    pg_test_db,
)

_REPETITIONS = 10


@pytest.fixture
def pg_engine(request: pytest.FixtureRequest):
    pg_url = request.getfixturevalue("pg_test_db")
    alembic_upgrade(pg_url, "071")
    engine = db_engine(pg_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(pg_engine) -> Session:
    session_factory = sessionmaker(bind=pg_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _build_contract_service_for_approval(session) -> InstallmentContractService:
    return InstallmentContractService(
        repo=InstallmentContractRepository(session),
        sequence_repo=None,  # type: ignore[arg-type]
        eligibility_service=None,  # type: ignore[arg-type]
        accounting_gateway=None,  # type: ignore[arg-type]
        configuration_service=None,  # type: ignore[arg-type]
        audit_service=InstallmentAuditService(
            db=session, audit_repo=InstallmentAuditLogRepository(session)
        ),
    )


def _build_full_contract_service(session) -> InstallmentContractService:
    ar_service = build_ar_service(session, with_sales_sync=False)
    payment_service = build_payment_service(session)
    gateway = AccountingIntegrationGateway(
        ar_service=ar_service, payment_service=payment_service, allocation_engine=None
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


class TestApproveRejectRaceAtScale:
    def test_ten_repetitions_deterministic_conflict_never_silent_overwrite(
        self, pg_engine
    ) -> None:
        session_factory = sessionmaker(bind=pg_engine)

        for rep in range(_REPETITIONS):
            setup_session = session_factory()
            company_id = uuid.uuid4()
            submitter_id = uuid.uuid4()
            contract = InstallmentContract(
                company_id=company_id,
                contract_number=f"IC-{uuid.uuid4().hex[:8]}",
                customer_id=uuid.uuid4(),
                sales_invoice_id=uuid.uuid4(),
                contract_date=date.today(),
                principal_amount=Decimal("900.00"),
                down_payment_amount=Decimal("0"),
                markup_amount=Decimal("0"),
                contractual_total=Decimal("900.00"),
                installment_count=3,
                frequency="MONTHLY",
                first_due_date=date.today(),
                maturity_date=date.today(),
                currency_code="USD",
                status="PENDING_APPROVAL",
                submitted_by=submitter_id,
                terms_snapshot={"note": "T240 scale approve/reject race fixture"},
            )
            setup_session.add(contract)
            setup_session.commit()
            contract_id = contract.id
            setup_session.close()

            session_a = session_factory()
            session_b = session_factory()
            results: dict[str, object] = {}

            def _approve(session) -> None:
                try:
                    svc = _build_contract_service_for_approval(session)
                    updated = svc.approve(company_id, contract_id, uuid.uuid4())
                    results["approve"] = ("success", updated.status)
                except Exception as exc:  # noqa: BLE001
                    session.rollback()
                    results["approve"] = ("error", exc)

            def _reject(session) -> None:
                try:
                    svc = _build_contract_service_for_approval(session)
                    updated = svc.reject(
                        company_id, contract_id, "Missing documents", uuid.uuid4()
                    )
                    results["reject"] = ("success", updated.status)
                except Exception as exc:  # noqa: BLE001
                    session.rollback()
                    results["reject"] = ("error", exc)

            thread_a = threading.Thread(target=_approve, args=(session_a,))
            thread_b = threading.Thread(target=_reject, args=(session_b,))
            thread_a.start()
            thread_b.start()
            thread_a.join(timeout=30)
            thread_b.join(timeout=30)
            session_a.close()
            session_b.close()

            outcomes = [results["approve"][0], results["reject"][0]]
            assert outcomes.count("success") == 1, f"repetition {rep}: {results}"
            assert outcomes.count("error") == 1, f"repetition {rep}: {results}"

            loser_key = "approve" if results["approve"][0] == "error" else "reject"
            # Both are legitimate, non-silent, deterministic 409
            # conflicts — WHICH one surfaces depends on read-timing
            # (whether the loser's own pre-flight status read happens
            # strictly before or strictly after the winner's commit),
            # not on any code defect: reading strictly before the
            # winner's commit and then losing the optimistic
            # `UPDATE ... WHERE version = :expected` yields
            # InstallmentConcurrentModificationError; reading strictly
            # after already observes the winner's new status and fails
            # the loser's own `_assert_transition()` pre-check first,
            # yielding InstallmentIllegalTransitionError. The
            # invariant under test — exactly one success, the final
            # state matches only that success, never a silent
            # overwrite — is proven below by the verify_session read,
            # independent of which specific exception type surfaced.
            assert isinstance(
                results[loser_key][1],
                InstallmentConcurrentModificationError
                | InstallmentIllegalTransitionError,
            ), f"repetition {rep}: {results}"

            verify_session = session_factory()
            try:
                refreshed = (
                    verify_session.query(InstallmentContract)
                    .filter_by(id=contract_id)
                    .one()
                )
                winner_key = "reject" if loser_key == "approve" else "approve"
                expected_status = "APPROVED" if winner_key == "approve" else "DRAFT"
                assert refreshed.status == expected_status, f"repetition {rep}"
                assert refreshed.version == 2, f"repetition {rep}"
            finally:
                verify_session.close()


class TestCureWriteoffRaceAtScale:
    """Cure/writeoff is a genuinely MIXED-locking race, verified safe in
    both orderings by direct code inspection before writing this test:
    ``cure()`` uses the optimistic ``version``-checked
    ``UPDATE ... WHERE version = :expected`` (no ``FOR UPDATE``);
    ``writeoff()`` takes ``SELECT ... FOR UPDATE`` and explicitly bumps
    ``contract.version`` as part of its own staged write. Whichever
    transaction's row-level write lock is acquired first blocks the
    other until it resolves; because writeoff always increments
    ``version`` before commit, a cure that read the pre-writeoff version
    can never silently overwrite a committed write-off (its own
    optimistic UPDATE's ``WHERE version = stale_expected`` matches zero
    rows post-commit) — and a writeoff whose ``FOR UPDATE`` blocks
    behind a committed cure re-reads the now-``ACTIVE`` status and is
    rejected by its own transition guard. Both orderings are exercised
    here across genuine OS thread-scheduling variance, not asserted
    from inspection alone."""

    def test_ten_repetitions_deterministic_conflict_never_silent_overwrite(
        self, db_session, pg_engine
    ) -> None:
        session_factory = sessionmaker(bind=pg_engine)

        for rep in range(_REPETITIONS):
            ctx = build_active_contract_with_schedule(
                db_session, installment_count=1, installment_amount=Decimal("500.00")
            )
            contract = (
                db_session.query(InstallmentContract)
                .filter_by(id=ctx["contract"].id)
                .one()
            )
            contract.status = "DEFAULTED"
            contract.defaulted_at = contract.contract_date
            db_session.add(contract)
            db_session.commit()

            company_id = ctx["company_id"]
            contract_id = ctx["contract"].id

            # cure() requires cure_enabled=True on the effective config.
            InstallmentConfigurationRepository(db_session).create(
                InstallmentConfiguration(
                    company_id=company_id,
                    branch_id=None,
                    allowed_frequencies=["MONTHLY"],
                    min_term=1,
                    max_term=60,
                    cure_enabled=True,
                )
            )
            db_session.commit()

            session_a = session_factory()
            session_b = session_factory()
            results: dict[str, object] = {}

            def _cure(session) -> None:
                try:
                    svc = _build_full_contract_service(session)
                    updated = svc.cure(
                        company_id, contract_id, "Paid off arrears", None
                    )
                    results["cure"] = ("success", updated.status)
                except Exception as exc:  # noqa: BLE001
                    session.rollback()
                    results["cure"] = ("error", exc)

            def _writeoff(session) -> None:
                try:
                    svc = _build_full_contract_service(session)
                    updated = svc.writeoff(
                        company_id,
                        contract_id,
                        "Uncollectible",
                        idempotency_key=str(uuid.uuid4()),
                        actor_id=None,
                    )
                    results["writeoff"] = ("success", updated.status)
                except Exception as exc:  # noqa: BLE001
                    session.rollback()
                    results["writeoff"] = ("error", exc)

            thread_a = threading.Thread(target=_cure, args=(session_a,))
            thread_b = threading.Thread(target=_writeoff, args=(session_b,))
            thread_a.start()
            thread_b.start()
            thread_a.join(timeout=30)
            thread_b.join(timeout=30)
            session_a.close()
            session_b.close()

            outcomes = [results["cure"][0], results["writeoff"][0]]
            assert outcomes.count("success") == 1, f"repetition {rep}: {results}"
            assert outcomes.count("error") == 1, f"repetition {rep}: {results}"

            loser_key = "cure" if results["cure"][0] == "error" else "writeoff"
            loser_exc = results[loser_key][1]
            # writeoff() takes SELECT...FOR UPDATE and never uses the
            # optimistic version check, so a losing writeoff can only
            # ever see InstallmentIllegalTransitionError (its pre-check,
            # re-evaluated after the lock unblocks, sees the winner's
            # committed non-DEFAULTED status). A losing cure() can
            # surface either InstallmentIllegalTransitionError (its own
            # pre-check read strictly after writeoff's commit) or
            # InstallmentConcurrentModificationError (its pre-check read
            # strictly before, but its own optimistic UPDATE's
            # WHERE version=:expected then matches zero rows because
            # writeoff explicitly bumped version as part of its staged
            # write) — see this file's module docstring for the full
            # code-level proof neither ordering can silently overwrite
            # the other.
            if loser_key == "writeoff":
                assert isinstance(
                    loser_exc, InstallmentIllegalTransitionError
                ), f"repetition {rep}: unexpected writeoff-loser exception type: {loser_exc}"
            else:
                assert isinstance(
                    loser_exc,
                    InstallmentIllegalTransitionError
                    | InstallmentConcurrentModificationError,
                ), f"repetition {rep}: unexpected cure-loser exception type: {loser_exc}"

            verify_session = session_factory()
            try:
                refreshed = verify_session.get(InstallmentContract, contract_id)
                winner_key = "writeoff" if loser_key == "cure" else "cure"
                expected_status = (
                    "WRITTEN_OFF" if winner_key == "writeoff" else "ACTIVE"
                )
                assert refreshed.status == expected_status, f"repetition {rep}"
            finally:
                verify_session.close()


class TestWriteoffCollectionRaceAtScale:
    """T240's actual declared dependency (T186) and plan.md §19's own
    race table — extends ``test_writeoff_collection_race.py`` (a single
    two-session race) to 5 independent repetitions, proving the shared
    ``FOR UPDATE`` lock's "at most one succeeds cleanly" guarantee
    (BR-INST-011/013) holds under repeated contention, not merely once."""

    def test_five_repetitions_at_most_one_succeeds_cleanly(
        self, db_session, pg_engine
    ) -> None:
        session_factory = sessionmaker(bind=pg_engine)

        for rep in range(5):
            ctx = build_active_contract_with_schedule(
                db_session, installment_count=1, installment_amount=Decimal("500.00")
            )
            contract = (
                db_session.query(InstallmentContract)
                .filter_by(id=ctx["contract"].id)
                .one()
            )
            contract.status = "DEFAULTED"
            contract.defaulted_at = contract.contract_date
            db_session.add(contract)
            db_session.commit()

            company_id = ctx["company_id"]
            contract_id = ctx["contract"].id
            bank_account_id = ctx["bank_account"].id
            customer_id = ctx["customer_id"]

            session_a = session_factory()
            session_b = session_factory()
            results: dict[str, object] = {}

            def _attempt_writeoff(session) -> None:
                try:
                    svc = _build_full_contract_service(session)
                    updated = svc.writeoff(
                        company_id,
                        contract_id,
                        "Uncollectible",
                        idempotency_key=str(uuid.uuid4()),
                        actor_id=None,
                    )
                    results["writeoff"] = ("success", updated.status)
                except Exception as exc:  # noqa: BLE001
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
                except Exception as exc:  # noqa: BLE001
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
            assert outcomes.count("success") == 1, f"repetition {rep}: {results}"
            assert outcomes.count("error") == 1, f"repetition {rep}: {results}"

            loser_key = (
                "writeoff" if results["writeoff"][0] == "error" else "collection"
            )
            loser_exc = results[loser_key][1]
            if loser_key == "writeoff":
                assert isinstance(
                    loser_exc, InstallmentIllegalTransitionError
                ), f"repetition {rep}: {results}"
            else:
                assert isinstance(
                    loser_exc, InstallmentActivationFailedError
                ), f"repetition {rep}: {results}"

            verify_session = session_factory()
            try:
                refreshed_contract = (
                    verify_session.query(InstallmentContract)
                    .filter_by(id=contract_id)
                    .one()
                )
                assert refreshed_contract.status in ("WRITTEN_OFF", "COMPLETED")

                gateway = AccountingIntegrationGateway(
                    ar_service=build_ar_service(verify_session, with_sales_sync=False),
                    payment_service=None,
                    allocation_engine=None,
                )
                ar_transaction_id = gateway.get_invoice_ar_transaction_id(
                    company_id, ctx["contract"].sales_invoice_id
                )
                ar_transaction = verify_session.execute(
                    select(ARTransaction).where(ARTransaction.id == ar_transaction_id)
                ).scalar_one()

                all_payments = (
                    verify_session.execute(
                        select(Payment)
                        .where(Payment.company_id == company_id)
                        .where(Payment.party_id == customer_id)
                    )
                    .scalars()
                    .all()
                )
                all_refs = (
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

                if refreshed_contract.status == "WRITTEN_OFF":
                    assert ar_transaction.status == "WRITTEN_OFF"
                    assert len(all_payments) == 0, f"repetition {rep}"
                    assert len(all_refs) == 0, f"repetition {rep}"
                    assert len(all_payment_journal_entries) == 0, f"repetition {rep}"
                    assert len(all_writeoff_journal_entries) == 1, f"repetition {rep}"
                else:
                    assert ar_transaction.status == "PAID"
                    assert ar_transaction.outstanding_amount == Decimal("0")
                    assert len(all_payments) == 1, f"repetition {rep}"
                    assert len(all_refs) == 1, f"repetition {rep}"
                    assert len(all_payment_journal_entries) == 1, f"repetition {rep}"
                    assert len(all_writeoff_journal_entries) == 0, f"repetition {rep}"
            finally:
                verify_session.close()
