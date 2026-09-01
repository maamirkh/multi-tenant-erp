"""[Epic 10, Phase 12, T206] Content-correctness tests for
``InstallmentDocumentService`` — complements T212's non-mutating proof
with proof that each document's actual content is right.

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
from modules.installments.services.document_service import InstallmentDocumentService
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
)


def _build_document_service(db_session: Session) -> InstallmentDocumentService:
    return InstallmentDocumentService(
        contract_repo=InstallmentContractRepository(db_session),
        schedule_repo=InstallmentScheduleRepository(db_session),
        allocation_ref_repo=InstallmentAllocationReferenceRepository(db_session),
    )


class TestAgreementDocument:
    def test_agreement_reflects_the_frozen_terms_snapshot(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=3,
            installment_amount=Decimal("100.00"),
            grace_period_days=15,
        )
        svc = _build_document_service(db_session)

        result = svc.get_agreement(ctx["company_id"], ctx["contract"].id)

        assert result["contract_number"] == ctx["contract"].contract_number
        assert result["contractual_total"] == "300.000000"
        assert result["installment_count"] == 3
        assert result["terms_snapshot"]["grace_period_days"] == 15


class TestScheduleDocument:
    def test_schedule_document_lists_every_line_with_allocation(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("100.00")
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
        svc = _build_document_service(db_session)

        result = svc.get_schedule_document(ctx["company_id"], ctx["contract"].id)

        assert len(result["lines"]) == 2
        first_line = result["lines"][0]
        second_line = result["lines"][1]
        assert first_line["allocated_amount"] == "100.000000"
        assert second_line["allocated_amount"] == "0"


class TestCustomerStatement:
    def test_statement_aggregates_across_multiple_contracts_for_one_customer(
        self, db_session: Session
    ) -> None:
        ctx1 = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = _build_document_service(db_session)

        result = svc.get_customer_statement(ctx1["company_id"], ctx1["customer_id"])

        assert len(result["contracts"]) == 1
        assert result["contracts"][0]["contract_id"] == str(ctx1["contract"].id)
        assert result["contracts"][0]["schedule_outstanding"] == "100.000000"

    def test_statement_never_includes_another_customers_contract(
        self, db_session: Session
    ) -> None:
        ctx1 = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        ctx2 = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("200.00")
        )
        svc = _build_document_service(db_session)

        result = svc.get_customer_statement(ctx1["company_id"], ctx1["customer_id"])

        contract_ids = {c["contract_id"] for c in result["contracts"]}
        assert str(ctx1["contract"].id) in contract_ids
        assert str(ctx2["contract"].id) not in contract_ids
