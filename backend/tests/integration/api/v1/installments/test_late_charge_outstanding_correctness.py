"""[Epic 10, Phase 12 closure follow-up] Financial correctness + tenant
isolation regression for the batched
``InstallmentReportingService._sum_late_charge_outstanding()`` (see
``tests/performance/installments/test_late_charge_outstanding_performance.py``
for the query-count side of this fix).

Proves the new single-aggregate-query implementation
(``AccountingIntegrationGateway.sum_ar_transactions_outstanding()`` ->
``AccountsReceivableService.sum_outstanding_by_ids()`` ->
``ARTransactionRepository.sum_outstanding_excluding_written_off()``)
computes EXACTLY the same total the old per-row loop did:

    for charge in list_for_company(company_id):       # already excludes waived
        if charge.accounting_ar_transaction_id is None: skip
        ar = get_ar_transaction(company_id, id)
        if ar is None or ar.status == "WRITTEN_OFF": skip
        if ar.outstanding_amount > 0: total += ar.outstanding_amount

i.e. only OPEN/PARTIALLY_PAID/etc. (non-WRITTEN_OFF) transactions with a
positive outstanding balance, linked from a non-waived late charge,
company-scoped — never a shadow balance, never cross-tenant leakage.

Real PostgreSQL (schedule/AR tables require it).
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from modules.accounting.dependencies import (
    build_allocation_engine,
    build_ar_service,
    build_payment_service,
)
from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.installments.models.contract import InstallmentContract
from modules.installments.models.late_charge import InstallmentLateCharge
from modules.installments.models.schedule import (
    InstallmentScheduleLine,
    InstallmentScheduleVersion,
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
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
)


def _build_reporting_service(db_session: Session) -> InstallmentReportingService:
    gateway = AccountingIntegrationGateway(
        ar_service=build_ar_service(db_session, with_sales_sync=False),
        payment_service=build_payment_service(db_session),
        allocation_engine=build_allocation_engine(db_session),
    )
    return InstallmentReportingService(
        contract_repo=InstallmentContractRepository(db_session),
        schedule_repo=InstallmentScheduleRepository(db_session),
        allocation_ref_repo=InstallmentAllocationReferenceRepository(db_session),
        late_charge_repo=InstallmentLateChargeRepository(db_session),
        audit_repo=InstallmentAuditLogRepository(db_session),
        plan_template_repo=InstallmentPlanTemplateRepository(db_session),
        accounting_gateway=gateway,
    )


def _ledger_id(db: Session, company_id: uuid.UUID, customer_id: uuid.UUID) -> uuid.UUID:
    return db.execute(
        select(CustomerLedger.id).where(
            CustomerLedger.company_id == company_id,
            CustomerLedger.customer_id == customer_id,
        )
    ).scalar_one()


def _add_late_charge(
    db: Session,
    *,
    company_id: uuid.UUID,
    ledger_id: uuid.UUID,
    contract_id: uuid.UUID,
    schedule_line_id: uuid.UUID,
    occurrence_date: date,
    outstanding_amount: Decimal,
    ar_status: str,
    waived: bool = False,
) -> None:
    """Insert one ``InstallmentLateCharge`` + its backing ``DEBIT_NOTE``
    ``ARTransaction``, with full control over the exact combination of
    AR status / outstanding amount / waiver state each correctness
    scenario needs."""
    ar_id = uuid.uuid4()
    db.execute(
        insert(ARTransaction),
        [
            {
                "id": ar_id,
                "company_id": company_id,
                "customer_ledger_id": ledger_id,
                "transaction_type": "DEBIT_NOTE",
                "transaction_date": occurrence_date,
                "currency_code": "USD",
                "exchange_rate": Decimal("1"),
                "amount_foreign": Decimal("25.00"),
                "amount_base": Decimal("25.00"),
                "outstanding_amount": outstanding_amount,
                "status": ar_status,
                "source_document_type": "InstallmentLateCharge",
            }
        ],
    )
    late_charge = InstallmentLateCharge(
        company_id=company_id,
        contract_id=contract_id,
        schedule_line_id=schedule_line_id,
        charge_amount=Decimal("25.00"),
        overdue_occurrence_date=occurrence_date,
        accounting_ar_transaction_id=ar_id,
    )
    if waived:
        late_charge.waived_at = date.today()  # any non-None sentinel value
        late_charge.waived_by = None
        late_charge.waived_reason = "test waiver"
    db.add(late_charge)
    db.commit()


def _add_second_contract_same_company(db: Session, *, company_id: uuid.UUID) -> dict:
    """Add a second, independent contract + one schedule line to a
    company ``build_active_contract_with_schedule()`` already set up
    (GL accounts, fiscal year, ``AccountingConfiguration``) — calling
    that fixture twice for the SAME ``company_id`` fails on the
    company's own GL account-code uniqueness constraint (each call
    creates its own '1100'/'4000'/etc. accounts), so a second contract
    within one company needs its own narrower builder that reuses the
    company-level setup and only adds a new customer ledger + contract
    + schedule line."""
    customer_id = uuid.uuid4()
    ar_service = build_ar_service(db, with_sales_sync=False)
    ledger = ar_service.get_or_create_ledger(company_id, customer_id)
    db.commit()

    today = date.today()
    contract = InstallmentContract(
        company_id=company_id,
        contract_number=f"IC-{uuid.uuid4().hex[:8]}",
        customer_id=customer_id,
        sales_invoice_id=uuid.uuid4(),
        contract_date=today,
        principal_amount=Decimal("100.00"),
        down_payment_amount=Decimal("0"),
        markup_amount=Decimal("0"),
        contractual_total=Decimal("100.00"),
        installment_count=1,
        frequency="MONTHLY",
        first_due_date=today,
        maturity_date=today,
        currency_code="USD",
        status="ACTIVE",
        terms_snapshot={"grace_period_days": 0, "late_charge_policy": None},
    )
    contract = InstallmentContractRepository(db).create(contract)

    version = InstallmentScheduleVersion(
        company_id=company_id,
        contract_id=contract.id,
        version_number=1,
        status="ACTIVE",
    )
    line = InstallmentScheduleLine(
        company_id=company_id,
        sequence=1,
        due_date=today,
        scheduled_amount=Decimal("100.00"),
    )
    InstallmentScheduleRepository(db).create_version_with_lines(version, [line])
    contract.active_schedule_version_id = version.id
    db.add(contract)
    db.commit()
    db.refresh(contract)

    return {
        "company_id": company_id,
        "customer_id": customer_id,
        "contract": contract,
        "schedule_lines": [line],
        "ledger": ledger,
    }


class TestLateChargeOutstandingFinancialCorrectness:
    def test_covers_unpaid_partial_paid_waived_and_written_off(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(db_session, installment_count=1)
        company_id = ctx["company_id"]
        ledger_id = _ledger_id(db_session, company_id, ctx["customer_id"])
        line_id = ctx["schedule_lines"][0].id
        contract_id = ctx["contract"].id
        today = date.today()

        # 1. Unpaid — fully outstanding, counted in full.
        _add_late_charge(
            db_session,
            company_id=company_id,
            ledger_id=ledger_id,
            contract_id=contract_id,
            schedule_line_id=line_id,
            occurrence_date=today,
            outstanding_amount=Decimal("25.00"),
            ar_status="OPEN",
        )
        # 2. Partially paid/allocated — only the remaining balance counts.
        _add_late_charge(
            db_session,
            company_id=company_id,
            ledger_id=ledger_id,
            contract_id=contract_id,
            schedule_line_id=line_id,
            occurrence_date=today - timedelta(days=1),
            outstanding_amount=Decimal("10.00"),
            ar_status="PARTIALLY_PAID",
        )
        # 3. Fully paid — zero outstanding, contributes nothing.
        _add_late_charge(
            db_session,
            company_id=company_id,
            ledger_id=ledger_id,
            contract_id=contract_id,
            schedule_line_id=line_id,
            occurrence_date=today - timedelta(days=2),
            outstanding_amount=Decimal("0.00"),
            ar_status="PAID",
        )
        # 4. Waived — excluded entirely regardless of its AR transaction's
        #    own (still-open) outstanding balance, since list_for_company()
        #    filters out waived late charges before the batch AR read ever
        #    sees this row's accounting_ar_transaction_id.
        _add_late_charge(
            db_session,
            company_id=company_id,
            ledger_id=ledger_id,
            contract_id=contract_id,
            schedule_line_id=line_id,
            occurrence_date=today - timedelta(days=3),
            outstanding_amount=Decimal("25.00"),
            ar_status="OPEN",
            waived=True,
        )
        # 5. Written off — excluded regardless of outstanding_amount.
        _add_late_charge(
            db_session,
            company_id=company_id,
            ledger_id=ledger_id,
            contract_id=contract_id,
            schedule_line_id=line_id,
            occurrence_date=today - timedelta(days=4),
            outstanding_amount=Decimal("25.00"),
            ar_status="WRITTEN_OFF",
        )

        svc = _build_reporting_service(db_session)
        total = svc._sum_late_charge_outstanding(company_id)

        # Only scenarios 1 (25.00) + 2 (10.00) contribute -> 35.00.
        assert total == Decimal("35.00")

    def test_multiple_contracts_aggregate_together(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        ctx1 = build_active_contract_with_schedule(
            db_session, installment_count=1, company_id=company_id
        )
        ctx2 = _add_second_contract_same_company(db_session, company_id=company_id)
        today = date.today()

        _add_late_charge(
            db_session,
            company_id=company_id,
            ledger_id=_ledger_id(db_session, company_id, ctx1["customer_id"]),
            contract_id=ctx1["contract"].id,
            schedule_line_id=ctx1["schedule_lines"][0].id,
            occurrence_date=today,
            outstanding_amount=Decimal("25.00"),
            ar_status="OPEN",
        )
        _add_late_charge(
            db_session,
            company_id=company_id,
            ledger_id=_ledger_id(db_session, company_id, ctx2["customer_id"]),
            contract_id=ctx2["contract"].id,
            schedule_line_id=ctx2["schedule_lines"][0].id,
            occurrence_date=today,
            outstanding_amount=Decimal("40.00"),
            ar_status="OPEN",
        )

        svc = _build_reporting_service(db_session)
        total = svc._sum_late_charge_outstanding(company_id)

        assert total == Decimal("65.00")

    def test_unrelated_accounting_transaction_never_counted(
        self, db_session: Session
    ) -> None:
        """The contract's own originating-invoice ``ARTransaction`` (a
        large ``INVOICE``, not referenced by any late charge) must never
        leak into the late-charge-only sum — proves the batch query is
        scoped to exactly the ids collected from late charges, never
        "every open AR transaction for the company"."""
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("1000.00")
        )
        company_id = ctx["company_id"]
        ledger_id = _ledger_id(db_session, company_id, ctx["customer_id"])

        _add_late_charge(
            db_session,
            company_id=company_id,
            ledger_id=ledger_id,
            contract_id=ctx["contract"].id,
            schedule_line_id=ctx["schedule_lines"][0].id,
            occurrence_date=date.today(),
            outstanding_amount=Decimal("25.00"),
            ar_status="OPEN",
        )

        svc = _build_reporting_service(db_session)
        total = svc._sum_late_charge_outstanding(company_id)

        # NOT 1000.00 (the invoice) + 25.00 — only the late charge's own
        # ARTransaction contributes.
        assert total == Decimal("25.00")


class TestLateChargeOutstandingTenantIsolation:
    def test_other_companys_late_charges_never_leak_into_this_companys_sum(
        self, db_session: Session
    ) -> None:
        """Direct data evidence (section 7): two REAL companies, each
        with its own late charge, prove Tenant B's amount is absent from
        Tenant A's ``_sum_late_charge_outstanding()`` result and vice
        versa — not merely inferred from reading the SQL."""
        ctx_a = build_active_contract_with_schedule(db_session, installment_count=1)
        ctx_b = build_active_contract_with_schedule(db_session, installment_count=1)
        assert ctx_a["company_id"] != ctx_b["company_id"]
        today = date.today()

        _add_late_charge(
            db_session,
            company_id=ctx_a["company_id"],
            ledger_id=_ledger_id(db_session, ctx_a["company_id"], ctx_a["customer_id"]),
            contract_id=ctx_a["contract"].id,
            schedule_line_id=ctx_a["schedule_lines"][0].id,
            occurrence_date=today,
            outstanding_amount=Decimal("25.00"),
            ar_status="OPEN",
        )
        _add_late_charge(
            db_session,
            company_id=ctx_b["company_id"],
            ledger_id=_ledger_id(db_session, ctx_b["company_id"], ctx_b["customer_id"]),
            contract_id=ctx_b["contract"].id,
            schedule_line_id=ctx_b["schedule_lines"][0].id,
            occurrence_date=today,
            outstanding_amount=Decimal("999.00"),
            ar_status="OPEN",
        )

        svc = _build_reporting_service(db_session)
        total_a = svc._sum_late_charge_outstanding(ctx_a["company_id"])
        total_b = svc._sum_late_charge_outstanding(ctx_b["company_id"])

        assert total_a == Decimal("25.00")
        assert total_b == Decimal("999.00")

    def test_reused_customer_id_across_companies_stays_isolated(
        self, db_session: Session
    ) -> None:
        """Stress case mirroring the Phase-12 closure commit's own
        same-customer-id-across-companies precedent — a shared
        ``customer_id`` must not cause Accounting's per-company
        ``CustomerLedger``/``ARTransaction`` scoping (or this batch
        query's ``company_id`` filter) to blend the two tenants'
        amounts."""
        shared_customer_id = uuid.uuid4()
        ctx_a = build_active_contract_with_schedule(
            db_session, installment_count=1, customer_id=shared_customer_id
        )
        ctx_b = build_active_contract_with_schedule(
            db_session, installment_count=1, customer_id=shared_customer_id
        )
        today = date.today()

        _add_late_charge(
            db_session,
            company_id=ctx_a["company_id"],
            ledger_id=_ledger_id(db_session, ctx_a["company_id"], shared_customer_id),
            contract_id=ctx_a["contract"].id,
            schedule_line_id=ctx_a["schedule_lines"][0].id,
            occurrence_date=today,
            outstanding_amount=Decimal("15.00"),
            ar_status="OPEN",
        )
        _add_late_charge(
            db_session,
            company_id=ctx_b["company_id"],
            ledger_id=_ledger_id(db_session, ctx_b["company_id"], shared_customer_id),
            contract_id=ctx_b["contract"].id,
            schedule_line_id=ctx_b["schedule_lines"][0].id,
            occurrence_date=today,
            outstanding_amount=Decimal("50.00"),
            ar_status="OPEN",
        )

        svc = _build_reporting_service(db_session)
        assert svc._sum_late_charge_outstanding(ctx_a["company_id"]) == Decimal("15.00")
        assert svc._sum_late_charge_outstanding(ctx_b["company_id"]) == Decimal("50.00")
