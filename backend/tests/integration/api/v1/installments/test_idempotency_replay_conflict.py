"""[Epic 10, Phase 7, closure-gap-1] Idempotency replay/conflict tests
against the REAL command methods — ``InstallmentCollectionService.
record_collection()``/``reverse_collection()`` — not the primitive in
isolation.

For each command, proves both normal outcomes of plan.md §20.3's
concurrency contract:

- same key + same fingerprint -> replay of the original stored result,
  with ZERO additional Payment/ARTransaction/JournalEntry/
  InstallmentAllocationReference row created;
- same key + different fingerprint -> ``InstallmentIdempotencyConflictError``
  (409), with ZERO additional business or Accounting effect persisted.

Real Postgres (schedule tables require it).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from modules.accounting.models.ar import ARTransaction
from modules.accounting.models.gl import JournalEntry
from modules.accounting.models.payments import Payment
from modules.installments.exceptions import InstallmentIdempotencyConflictError
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
)


def _counts(db_session, company_id, contract_id) -> dict[str, int]:
    return {
        "payments": len(
            db_session.execute(select(Payment).where(Payment.company_id == company_id))
            .scalars()
            .all()
        ),
        "ar_transactions": len(
            db_session.execute(
                select(ARTransaction).where(ARTransaction.company_id == company_id)
            )
            .scalars()
            .all()
        ),
        "journal_entries": len(
            db_session.execute(
                select(JournalEntry).where(JournalEntry.company_id == company_id)
            )
            .scalars()
            .all()
        ),
        "allocation_refs": len(
            InstallmentAllocationReferenceRepository(db_session).list_for_contract(
                company_id, contract_id
            )
        ),
    }


class TestRecordCollectionIdempotency:
    def test_same_key_same_fingerprint_replays_with_zero_additional_effect(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        service = build_collection_service(db_session)
        key = str(uuid.uuid4())

        first = service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=key,
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        counts_after_first = _counts(db_session, ctx["company_id"], ctx["contract"].id)

        # Same key, identical amount/payment_method -> identical
        # fingerprint -> replay, not reprocessing.
        second = service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=key,
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        counts_after_second = _counts(db_session, ctx["company_id"], ctx["contract"].id)

        assert second == first
        assert counts_after_second == counts_after_first

    def test_same_key_different_fingerprint_returns_409_with_zero_additional_effect(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        service = build_collection_service(db_session)
        key = str(uuid.uuid4())

        service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=key,
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        counts_after_first = _counts(db_session, ctx["company_id"], ctx["contract"].id)

        # Same key, DIFFERENT amount -> different fingerprint -> conflict,
        # never a second collection.
        with pytest.raises(InstallmentIdempotencyConflictError):
            service.record_collection(
                ctx["company_id"],
                ctx["contract"].id,
                amount=Decimal("200.00"),
                payment_method="BANK_TRANSFER",
                idempotency_key=key,
                actor_id=None,
                bank_account_id=ctx["bank_account"].id,
            )
        db_session.rollback()

        counts_after_conflict = _counts(
            db_session, ctx["company_id"], ctx["contract"].id
        )
        assert counts_after_conflict == counts_after_first


class TestReverseCollectionIdempotency:
    def test_same_key_same_fingerprint_replays_with_zero_additional_reversal(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        service = build_collection_service(db_session)

        collect_result = service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        collection_id = uuid.UUID(collect_result["accounting_payment_id"])

        reverse_key = str(uuid.uuid4())
        first_reversal = service.reverse_collection(
            ctx["company_id"],
            collection_id,
            reason="Customer requested reversal",
            idempotency_key=reverse_key,
            actor_id=None,
        )
        refs_after_first = InstallmentAllocationReferenceRepository(
            db_session
        ).list_for_contract(ctx["company_id"], ctx["contract"].id)

        # Same key, SAME collection_id -> identical fingerprint -> replay,
        # not a second reversal-reference row.
        second_reversal = service.reverse_collection(
            ctx["company_id"],
            collection_id,
            reason="Customer requested reversal",
            idempotency_key=reverse_key,
            actor_id=None,
        )
        refs_after_second = InstallmentAllocationReferenceRepository(
            db_session
        ).list_for_contract(ctx["company_id"], ctx["contract"].id)

        assert second_reversal == first_reversal
        assert len(refs_after_second) == len(refs_after_first)

    def test_same_key_different_fingerprint_returns_409_with_zero_additional_reversal(
        self, db_session
    ) -> None:
        # 3 lines so two 100.00 collections leave the contract ACTIVE
        # (100 still outstanding) — a completed contract would itself
        # (correctly) block reversal, which would mask the fingerprint
        # check this test targets.
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=3, installment_amount=Decimal("100.00")
        )
        service = build_collection_service(db_session)

        first_collection = service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        second_collection = service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        first_collection_id = uuid.UUID(first_collection["accounting_payment_id"])
        second_collection_id = uuid.UUID(second_collection["accounting_payment_id"])

        reverse_key = str(uuid.uuid4())
        service.reverse_collection(
            ctx["company_id"],
            first_collection_id,
            reason="Reversal of first collection",
            idempotency_key=reverse_key,
            actor_id=None,
        )
        refs_after_first_reversal = InstallmentAllocationReferenceRepository(
            db_session
        ).list_for_contract(ctx["company_id"], ctx["contract"].id)

        # Same key, DIFFERENT collection_id (the fingerprint's only
        # input) -> different fingerprint -> conflict, never a second
        # reversal.
        with pytest.raises(InstallmentIdempotencyConflictError):
            service.reverse_collection(
                ctx["company_id"],
                second_collection_id,
                reason="Reversal of second collection",
                idempotency_key=reverse_key,
                actor_id=None,
            )
        db_session.rollback()

        refs_after_conflict = InstallmentAllocationReferenceRepository(
            db_session
        ).list_for_contract(ctx["company_id"], ctx["contract"].id)
        assert len(refs_after_conflict) == len(refs_after_first_reversal)
