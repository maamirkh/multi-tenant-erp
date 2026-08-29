"""[Epic 10, Phase 9, T160] Service test — settlement quote generation is
provably non-mutating (no contract/schedule state change, no Accounting
call) even though it IS audited (FR-INST-341).

Real Postgres (schedule tables require it).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from modules.accounting.models.payments import Payment
from modules.installments.models.audit import InstallmentAuditLog
from modules.installments.models.contract import InstallmentContract
from modules.installments.models.schedule import InstallmentScheduleLine
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_settlement_service,
)


class TestSettlementQuoteNonMutating:
    def test_quote_does_not_change_contract_or_schedule_state(self, db_session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        service = build_settlement_service(db_session)

        before_version = ctx["contract"].version
        before_status = ctx["contract"].status
        before_line_amounts = sorted(
            str(line.scheduled_amount) for line in ctx["schedule_lines"]
        )

        quote = service.generate_quote(
            ctx["company_id"], ctx["contract"].id, date.today()
        )

        assert quote.settlement_amount == Decimal("200.00")
        assert quote.schedule_outstanding == Decimal("200.00")
        assert quote.late_charge_outstanding == Decimal("0")

        refreshed_contract = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        assert refreshed_contract.version == before_version
        assert refreshed_contract.status == before_status

        refreshed_lines = (
            db_session.query(InstallmentScheduleLine)
            .filter_by(company_id=ctx["company_id"])
            .all()
        )
        assert sorted(str(line.scheduled_amount) for line in refreshed_lines) == (
            before_line_amounts
        )

    def test_quote_makes_no_accounting_call(self, db_session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        service = build_settlement_service(db_session)

        service.generate_quote(ctx["company_id"], ctx["contract"].id, date.today())

        payments = (
            db_session.execute(
                select(Payment).where(Payment.company_id == ctx["company_id"])
            )
            .scalars()
            .all()
        )
        assert payments == []

    def test_quote_is_audited_despite_being_non_mutating(self, db_session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        service = build_settlement_service(db_session)

        service.generate_quote(ctx["company_id"], ctx["contract"].id, date.today())

        audit_rows = (
            db_session.execute(
                select(InstallmentAuditLog).where(
                    InstallmentAuditLog.entity_id == ctx["contract"].id,
                    InstallmentAuditLog.action == "SETTLEMENT_QUOTED",
                )
            )
            .scalars()
            .all()
        )
        assert len(audit_rows) == 1

    def test_two_quotes_for_the_same_unchanged_state_are_identical(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=3, installment_amount=Decimal("50.00")
        )
        service = build_settlement_service(db_session)
        as_of = date.today()

        first = service.generate_quote(ctx["company_id"], ctx["contract"].id, as_of)
        second = service.generate_quote(ctx["company_id"], ctx["contract"].id, as_of)

        assert first.settlement_amount == second.settlement_amount == Decimal("150.00")
