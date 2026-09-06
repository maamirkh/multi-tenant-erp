"""[Epic 10, Phase 10 closure evidence] Real-Postgres forced-failure
test: the exact internal commit boundary inside ``cancel()``'s
financial-activity path.

Trace (verified by direct code reading, not summary):

    _stage_cancellation_rows()                 [flush only]
            v
    reallocate_payment():
        loop over the down payment's ONE existing allocation line:
            target ARTransaction outstanding restored, credit
            transaction updated, line soft-deleted, flush
            db.commit()                        <- COMMIT #1: sweeps in
                                                   BOTH the Accounting
                                                   reversal AND every
                                                   Installments row
                                                   staged above
        payment.status = "POSTED"; db.commit() <- COMMIT #2 (status only)
        return allocation_engine.allocate(..., [])
            stage_allocation([]) -> payment.status = "ALLOCATED"
            finalize_allocation() -> db.commit() <- COMMIT #3 (status only)

This test forces a failure immediately AFTER COMMIT #1 but BEFORE
COMMIT #2 — the exact boundary the closure verification asked about —
using the least invasive technique consistent with this repo's own
atomicity-test patterns: patch the session's own ``commit`` bound
method to let the FIRST call through to the real ``commit()``
unmodified, then raise on the second.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import select

from core.events.outbox import OutboxRecord
from modules.accounting.models.ar import ARTransaction
from modules.accounting.models.payments import Payment
from modules.installments.models.audit import InstallmentAuditLog
from modules.installments.models.contract import InstallmentContract
from modules.installments.models.idempotency import InstallmentIdempotencyKey
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_contract_service,
)


class _InjectedFailureAfterFirstCommit(Exception):
    pass


class TestCancellationIntermediateCommitSafety:
    def test_failure_after_commit_1_leaves_a_consistent_committed_cancellation(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            down_payment_amount=Decimal("50.00"),
        )
        assert ctx["down_payment"] is not None
        svc = build_contract_service(db_session)
        idem_key = str(uuid.uuid4())

        real_commit = db_session.commit
        call_count = {"n": 0}

        def _succeed_once_then_fail(*args: object, **kwargs: object) -> None:
            call_count["n"] += 1
            if call_count["n"] == 1:
                real_commit(*args, **kwargs)
                return
            raise _InjectedFailureAfterFirstCommit(
                "simulated failure between commit #1 and commit #2"
            )

        with patch.object(db_session, "commit", side_effect=_succeed_once_then_fail):
            try:
                svc.cancel(
                    ctx["company_id"],
                    ctx["contract"].id,
                    "Customer request",
                    idempotency_key=idem_key,
                    actor_id=None,
                    payment_id=ctx["down_payment"].id,
                )
                raise AssertionError(
                    "expected _InjectedFailureAfterFirstCommit to propagate"
                )
            except _InjectedFailureAfterFirstCommit:
                pass
        # commit #1 already durably committed for real (the patch let it
        # through) — this rollback only discards whatever was flushed-
        # but-uncommitted AFTER it (the payment.status="POSTED" mutation
        # attempted inside commit #2's now-failed call).
        db_session.rollback()
        assert call_count["n"] == 2, "the failure must occur on the SECOND commit call"

        # --- The core financial + business outcome IS durably committed ---
        refreshed_contract = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        assert refreshed_contract.status == "CANCELLED"
        assert refreshed_contract.cancelled_at is not None

        invoice_ar = (
            db_session.execute(
                select(ARTransaction).where(ARTransaction.id == ctx["invoice"].id)
            )
            .scalars()
            .one()
        )
        # Invoice total = contractual_total (100.00) + down_payment
        # (50.00) = 150.00; the down payment reduced outstanding to
        # 100.00 at fixture setup. Restored exactly once, the reversal
        # brings outstanding back to the full 150.00.
        assert invoice_ar.outstanding_amount == Decimal("150.00")

        audit_rows = (
            db_session.execute(
                select(InstallmentAuditLog).where(
                    InstallmentAuditLog.entity_id == ctx["contract"].id,
                    InstallmentAuditLog.action == "CANCELLED",
                )
            )
            .scalars()
            .all()
        )
        assert len(audit_rows) == 1

        outbox_rows = (
            db_session.query(OutboxRecord)
            .filter_by(aggregate_id=str(ctx["contract"].id))
            .all()
        )
        assert len(outbox_rows) == 1

        reservations = (
            db_session.execute(
                select(InstallmentIdempotencyKey)
                .where(InstallmentIdempotencyKey.company_id == ctx["company_id"])
                .where(InstallmentIdempotencyKey.operation == "contract.cancel")
            )
            .scalars()
            .all()
        )
        assert len(reservations) == 1
        assert reservations[0].status == "COMPLETED"

        # --- The ONLY residual effect of the interrupted call: whatever
        # Payment.status was left at is a pre-existing, non-financial
        # Accounting bookkeeping quirk (commits #2/#3 only ever
        # round-trip ALLOCATED -> POSTED -> ALLOCATED for this exact
        # scenario) — empirically the SAME final value a fully
        # successful, uninterrupted call would also leave it at.
        payment_after_failure = (
            db_session.execute(
                select(Payment).where(Payment.id == ctx["down_payment"].id)
            )
            .scalars()
            .one()
        )
        assert payment_after_failure.status == "ALLOCATED"

        # --- Retry with the SAME key: REPLAY, not reprocessing ---
        retried = svc.cancel(
            ctx["company_id"],
            ctx["contract"].id,
            "Customer request",
            idempotency_key=idem_key,
            actor_id=None,
            payment_id=ctx["down_payment"].id,
        )
        assert retried.id == refreshed_contract.id
        assert retried.status == "CANCELLED"

        # No duplicate monetary effect from the retry.
        invoice_ar_after_retry = (
            db_session.execute(
                select(ARTransaction).where(ARTransaction.id == ctx["invoice"].id)
            )
            .scalars()
            .one()
        )
        assert invoice_ar_after_retry.outstanding_amount == Decimal("150.00")

        audit_rows_after_retry = (
            db_session.execute(
                select(InstallmentAuditLog).where(
                    InstallmentAuditLog.entity_id == ctx["contract"].id,
                    InstallmentAuditLog.action == "CANCELLED",
                )
            )
            .scalars()
            .all()
        )
        assert len(audit_rows_after_retry) == 1, "retry must create ZERO new audit rows"
