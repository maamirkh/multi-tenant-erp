"""[Epic 10, Phase 7, T132] Service test: collection reversal —
reversal-reference rows correctly reference the original, and the
original rows are never mutated (BR-INST-017). Real Postgres.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
)


class TestReverseCollection:
    def test_reversal_references_original_without_mutating_it(
        self, db_session: Session
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

        refs_before = InstallmentAllocationReferenceRepository(
            db_session
        ).list_for_contract(ctx["company_id"], ctx["contract"].id)
        assert len(refs_before) == 1
        original = refs_before[0]
        original_snapshot = (
            original.id,
            original.allocated_amount,
            original.is_reversal,
            original.reverses_allocation_reference_id,
        )

        reversal_result = service.reverse_collection(
            ctx["company_id"],
            collection_id,
            reason="Customer requested reversal",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )
        assert reversal_result["status"] == "REVERSED"

        refs_after = InstallmentAllocationReferenceRepository(
            db_session
        ).list_for_contract(ctx["company_id"], ctx["contract"].id)
        assert len(refs_after) == 2

        original_after = next(r for r in refs_after if r.id == original.id)
        assert (
            original_after.id,
            original_after.allocated_amount,
            original_after.is_reversal,
            original_after.reverses_allocation_reference_id,
        ) == original_snapshot  # BR-INST-017: original row never mutated

        reversal_row = next(r for r in refs_after if r.is_reversal)
        assert reversal_row.reverses_allocation_reference_id == original.id
        assert reversal_row.allocated_amount == original.allocated_amount
        assert reversal_row.schedule_line_id == original.schedule_line_id

    def test_reversal_restores_schedule_line_outstanding(
        self, db_session: Session
    ) -> None:
        # Deliberately a partial payment against a multi-line schedule
        # (not a full payoff) — reversing a collection that completed
        # the contract is out of this phase's scope (no un-completion
        # path exists; _LEGAL_TRANSITIONS["COMPLETED"] is terminal by
        # design, not something this phase redesigns).
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("250.00")
        )
        service = build_collection_service(db_session)

        collect_result = service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("250.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        assert collect_result["contract_status"] == "ACTIVE"
        collection_id = uuid.UUID(collect_result["accounting_payment_id"])

        service.reverse_collection(
            ctx["company_id"],
            collection_id,
            reason="Reversal restores outstanding",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )

        allocation_ref_repo = InstallmentAllocationReferenceRepository(db_session)
        net = allocation_ref_repo.get_net_allocated_by_line(
            ctx["company_id"], [ctx["schedule_lines"][0].id]
        )
        assert net.get(ctx["schedule_lines"][0].id, Decimal("0")) == Decimal("0")

    def test_cannot_reverse_the_same_collection_twice(
        self, db_session: Session
    ) -> None:
        from modules.installments.exceptions import InstallmentReversalNotAllowedError

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
        assert collect_result["contract_status"] == "ACTIVE"
        collection_id = uuid.UUID(collect_result["accounting_payment_id"])

        service.reverse_collection(
            ctx["company_id"],
            collection_id,
            reason="First reversal",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )

        try:
            service.reverse_collection(
                ctx["company_id"],
                collection_id,
                reason="Second reversal attempt",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )
            raise AssertionError("expected InstallmentReversalNotAllowedError")
        except InstallmentReversalNotAllowedError:
            pass
