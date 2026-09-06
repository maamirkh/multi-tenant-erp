"""[Epic 10, Phase 12 — closure fix] Multi-tenant AGGREGATE isolation for
every Phase-12 report type + dashboard KPIs.

Closes the tenant-isolation evidence gap identified in Phase-12 closure
verification: prior test coverage only proved individual-resource IDOR
(404 on a wrong company_id) for earlier phases' single-record endpoints —
no test proved that a REPORT or the DASHBOARD's aggregate figures cannot
be inflated/contaminated by another tenant's rows.

Methodology (per verification instruction): capture Tenant A's result
BEFORE Tenant B exists, seed Tenant B with deliberately overlapping data
(the SAME customer_id reused across two different companies — the
sharpest possible temptation for a missing/wrong company_id predicate to
leak), then re-capture Tenant A's result and assert it is IDENTICAL.
Inspecting `company_id` predicates in the source is not accepted as proof
on its own; every check below exercises the real service layer against
real Postgres rows for two genuinely distinct companies.

Real PostgreSQL throughout (schedule persistence requires it).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.accounting.dependencies import (
    build_allocation_engine,
    build_ar_service,
    build_payment_service,
)
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.late_charge import (
    InstallmentLateChargeRepository,
)
from modules.installments.repositories.plan_template import (
    InstallmentPlanTemplateRepository,
)
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.services.accounting_gateway import (
    AccountingIntegrationGateway,
)
from modules.installments.services.reporting_service import (
    InstallmentReportingService,
)
from tests.security.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
    build_contract_service,
    build_settlement_service,
)


def _build_reporting_service(db: Session) -> InstallmentReportingService:
    gateway = AccountingIntegrationGateway(
        ar_service=build_ar_service(db, with_sales_sync=False),
        payment_service=build_payment_service(db),
        allocation_engine=build_allocation_engine(db),
    )
    return InstallmentReportingService(
        contract_repo=InstallmentContractRepository(db),
        schedule_repo=InstallmentScheduleRepository(db),
        allocation_ref_repo=InstallmentAllocationReferenceRepository(db),
        late_charge_repo=InstallmentLateChargeRepository(db),
        audit_repo=InstallmentAuditLogRepository(db),
        plan_template_repo=InstallmentPlanTemplateRepository(db),
        accounting_gateway=gateway,
    )


class TestContractRegisterIsolation:
    def test_tenant_b_contracts_never_appear_in_tenant_a_register(
        self, pg_db_session: Session
    ) -> None:
        shared_customer = uuid.uuid4()
        ctx_a = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            customer_id=shared_customer,
        )
        svc = _build_reporting_service(pg_db_session)
        before_rows, before_total = svc.get_contract_register(
            ctx_a["company_id"], skip=0, limit=20
        )

        # Tenant B: same customer_id, larger amount — maximum temptation
        # for a company_id-scoping bug to leak this into Tenant A's page.
        build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("999.00"),
            customer_id=shared_customer,
        )

        after_rows, after_total = svc.get_contract_register(
            ctx_a["company_id"], skip=0, limit=20
        )
        assert after_total == before_total == 1
        assert after_rows == before_rows
        assert after_rows[0]["contract_id"] == str(ctx_a["contract"].id)


class TestDueOverdueAgingIsolation:
    def test_due_report_totals_unaffected_by_tenant_b(
        self, pg_db_session: Session
    ) -> None:
        shared_customer = uuid.uuid4()
        ctx_a = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            customer_id=shared_customer,
        )
        svc = _build_reporting_service(pg_db_session)
        before_rows, before_total = svc.get_due_report(
            ctx_a["company_id"], skip=0, limit=20
        )

        build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("500.00"),
            customer_id=shared_customer,
        )

        after_rows, after_total = svc.get_due_report(
            ctx_a["company_id"], skip=0, limit=20
        )
        assert after_total == before_total
        assert after_rows == before_rows

    def test_overdue_report_totals_unaffected_by_tenant_b(
        self, pg_db_session: Session
    ) -> None:
        shared_customer = uuid.uuid4()
        ctx_a = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            grace_period_days=0,
            customer_id=shared_customer,
        )
        svc = _build_reporting_service(pg_db_session)
        before_rows, before_total = svc.get_overdue_report(
            ctx_a["company_id"], skip=0, limit=20
        )

        build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("500.00"),
            grace_period_days=0,
            customer_id=shared_customer,
        )

        after_rows, after_total = svc.get_overdue_report(
            ctx_a["company_id"], skip=0, limit=20
        )
        assert after_total == before_total
        assert after_rows == before_rows

    def test_aging_report_totals_unaffected_by_tenant_b(
        self, pg_db_session: Session
    ) -> None:
        shared_customer = uuid.uuid4()
        ctx_a = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            customer_id=shared_customer,
        )
        svc = _build_reporting_service(pg_db_session)
        before_rows, before_total = svc.get_aging_report(
            ctx_a["company_id"], skip=0, limit=20
        )

        build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("500.00"),
            customer_id=shared_customer,
        )

        after_rows, after_total = svc.get_aging_report(
            ctx_a["company_id"], skip=0, limit=20
        )
        assert after_total == before_total
        assert after_rows == before_rows


class TestCollectionReportIsolation:
    def test_collection_report_never_includes_tenant_b_collections(
        self, pg_db_session: Session
    ) -> None:
        shared_customer = uuid.uuid4()
        ctx_a = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            customer_id=shared_customer,
        )
        collection_svc_a = build_collection_service(pg_db_session)
        collection_svc_a.record_collection(
            ctx_a["company_id"],
            ctx_a["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx_a["bank_account"].id,
        )
        svc = _build_reporting_service(pg_db_session)
        before_rows, before_total = svc.get_collection_report(
            ctx_a["company_id"], skip=0, limit=20
        )
        assert before_total == 1

        # Tenant B: same customer_id, a larger collection recorded.
        ctx_b = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("777.00"),
            customer_id=shared_customer,
        )
        collection_svc_b = build_collection_service(pg_db_session)
        collection_svc_b.record_collection(
            ctx_b["company_id"],
            ctx_b["contract"].id,
            amount=Decimal("777.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx_b["bank_account"].id,
        )

        after_rows, after_total = svc.get_collection_report(
            ctx_a["company_id"], skip=0, limit=20
        )
        assert after_total == before_total == 1
        assert after_rows == before_rows
        assert after_rows[0]["contract_id"] == str(ctx_a["contract"].id)


class TestSettlementReportIsolation:
    def test_settlement_report_never_includes_tenant_b_settlement(
        self, pg_db_session: Session
    ) -> None:
        shared_customer = uuid.uuid4()
        ctx_a = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            customer_id=shared_customer,
        )
        settlement_svc_a = build_settlement_service(pg_db_session)
        settlement_svc_a.execute(
            ctx_a["company_id"],
            ctx_a["contract"].id,
            Decimal("100.00"),
            ctx_a["today"],
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx_a["bank_account"].id,
        )
        svc = _build_reporting_service(pg_db_session)
        before_rows, before_total = svc.get_settlement_report(
            ctx_a["company_id"], skip=0, limit=20
        )
        assert before_total == 1

        ctx_b = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("888.00"),
            customer_id=shared_customer,
        )
        settlement_svc_b = build_settlement_service(pg_db_session)
        settlement_svc_b.execute(
            ctx_b["company_id"],
            ctx_b["contract"].id,
            Decimal("888.00"),
            ctx_b["today"],
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx_b["bank_account"].id,
        )

        after_rows, after_total = svc.get_settlement_report(
            ctx_a["company_id"], skip=0, limit=20
        )
        assert after_total == before_total == 1
        assert after_rows == before_rows
        assert after_rows[0]["contract_id"] == str(ctx_a["contract"].id)


class TestDefaultWriteoffReportIsolation:
    def test_writeoff_report_never_includes_tenant_b_writeoff(
        self, pg_db_session: Session
    ) -> None:
        shared_customer = uuid.uuid4()
        ctx_a = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            customer_id=shared_customer,
        )
        contract_a = ctx_a["contract"]
        contract_a.status = "DEFAULTED"
        contract_a.defaulted_at = contract_a.contract_date
        pg_db_session.add(contract_a)
        pg_db_session.commit()
        contract_svc_a = build_contract_service(pg_db_session)
        contract_svc_a.writeoff(
            ctx_a["company_id"],
            ctx_a["contract"].id,
            "Uncollectible",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )
        svc = _build_reporting_service(pg_db_session)
        before_rows, before_total = svc.get_default_writeoff_report(
            ctx_a["company_id"], skip=0, limit=20
        )
        assert before_total == 1
        assert before_rows[0]["written_off_amount"] == "100.000000"

        ctx_b = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("999.00"),
            customer_id=shared_customer,
        )
        contract_b = ctx_b["contract"]
        contract_b.status = "DEFAULTED"
        contract_b.defaulted_at = contract_b.contract_date
        pg_db_session.add(contract_b)
        pg_db_session.commit()
        contract_svc_b = build_contract_service(pg_db_session)
        contract_svc_b.writeoff(
            ctx_b["company_id"],
            ctx_b["contract"].id,
            "Uncollectible",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )

        after_rows, after_total = svc.get_default_writeoff_report(
            ctx_a["company_id"], skip=0, limit=20
        )
        assert after_total == before_total == 1
        assert after_rows == before_rows
        assert after_rows[0]["written_off_amount"] == "100.000000"


class TestDashboardAggregateIsolation:
    def test_dashboard_totals_unaffected_by_tenant_b_data(
        self, pg_db_session: Session
    ) -> None:
        shared_customer = uuid.uuid4()
        ctx_a = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            customer_id=shared_customer,
        )
        svc = _build_reporting_service(pg_db_session)
        before = svc.get_dashboard(ctx_a["company_id"])
        assert before.active_contract_count == 1
        assert before.outstanding_amount == Decimal("100.00")

        # Tenant B: same customer_id, a much larger contract, a
        # WRITTEN_OFF contract, and a collection — every KPI bucket
        # Tenant A's dashboard reports gets a tempting, differently-sized
        # value to leak from Tenant B if isolation is broken anywhere.
        ctx_b = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("5000.00"),
            customer_id=shared_customer,
        )
        collection_svc_b = build_collection_service(pg_db_session)
        collection_svc_b.record_collection(
            ctx_b["company_id"],
            ctx_b["contract"].id,
            amount=Decimal("5000.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx_b["bank_account"].id,
        )
        # Tenant C: same customer_id again, a WRITTEN_OFF contract — a
        # THIRD tenant, proving the leak-check generalizes beyond a
        # single "other company" (accounts/fiscal year/config are
        # per-company singletons in this fixture, so a second contract
        # for Tenant B's own company_id would collide on unique account
        # codes — a fresh company is the correct way to add more
        # "other-tenant" data, and is just as valid a leak vector as
        # reusing Tenant B's company_id would have been).
        ctx_c = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("777.00"),
            customer_id=shared_customer,
        )
        contract_c = ctx_c["contract"]
        contract_c.status = "DEFAULTED"
        contract_c.defaulted_at = contract_c.contract_date
        pg_db_session.add(contract_c)
        pg_db_session.commit()
        contract_svc_c = build_contract_service(pg_db_session)
        contract_svc_c.writeoff(
            ctx_c["company_id"],
            ctx_c["contract"].id,
            "Uncollectible",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )

        after = svc.get_dashboard(ctx_a["company_id"])
        assert after.active_contract_count == before.active_contract_count == 1
        assert (
            after.outstanding_amount == before.outstanding_amount == Decimal("100.00")
        )
        assert after.collected_today_amount == before.collected_today_amount
        assert after.written_off_balance == before.written_off_balance == Decimal("0")
        assert after.defaulted_balance == before.defaulted_balance == Decimal("0")

        # And each OTHER tenant's own dashboard sees only its own data —
        # Tenant B's collection never appears in Tenant C's figures and
        # vice versa, closing the loop on every pairing.
        dashboard_b = svc.get_dashboard(ctx_b["company_id"])
        assert dashboard_b.collected_today_amount == Decimal("5000.00")
        assert dashboard_b.written_off_balance == Decimal("0")

        dashboard_c = svc.get_dashboard(ctx_c["company_id"])
        assert dashboard_c.written_off_balance == Decimal("777.00")
        assert dashboard_c.collected_today_amount == Decimal("0")
