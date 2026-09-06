"""[Epic 10, Phase 10, T187] Real-Postgres concurrency test — concurrent
approval/rejection on the same PENDING_APPROVAL contract. Deterministic
conflict via the optimistic ``version`` column, never a silent overwrite
(FR-INST-382) — ``approve()``/``reject()`` both use
``update_with_version_check()``'s single atomic
``UPDATE ... WHERE version = :expected ... RETURNING``, so Postgres's
own row-level write serialization resolves the race: whichever UPDATE
commits first wins; the second's WHERE clause no longer matches and
``InstallmentConcurrentModificationError`` is raised — no ``FOR UPDATE``
lock is needed or taken here (discrete-transition optimistic locking,
distinct from the money-mutating operations' ``FOR UPDATE`` strategy).
"""

from __future__ import annotations

import threading
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import sessionmaker

from modules.installments.exceptions import InstallmentConcurrentModificationError
from modules.installments.models.contract import InstallmentContract
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.services.audit_service import InstallmentAuditService
from modules.installments.services.contract_service import InstallmentContractService


def _build_service(session) -> InstallmentContractService:
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


class TestApproveRejectRace:
    def test_concurrent_approve_and_reject_yield_one_success_one_conflict(
        self, db_session, pg_engine
    ) -> None:
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
            terms_snapshot={"note": "approve/reject race fixture"},
        )
        db_session.add(contract)
        db_session.commit()
        contract_id = contract.id

        session_factory = sessionmaker(bind=pg_engine)
        session_a = session_factory()
        session_b = session_factory()

        results: dict[str, object] = {}

        def _approve(session) -> None:
            try:
                svc = _build_service(session)
                updated = svc.approve(company_id, contract_id, uuid.uuid4())
                results["approve"] = ("success", updated.status)
            except Exception as exc:  # noqa: BLE001 — capturing for assertion
                session.rollback()
                results["approve"] = ("error", exc)

        def _reject(session) -> None:
            try:
                svc = _build_service(session)
                updated = svc.reject(
                    company_id, contract_id, "Missing documents", uuid.uuid4()
                )
                results["reject"] = ("success", updated.status)
            except Exception as exc:  # noqa: BLE001 — capturing for assertion
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
        assert (
            outcomes.count("success") == 1
        ), f"expected exactly one success, got: {results}"
        assert outcomes.count("error") == 1

        loser_key = "approve" if results["approve"][0] == "error" else "reject"
        loser_exc = results[loser_key][1]
        assert isinstance(loser_exc, InstallmentConcurrentModificationError)

        verify_session = session_factory()
        try:
            refreshed = (
                verify_session.query(InstallmentContract)
                .filter_by(id=contract_id)
                .one()
            )
            # Deterministic, non-torn final state: exactly the winner's
            # own outcome, never a silently-overwritten mix of both.
            winner_key = "reject" if loser_key == "approve" else "approve"
            expected_status = "APPROVED" if winner_key == "approve" else "DRAFT"
            assert refreshed.status == expected_status
            assert refreshed.status == results[winner_key][1]
            assert refreshed.version == 2
        finally:
            verify_session.close()
