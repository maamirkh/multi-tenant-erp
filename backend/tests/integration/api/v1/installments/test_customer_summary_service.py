"""[Epic 10, Phase 12, T207] Correctness tests for
``InstallmentCustomerSummaryService`` — read-only, importable by CRM's
``Customer360Service`` in a future, separately-scoped change.

Real PostgreSQL throughout (schedule persistence requires it).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.services.customer_summary_service import (
    InstallmentCustomerSummaryService,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
)


def _build_summary_service(db_session: Session) -> InstallmentCustomerSummaryService:
    return InstallmentCustomerSummaryService(
        contract_repo=InstallmentContractRepository(db_session),
        schedule_repo=InstallmentScheduleRepository(db_session),
        allocation_ref_repo=InstallmentAllocationReferenceRepository(db_session),
    )


class TestCustomerSummary:
    def test_summary_reflects_one_active_contract(self, db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = _build_summary_service(db_session)

        summary = svc.get_summary(ctx["company_id"], ctx["customer_id"])

        assert summary.contract_count == 1
        assert summary.active_contract_count == 1
        assert summary.total_contractual_amount == Decimal("100.00")
        assert summary.total_outstanding_amount == Decimal("100.00")
        assert summary.defaulted_contract_count == 0
        assert summary.written_off_contract_count == 0

    def test_outstanding_drops_to_zero_after_full_collection(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        collection_svc = build_collection_service(db_session)
        collection_svc.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        svc = _build_summary_service(db_session)

        summary = svc.get_summary(ctx["company_id"], ctx["customer_id"])

        assert summary.total_outstanding_amount == Decimal("0")
        # The contract completed — no longer counted as "active".
        assert summary.active_contract_count == 0

    def test_summary_for_unknown_customer_is_all_zero(
        self, db_session: Session
    ) -> None:
        svc = _build_summary_service(db_session)

        summary = svc.get_summary(uuid.uuid4(), uuid.uuid4())

        assert summary.contract_count == 0
        assert summary.total_contractual_amount == Decimal("0")
        assert summary.total_outstanding_amount == Decimal("0")
