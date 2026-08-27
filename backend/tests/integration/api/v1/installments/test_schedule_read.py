"""[Epic 10, Phase 7, T129] Service tests for
``InstallmentContractService.get_active_schedule()``/``get_schedule_version()``
and their ``InstallmentScheduleRead``/``InstallmentScheduleLineRead``
serialization — proves the schema correctly validates a list of raw
``InstallmentScheduleLine`` ORM rows (``from_attributes=True``) via the
router's direct-constructor usage pattern, not only via ``.model_validate()``.

Real Postgres (schedule tables require it).
"""

from __future__ import annotations

from decimal import Decimal

from modules.installments.exceptions import InstallmentNotFoundError
from modules.installments.schemas.schedule import InstallmentScheduleRead
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
)
from tests.integration.api.v1.installments.test_activation_service import (
    _build_contract_service,
)


class TestGetActiveSchedule:
    def test_returns_active_version_and_lines_serializable(self, db_session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=3, installment_amount=Decimal("100.00")
        )
        service = _build_contract_service(db_session)

        contract, version, lines = service.get_active_schedule(
            ctx["company_id"], ctx["contract"].id
        )

        assert contract.id == ctx["contract"].id
        assert version.version_number == 1
        assert version.status == "ACTIVE"
        assert len(lines) == 3

        # Exercises the router's exact direct-constructor call shape —
        # a list of raw ORM InstallmentScheduleLine rows, not dicts.
        schedule_read = InstallmentScheduleRead(
            contract_id=contract.id,
            version_number=version.version_number,
            status=version.status,
            generated_at=version.generated_at,
            lines=list(lines),
        )
        assert len(schedule_read.lines) == 3
        assert schedule_read.lines[0].scheduled_amount == Decimal("100.00")
        assert schedule_read.lines[0].sequence == 1

    def test_no_active_version_raises_not_found(self, db_session) -> None:
        import uuid
        from datetime import date

        from modules.accounting.models.coa import Account
        from modules.accounting.models.foundation import AccountingConfiguration
        from modules.accounting.repositories.coa import AccountRepository
        from modules.accounting.repositories.fiscal import (
            FiscalPeriodRepository,
            FiscalYearRepository,
            OpeningBalanceRepository,
        )
        from modules.accounting.repositories.foundation import (
            AccountingConfigurationRepository,
        )
        from modules.accounting.repositories.gl import AccountingAuditLogRepository
        from modules.accounting.services.audit_service import AuditLogService
        from modules.accounting.services.fiscal_service import FiscalCalendarService
        from modules.installments.models.contract import InstallmentContract
        from modules.installments.repositories.contract import (
            InstallmentContractRepository,
        )

        account_repo = AccountRepository(db_session)
        fiscal_service = FiscalCalendarService(
            db=db_session,
            year_repo=FiscalYearRepository(db_session),
            period_repo=FiscalPeriodRepository(db_session),
            opening_balance_repo=OpeningBalanceRepository(db_session),
            audit_service=AuditLogService(
                db=db_session, audit_repo=AccountingAuditLogRepository(db_session)
            ),
        )
        company_id = uuid.uuid4()
        customer_id = uuid.uuid4()
        ar_account = account_repo.create(
            Account(
                company_id=company_id,
                account_code="1100",
                account_name="AR",
                account_type="ASSET",
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
        AccountingConfigurationRepository(db_session).create(
            AccountingConfiguration(
                company_id=company_id, default_ar_account_id=ar_account.id
            )
        )
        db_session.commit()

        contract = InstallmentContractRepository(db_session).create(
            InstallmentContract(
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
                status="APPROVED",
                terms_snapshot={"note": "no-schedule-yet fixture"},
            )
        )

        service = _build_contract_service(db_session)
        try:
            service.get_active_schedule(company_id, contract.id)
            raise AssertionError("expected InstallmentNotFoundError")
        except InstallmentNotFoundError:
            pass
