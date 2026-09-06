"""[Epic 10, Phase 12 — closure fix] Tenant isolation for
``InstallmentDocumentService`` (agreement/schedule/customer-statement) and
``InstallmentCustomerSummaryService`` — closes the Phase-12 tenant-isolation
evidence gap (customer statement/summary sections).

Every document/summary lookup below is attempted with Tenant A's own
company_id against a resource that actually belongs to Tenant B (or vice
versa) — proving IDOR-safe 404 behavior, not merely inspecting the
`company_id`-scoped repository query in the source. The customer-statement
checks additionally reuse the SAME customer_id across two DIFFERENT
companies (the sharpest overlap the data model allows) to prove aggregation
never crosses the tenant boundary even when the non-tenant identifier
matches exactly.

Real PostgreSQL throughout (schedule persistence requires it).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from modules.installments.exceptions import InstallmentNotFoundError
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.services.customer_summary_service import (
    InstallmentCustomerSummaryService,
)
from modules.installments.services.document_service import InstallmentDocumentService
from tests.security.installments.conftest import (
    build_active_contract_with_schedule,
    build_settlement_service,
)


def _build_document_service(db: Session) -> InstallmentDocumentService:
    return InstallmentDocumentService(
        contract_repo=InstallmentContractRepository(db),
        schedule_repo=InstallmentScheduleRepository(db),
        allocation_ref_repo=InstallmentAllocationReferenceRepository(db),
    )


def _build_summary_service(db: Session) -> InstallmentCustomerSummaryService:
    return InstallmentCustomerSummaryService(
        contract_repo=InstallmentContractRepository(db),
        schedule_repo=InstallmentScheduleRepository(db),
        allocation_ref_repo=InstallmentAllocationReferenceRepository(db),
    )


class TestAgreementDocumentIsolation:
    def test_tenant_a_cannot_retrieve_tenant_b_agreement(
        self, pg_db_session: Session
    ) -> None:
        ctx_b = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = _build_document_service(pg_db_session)
        company_a = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.get_agreement(company_a, ctx_b["contract"].id)


class TestScheduleDocumentIsolation:
    def test_tenant_a_cannot_retrieve_tenant_b_schedule_document(
        self, pg_db_session: Session
    ) -> None:
        ctx_b = build_active_contract_with_schedule(
            pg_db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        svc = _build_document_service(pg_db_session)
        company_a = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.get_schedule_document(company_a, ctx_b["contract"].id)


class TestSettlementQuoteDocumentIsolation:
    def test_tenant_a_cannot_retrieve_tenant_b_settlement_quote(
        self, pg_db_session: Session
    ) -> None:
        ctx_b = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_settlement_service(pg_db_session)
        company_a = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.generate_quote(
                company_a, ctx_b["contract"].id, ctx_b["today"], actor_id=None
            )


class TestCustomerStatementIsolation:
    def test_tenant_a_gets_empty_statement_for_tenant_b_customer(
        self, pg_db_session: Session
    ) -> None:
        """Tenant A queries a customer_id that only exists as Tenant B's
        customer — must see zero contracts, never Tenant B's data."""
        ctx_b = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = _build_document_service(pg_db_session)
        company_a = uuid.uuid4()

        result = svc.get_customer_statement(company_a, ctx_b["customer_id"])

        assert result["contracts"] == []

    def test_statement_never_aggregates_tenant_b_contract_for_shared_customer_id(
        self, pg_db_session: Session
    ) -> None:
        """The sharpest overlap case: the SAME customer_id is reused
        across two genuinely different companies. Tenant A's statement
        for that customer_id must show ONLY Tenant A's own contract."""
        shared_customer = uuid.uuid4()
        ctx_a = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            customer_id=shared_customer,
        )
        ctx_b = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("999.00"),
            customer_id=shared_customer,
        )
        svc = _build_document_service(pg_db_session)

        result_a = svc.get_customer_statement(ctx_a["company_id"], shared_customer)
        result_b = svc.get_customer_statement(ctx_b["company_id"], shared_customer)

        assert len(result_a["contracts"]) == 1
        assert result_a["contracts"][0]["contract_id"] == str(ctx_a["contract"].id)
        assert result_a["contracts"][0]["contractual_total"] == "100.000000"

        assert len(result_b["contracts"]) == 1
        assert result_b["contracts"][0]["contract_id"] == str(ctx_b["contract"].id)
        assert result_b["contracts"][0]["contractual_total"] == "999.000000"


class TestCustomerSummaryIsolation:
    def test_summary_never_aggregates_tenant_b_contract_for_shared_customer_id(
        self, pg_db_session: Session
    ) -> None:
        shared_customer = uuid.uuid4()
        ctx_a = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            customer_id=shared_customer,
        )
        build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("999.00"),
            customer_id=shared_customer,
        )
        svc = _build_summary_service(pg_db_session)

        summary_a = svc.get_summary(ctx_a["company_id"], shared_customer)

        assert summary_a.contract_count == 1
        assert summary_a.total_contractual_amount == Decimal("100.00")
        assert summary_a.total_outstanding_amount == Decimal("100.00")

    def test_summary_for_tenant_b_customer_under_tenant_a_is_all_zero(
        self, pg_db_session: Session
    ) -> None:
        ctx_b = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = _build_summary_service(pg_db_session)
        company_a = uuid.uuid4()

        summary = svc.get_summary(company_a, ctx_b["customer_id"])

        assert summary.contract_count == 0
        assert summary.total_contractual_amount == Decimal("0")
        assert summary.total_outstanding_amount == Decimal("0")
