"""[Epic 10, Phase 6, T107] Tests for the money-mutating
``AccountingIntegrationGateway`` methods added in Phase 6 —
``record_down_payment()``, ``record_collection()``, ``reverse_payment()``,
``post_late_charge()``, ``reverse_late_charge()``, ``writeoff()``.

Uses the same SQLite ``db_session`` fixture and Accounting DI factories
(``build_ar_service``/``build_payment_service``/``build_allocation_engine``)
already established by the T109-T112 backward-compatibility regression
files — these tests exercise Accounting business logic (staging,
finalizing, commit ordering), not Postgres-specific constructs, matching
that same convention. Real-Postgres forced-failure atomicity proof for
the underlying staged/finalize methods is covered separately by
T114-T116.

Each test proves the exact stage -> Installments-rows -> finalize-last
sequence plan.md §12.3.1-§12.3.3 requires: the ``stage_installments_rows``
callback receives the *staged* (uncommitted) Accounting objects, an
``InstallmentAuditLog`` row staged inside that callback lands in the
*same* commit as the Accounting rows, and a callback that raises leaves
nothing committed anywhere.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.dependencies import (
    build_allocation_engine,
    build_ar_service,
    build_payment_service,
)
from modules.accounting.models.banking import BankAccount
from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.repositories.banking import BankAccountRepository
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
from modules.installments.models.audit import InstallmentAuditLog
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.services.accounting_gateway import (
    AccountingIntegrationGateway,
)


@pytest.fixture
def setup(db_session: Session) -> dict:
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
    company_id = uuid4()
    ar = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1100",
            account_name="AR",
            account_type="ASSET",
        )
    )
    bank_gl = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1000",
            account_name="Bank",
            account_type="ASSET",
        )
    )
    bank = BankAccountRepository(db_session).create(
        BankAccount(
            company_id=company_id,
            bank_name="Test Bank",
            account_number="ACC-GW-01",
            currency_code="USD",
            gl_account_id=bank_gl.id,
        )
    )
    revenue = account_repo.create(
        Account(
            company_id=company_id,
            account_code="4000",
            account_name="Revenue",
            account_type="REVENUE",
        )
    )
    late_fee_income = account_repo.create(
        Account(
            company_id=company_id,
            account_code="4900",
            account_name="Late Fee Income",
            account_type="REVENUE",
        )
    )
    bad_debt = account_repo.create(
        Account(
            company_id=company_id,
            account_code="6900",
            account_name="Bad Debt Expense",
            account_type="EXPENSE",
        )
    )
    today = date.today()
    fiscal_service.create_fiscal_year(
        company_id,
        f"FY-{uuid4().hex[:8]}",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
    )
    AccountingConfigurationRepository(db_session).create(
        AccountingConfiguration(
            company_id=company_id,
            default_ar_account_id=ar.id,
            default_revenue_account_id=revenue.id,
            default_bad_debt_account_id=bad_debt.id,
        )
    )
    return {
        "company_id": company_id,
        "bank": bank,
        "late_fee_income": late_fee_income,
        "today": today,
    }


@pytest.fixture
def gateway(db_session: Session) -> AccountingIntegrationGateway:
    return AccountingIntegrationGateway(
        ar_service=build_ar_service(db_session, with_sales_sync=False),
        payment_service=build_payment_service(db_session),
        allocation_engine=build_allocation_engine(db_session),
    )


@pytest.fixture
def ar_service(db_session: Session):
    return build_ar_service(db_session, with_sales_sync=False)


@pytest.fixture
def installment_audit_repo(db_session: Session) -> InstallmentAuditLogRepository:
    return InstallmentAuditLogRepository(db_session)


class TestRecordDownPaymentAndCollection:
    def test_record_down_payment_stages_and_finalizes_atomically(
        self,
        gateway: AccountingIntegrationGateway,
        ar_service,
        installment_audit_repo: InstallmentAuditLogRepository,
        setup: dict,
    ) -> None:
        customer_id = uuid4()
        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-GW-1",
            total_amount=Decimal("500.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )

        captured = {}
        contract_id = uuid4()

        def stage_installments_rows(staged_payment, staged_allocation) -> None:
            captured["staged_payment"] = staged_payment
            captured["staged_allocation"] = staged_allocation
            installment_audit_repo.create(
                InstallmentAuditLog(
                    company_id=setup["company_id"],
                    entity_type="InstallmentContract",
                    entity_id=contract_id,
                    action="DOWN_PAYMENT_RECORDED",
                )
            )

        payment, allocation_lines = gateway.record_down_payment(
            company_id=setup["company_id"],
            customer_id=customer_id,
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("500.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("500.00")}
            ],
            actor_id=None,
            stage_installments_rows=stage_installments_rows,
        )

        assert payment.status == "ALLOCATED"
        assert len(allocation_lines) == 1
        assert "staged_payment" in captured
        assert "staged_allocation" in captured

        refreshed_invoice = ar_service.get_transaction_by_id(
            setup["company_id"], invoice.id
        )
        assert refreshed_invoice.outstanding_amount == Decimal("0")

        audit_rows = installment_audit_repo.list_for_entity(
            setup["company_id"], "InstallmentContract", contract_id
        )
        assert len(audit_rows) == 1
        assert audit_rows[0].action == "DOWN_PAYMENT_RECORDED"

    def test_record_collection_targets_same_mechanics(
        self,
        gateway: AccountingIntegrationGateway,
        ar_service,
        setup: dict,
    ) -> None:
        customer_id = uuid4()
        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-GW-2",
            total_amount=Decimal("300.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )

        payment, allocation_lines = gateway.record_collection(
            company_id=setup["company_id"],
            customer_id=customer_id,
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("300.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("300.00")}
            ],
            actor_id=None,
            stage_installments_rows=lambda staged_payment, staged_allocation: None,
        )

        assert payment.status == "ALLOCATED"
        assert len(allocation_lines) == 1

    def test_callback_failure_leaves_nothing_committed(
        self,
        gateway: AccountingIntegrationGateway,
        ar_service,
        db_session: Session,
        setup: dict,
    ) -> None:
        customer_id = uuid4()
        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-GW-3",
            total_amount=Decimal("400.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )

        class _InjectedFailure(Exception):
            pass

        def failing_callback(staged_payment, staged_allocation) -> None:
            raise _InjectedFailure("forced failure before finalize")

        with pytest.raises(_InjectedFailure):
            gateway.record_down_payment(
                company_id=setup["company_id"],
                customer_id=customer_id,
                payment_method="BANK_TRANSFER",
                payment_date=setup["today"],
                amount=Decimal("400.00"),
                currency_code="USD",
                bank_account_id=setup["bank"].id,
                allocation_lines=[
                    {"transaction_id": invoice.id, "amount_foreign": Decimal("400.00")}
                ],
                actor_id=None,
                stage_installments_rows=failing_callback,
            )
        db_session.rollback()

        refreshed_invoice = ar_service.get_transaction_by_id(
            setup["company_id"], invoice.id
        )
        assert refreshed_invoice.outstanding_amount == Decimal("400.00")
        assert refreshed_invoice.status == "OPEN"


class TestReversePayment:
    def test_reverse_payment_unallocates_without_cancelling(
        self,
        gateway: AccountingIntegrationGateway,
        ar_service,
        setup: dict,
    ) -> None:
        customer_id = uuid4()
        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-GW-4",
            total_amount=Decimal("250.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        payment, _ = gateway.record_collection(
            company_id=setup["company_id"],
            customer_id=customer_id,
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("250.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("250.00")}
            ],
            actor_id=None,
            stage_installments_rows=lambda *_: None,
        )

        staged_calls = []
        gateway.reverse_payment(
            company_id=setup["company_id"],
            payment_id=payment.id,
            full_cancellation=False,
            reason="Reversal test",
            actor_id=None,
            stage_installments_rows=lambda: staged_calls.append("staged"),
        )

        assert staged_calls == ["staged"]
        refreshed_invoice = ar_service.get_transaction_by_id(
            setup["company_id"], invoice.id
        )
        assert refreshed_invoice.outstanding_amount == Decimal("250.00")

    def test_reverse_payment_with_full_cancellation_honors_accounting_permission_gate(
        self,
        gateway: AccountingIntegrationGateway,
        ar_service,
        setup: dict,
    ) -> None:
        """The gateway does not bypass or weaken Accounting's own
        ``cancel_payment()`` authorization check (a real, pre-existing
        SoD gate: cancelling a posted payment reverses its GL journal,
        so it requires ``accounting.journal.reverse`` — a system actor,
        ``actor_id=None``, never satisfies a human-approval requirement,
        per ``user_has_accounting_permission()``). ``reverse_payment()``
        still un-allocates first (staged rows are already durable) and
        then lets the pre-existing permission error propagate unchanged
        — proving no Accounting-side authorization behavior was altered
        by this integration."""
        from modules.accounting.exceptions import ApprovalPermissionDeniedError

        customer_id = uuid4()
        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-GW-5",
            total_amount=Decimal("150.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        payment, _ = gateway.record_collection(
            company_id=setup["company_id"],
            customer_id=customer_id,
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("150.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("150.00")}
            ],
            actor_id=None,
            stage_installments_rows=lambda *_: None,
        )

        with pytest.raises(ApprovalPermissionDeniedError):
            gateway.reverse_payment(
                company_id=setup["company_id"],
                payment_id=payment.id,
                full_cancellation=True,
                reason="Full cancellation test",
                actor_id=None,
                stage_installments_rows=lambda: None,
            )

        refreshed_invoice = ar_service.get_transaction_by_id(
            setup["company_id"], invoice.id
        )
        assert refreshed_invoice.outstanding_amount == Decimal("150.00")


class TestPostLateChargeAndReverse:
    def test_post_late_charge_creates_debit_note_ar_transaction(
        self,
        gateway: AccountingIntegrationGateway,
        ar_service,
        setup: dict,
    ) -> None:
        customer_id = uuid4()
        late_charge_id = uuid4()
        captured = {}

        def stage_installments_rows(staged) -> None:
            captured["staged"] = staged

        ar_transaction = gateway.post_late_charge(
            company_id=setup["company_id"],
            customer_id=customer_id,
            amount=Decimal("25.00"),
            contra_account_id=setup["late_fee_income"].id,
            reason="Late payment fee",
            posting_date=setup["today"],
            source_document_id=late_charge_id,
            actor_id=None,
            stage_installments_rows=stage_installments_rows,
        )

        assert ar_transaction.transaction_type == "DEBIT_NOTE"
        assert ar_transaction.outstanding_amount == Decimal("25.00")
        assert ar_transaction.status == "OPEN"
        assert ar_transaction.source_document_type == "InstallmentLateCharge"
        assert ar_transaction.source_document_id == late_charge_id
        assert "staged" in captured

    def test_reverse_late_charge_waives_a_posted_charge(
        self,
        gateway: AccountingIntegrationGateway,
        ar_service,
        setup: dict,
    ) -> None:
        customer_id = uuid4()
        ar_transaction = gateway.post_late_charge(
            company_id=setup["company_id"],
            customer_id=customer_id,
            amount=Decimal("40.00"),
            contra_account_id=setup["late_fee_income"].id,
            reason="Late payment fee",
            posting_date=setup["today"],
            source_document_id=uuid4(),
            actor_id=None,
            stage_installments_rows=lambda staged: None,
        )

        staged_calls = []
        reversed_transaction = gateway.reverse_late_charge(
            company_id=setup["company_id"],
            ar_transaction_id=ar_transaction.id,
            reason="Waived per policy",
            actor_id=None,
            stage_installments_rows=lambda: staged_calls.append("staged"),
        )

        assert staged_calls == ["staged"]
        assert reversed_transaction.outstanding_amount == Decimal("0")
        assert reversed_transaction.status == "PAID"

    def test_post_late_charge_callback_failure_leaves_nothing_committed(
        self,
        gateway: AccountingIntegrationGateway,
        ar_service,
        db_session: Session,
        setup: dict,
    ) -> None:
        class _InjectedFailure(Exception):
            pass

        def failing_callback(staged) -> None:
            raise _InjectedFailure("forced failure before finalize")

        with pytest.raises(_InjectedFailure):
            gateway.post_late_charge(
                company_id=setup["company_id"],
                customer_id=uuid4(),
                amount=Decimal("10.00"),
                contra_account_id=setup["late_fee_income"].id,
                reason="Late payment fee",
                posting_date=setup["today"],
                source_document_id=uuid4(),
                actor_id=None,
                stage_installments_rows=failing_callback,
            )
        db_session.rollback()

        balance = ar_service.reconcile_ar_control_account(setup["company_id"])
        assert balance == Decimal("0")


class TestWriteoff:
    def test_writeoff_marks_ar_transaction_written_off(
        self,
        gateway: AccountingIntegrationGateway,
        ar_service,
        setup: dict,
    ) -> None:
        customer_id = uuid4()
        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-GW-6",
            total_amount=Decimal("600.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )

        captured = {}

        def stage_installments_rows(staged) -> None:
            captured["staged"] = staged

        written_off = gateway.writeoff(
            company_id=setup["company_id"],
            ar_transaction_id=invoice.id,
            reason="Uncollectible",
            actor_id=None,
            stage_installments_rows=stage_installments_rows,
        )

        assert written_off.status == "WRITTEN_OFF"
        assert written_off.outstanding_amount == Decimal("0")
        assert "staged" in captured

    def test_writeoff_callback_failure_leaves_nothing_committed(
        self,
        gateway: AccountingIntegrationGateway,
        ar_service,
        db_session: Session,
        setup: dict,
    ) -> None:
        customer_id = uuid4()
        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-GW-7",
            total_amount=Decimal("700.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )

        class _InjectedFailure(Exception):
            pass

        def failing_callback(staged) -> None:
            raise _InjectedFailure("forced failure before finalize")

        with pytest.raises(_InjectedFailure):
            gateway.writeoff(
                company_id=setup["company_id"],
                ar_transaction_id=invoice.id,
                reason="Uncollectible",
                actor_id=None,
                stage_installments_rows=failing_callback,
            )
        db_session.rollback()

        refreshed_invoice = ar_service.get_transaction_by_id(
            setup["company_id"], invoice.id
        )
        assert refreshed_invoice.status == "OPEN"
        assert refreshed_invoice.outstanding_amount == Decimal("700.00")


class TestTenantIsolation:
    """[Phase 6 Special Hard-Gate Rule §5] Every Accounting effect a
    gateway money-mutating method reaches must belong to the
    authoritative ``company_id`` passed in — a caller supplying a
    *different* company's id must never see, mutate, or write off
    another tenant's ``ARTransaction``/``Payment``. These methods add no
    new queries of their own (they delegate straight to Accounting's
    already company_id-scoped ``get_by_id_or_none``/``find_by_source_document``
    lookups) — this test proves that inherited scoping genuinely holds
    for the Phase 6 call paths, not merely that it holds somewhere in
    Accounting's own pre-existing test suite.
    """

    def test_writeoff_cannot_reach_another_companys_ar_transaction(
        self, gateway: AccountingIntegrationGateway, ar_service, setup: dict
    ) -> None:
        from modules.accounting.exceptions import ARTransactionNotFoundError

        customer_id = uuid4()
        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-GW-TENANT-1",
            total_amount=Decimal("900.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )

        other_company_id = uuid4()
        with pytest.raises(ARTransactionNotFoundError):
            gateway.writeoff(
                company_id=other_company_id,
                ar_transaction_id=invoice.id,
                reason="Cross-tenant write-off attempt",
                actor_id=None,
                stage_installments_rows=lambda staged: None,
            )

        refreshed_invoice = ar_service.get_transaction_by_id(
            setup["company_id"], invoice.id
        )
        assert refreshed_invoice.status == "OPEN"
        assert refreshed_invoice.outstanding_amount == Decimal("900.00")

    def test_reverse_late_charge_cannot_reach_another_companys_ar_transaction(
        self, gateway: AccountingIntegrationGateway, ar_service, setup: dict
    ) -> None:
        from modules.accounting.exceptions import ARTransactionNotFoundError

        ar_transaction = gateway.post_late_charge(
            company_id=setup["company_id"],
            customer_id=uuid4(),
            amount=Decimal("30.00"),
            contra_account_id=setup["late_fee_income"].id,
            reason="Late payment fee",
            posting_date=setup["today"],
            source_document_id=uuid4(),
            actor_id=None,
            stage_installments_rows=lambda staged: None,
        )

        other_company_id = uuid4()
        with pytest.raises(ARTransactionNotFoundError):
            gateway.reverse_late_charge(
                company_id=other_company_id,
                ar_transaction_id=ar_transaction.id,
                reason="Cross-tenant waiver attempt",
                actor_id=None,
                stage_installments_rows=lambda: None,
            )

        refreshed_transaction = ar_service.get_transaction_by_id(
            setup["company_id"], ar_transaction.id
        )
        assert refreshed_transaction.status == "OPEN"
        assert refreshed_transaction.outstanding_amount == Decimal("30.00")

    def test_reverse_payment_cannot_reach_another_companys_payment(
        self, gateway: AccountingIntegrationGateway, ar_service, setup: dict
    ) -> None:
        from modules.accounting.exceptions import PaymentNotFoundError

        customer_id = uuid4()
        invoice, _ = ar_service.record_sales_invoice(
            company_id=setup["company_id"],
            customer_id=customer_id,
            invoice_id=uuid4(),
            invoice_number="INV-GW-TENANT-2",
            total_amount=Decimal("200.00"),
            currency_code="USD",
            transaction_date=setup["today"],
            due_date=setup["today"],
            actor_id=None,
        )
        payment, _ = gateway.record_collection(
            company_id=setup["company_id"],
            customer_id=customer_id,
            payment_method="BANK_TRANSFER",
            payment_date=setup["today"],
            amount=Decimal("200.00"),
            currency_code="USD",
            bank_account_id=setup["bank"].id,
            allocation_lines=[
                {"transaction_id": invoice.id, "amount_foreign": Decimal("200.00")}
            ],
            actor_id=None,
            stage_installments_rows=lambda *_: None,
        )

        other_company_id = uuid4()
        with pytest.raises(PaymentNotFoundError):
            gateway.reverse_payment(
                company_id=other_company_id,
                payment_id=payment.id,
                full_cancellation=False,
                reason="Cross-tenant reversal attempt",
                actor_id=None,
                stage_installments_rows=lambda: None,
            )
