"""[Epic 10, Phase 12, T213] Performance test — report/list pagination
remains responsive under volume, no N+1 query pattern (batch-load
allocation references per page, never per-line, plan.md §25).

Seeds many contracts (each with its own schedule) via SQLAlchemy Core
bulk inserts (the established
``tests/performance/accounting/test_ar_aging_performance.py`` precedent),
then counts the ACTUAL number of SQL statements a single report page
issues via a ``before_cursor_execute`` listener — the real proof that
query count is O(1) per page, not O(total rows in the company).

Real PostgreSQL (schedule persistence requires it).
"""

from __future__ import annotations

import time
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import bindparam, event, insert, update
from sqlalchemy.orm import Session

from modules.accounting.dependencies import (
    build_allocation_engine,
    build_ar_service,
    build_payment_service,
)
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from modules.installments.models.contract import InstallmentContract
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

_CONTRACT_COUNT = 500
_LINES_PER_CONTRACT = 3
_PAGE_SIZE = 20
_TARGET_SECONDS = 3


def _seed_company_with_many_contracts(
    db: Session, company_id: uuid.UUID
) -> tuple[uuid.UUID, date]:
    """Bulk-insert many contracts, each with its own 3-line schedule —
    SQLAlchemy Core inserts, no ORM per-row overhead, matching the
    accounting aging-benchmark's own established technique."""
    account_repo = AccountRepository(db)
    fiscal_service = FiscalCalendarService(
        db=db,
        year_repo=FiscalYearRepository(db),
        period_repo=FiscalPeriodRepository(db),
        opening_balance_repo=OpeningBalanceRepository(db),
        audit_service=AuditLogService(
            db=db, audit_repo=AccountingAuditLogRepository(db)
        ),
    )
    ar_account = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1100",
            account_name="AR",
            account_type="ASSET",
        )
    )
    revenue_account = account_repo.create(
        Account(
            company_id=company_id,
            account_code="4000",
            account_name="Revenue",
            account_type="REVENUE",
        )
    )
    today = date.today()
    fiscal_service.create_fiscal_year(
        company_id,
        f"FY-{uuid.uuid4().hex[:8]}",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )
    AccountingConfigurationRepository(db).create(
        AccountingConfiguration(
            company_id=company_id,
            default_ar_account_id=ar_account.id,
            default_revenue_account_id=revenue_account.id,
        )
    )
    db.commit()

    # InstallmentContract.active_schedule_version_id and
    # InstallmentScheduleVersion.contract_id form a circular FK pair, so
    # neither table can be bulk-inserted first while referencing the
    # other's not-yet-existing rows. active_schedule_version_id is
    # nullable at the ORM/DB level for exactly this reason (see
    # contract.py's module docstring) — insert contracts with it NULL,
    # insert versions (which validly reference the now-existing
    # contracts), then bulk-UPDATE contracts to point at their version.
    contract_ids = [uuid.uuid4() for _ in range(_CONTRACT_COUNT)]
    version_ids = [uuid.uuid4() for _ in range(_CONTRACT_COUNT)]

    contract_rows = [
        {
            "id": contract_ids[i],
            "company_id": company_id,
            "contract_number": f"PERF-IC-{i:06d}",
            "customer_id": uuid.uuid4(),
            "sales_invoice_id": uuid.uuid4(),
            "contract_date": today,
            "principal_amount": Decimal("300.00"),
            "down_payment_amount": Decimal("0"),
            "markup_amount": Decimal("0"),
            "contractual_total": Decimal("300.00"),
            "installment_count": _LINES_PER_CONTRACT,
            "frequency": "MONTHLY",
            "first_due_date": today,
            "maturity_date": today + timedelta(days=90),
            "currency_code": "USD",
            "status": "ACTIVE",
            "terms_snapshot": {"grace_period_days": 0, "late_charge_policy": None},
            "active_schedule_version_id": None,
        }
        for i in range(_CONTRACT_COUNT)
    ]
    db.execute(insert(InstallmentContract), contract_rows)

    version_rows = [
        {
            "id": version_ids[i],
            "company_id": company_id,
            "contract_id": contract_ids[i],
            "version_number": 1,
            "status": "ACTIVE",
        }
        for i in range(_CONTRACT_COUNT)
    ]
    db.execute(insert(InstallmentScheduleVersion), version_rows)

    db.execute(
        update(InstallmentContract.__table__)
        .where(InstallmentContract.__table__.c.id == bindparam("_id"))
        .values(active_schedule_version_id=bindparam("_version_id")),
        [
            {"_id": contract_ids[i], "_version_id": version_ids[i]}
            for i in range(_CONTRACT_COUNT)
        ],
    )

    line_rows = []
    for i in range(_CONTRACT_COUNT):
        for seq in range(_LINES_PER_CONTRACT):
            line_rows.append(
                {
                    "company_id": company_id,
                    "schedule_version_id": version_ids[i],
                    "sequence": seq + 1,
                    "due_date": today + timedelta(days=seq * 30),
                    "scheduled_amount": Decimal("100.00"),
                }
            )
    db.execute(insert(InstallmentScheduleLine), line_rows)
    db.commit()

    return company_id, today


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


class _QueryCounter:
    def __init__(self) -> None:
        self.count = 0

    def __call__(self, *args: object, **kwargs: object) -> None:
        self.count += 1


class TestReportPaginationPerformance:
    def test_due_report_page_is_fast_and_query_count_is_bounded(
        self, db_session: Session, monkeypatch
    ) -> None:
        company_id, today = _seed_company_with_many_contracts(db_session, uuid.uuid4())
        # Seeding uses local date.today() for due dates (see
        # _seed_company_with_many_contracts); production reads business
        # date from UTC (business_date.py, FR-INST-115). Pin
        # get_business_date() to the exact date seeding used so "due
        # today" is deterministic regardless of which side of the
        # UTC/local midnight boundary the test happens to run on.
        monkeypatch.setattr(
            "modules.installments.services.reporting_service.get_business_date",
            lambda: today,
        )
        svc = _build_reporting_service(db_session)

        counter = _QueryCounter()
        event.listen(db_session.bind, "before_cursor_execute", counter)
        try:
            start = time.perf_counter()
            rows, total = svc.get_due_report(company_id, skip=0, limit=_PAGE_SIZE)
            elapsed = time.perf_counter() - start
        finally:
            event.remove(db_session.bind, "before_cursor_execute", counter)

        # Only the first line of each contract's 3-line schedule is due
        # "today" (the other two fall 30/60 days out and are UPCOMING,
        # not DUE) — one due line per contract.
        assert total == _CONTRACT_COUNT
        assert elapsed < _TARGET_SECONDS, (
            f"due report page took {elapsed:.2f}s against "
            f"{_CONTRACT_COUNT} contracts, expected < {_TARGET_SECONDS}s"
        )
        # O(1) queries per page: one count query, one paginated-rows
        # query, one batch net-allocated lookup — never one query per
        # contract/line (T213's explicit N+1 prohibition). A generous
        # upper bound (10) absorbs connection/transaction bookkeeping
        # statements without weakening the actual claim: query count
        # must NOT scale with `_CONTRACT_COUNT` (500) or
        # `_CONTRACT_COUNT * _LINES_PER_CONTRACT` (1500).
        assert counter.count < 10, (
            f"expected O(1) queries per report page, got {counter.count} "
            f"against {_CONTRACT_COUNT} contracts"
        )

    def test_overdue_report_page_query_count_is_bounded(
        self, db_session: Session
    ) -> None:
        company_id, _today = _seed_company_with_many_contracts(db_session, uuid.uuid4())
        svc = _build_reporting_service(db_session)

        counter = _QueryCounter()
        event.listen(db_session.bind, "before_cursor_execute", counter)
        try:
            svc.get_overdue_report(company_id, skip=0, limit=_PAGE_SIZE)
        finally:
            event.remove(db_session.bind, "before_cursor_execute", counter)

        assert counter.count < 10

    def test_contract_register_page_query_count_is_bounded(
        self, db_session: Session
    ) -> None:
        company_id, _today = _seed_company_with_many_contracts(db_session, uuid.uuid4())
        svc = _build_reporting_service(db_session)

        counter = _QueryCounter()
        event.listen(db_session.bind, "before_cursor_execute", counter)
        try:
            rows, total = svc.get_contract_register(
                company_id, skip=0, limit=_PAGE_SIZE
            )
        finally:
            event.remove(db_session.bind, "before_cursor_execute", counter)

        assert total == _CONTRACT_COUNT
        assert len(rows) == _PAGE_SIZE
        assert counter.count < 5

    def test_second_page_is_not_slower_than_first_page(
        self, db_session: Session
    ) -> None:
        """A stronger regression guard against OFFSET-scanning-style
        N+1-adjacent patterns: page 10 (skip=180) must not take
        meaningfully longer than page 1 (skip=0)."""
        company_id, _today = _seed_company_with_many_contracts(db_session, uuid.uuid4())
        svc = _build_reporting_service(db_session)

        start_first = time.perf_counter()
        svc.get_due_report(company_id, skip=0, limit=_PAGE_SIZE)
        first_page_elapsed = time.perf_counter() - start_first

        start_later = time.perf_counter()
        svc.get_due_report(company_id, skip=180, limit=_PAGE_SIZE)
        later_page_elapsed = time.perf_counter() - start_later

        assert later_page_elapsed < max(first_page_elapsed * 5, 1.0)
